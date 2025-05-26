"""
Security utilities for the stock agent.
"""

import os
import hashlib
import secrets
from typing import Optional, Dict, Any, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import json
from datetime import datetime, timedelta

from .logging import LoggerMixin
from .exceptions import SecurityError


class EncryptionManager(LoggerMixin):
    """Manages encryption and decryption of sensitive data."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption manager.
        
        Args:
            encryption_key: Base64 encoded encryption key. If None, generates a new key.
        """
        if encryption_key:
            try:
                self.key = encryption_key.encode()
                self.fernet = Fernet(self.key)
            except Exception as e:
                raise SecurityError(f"Invalid encryption key: {e}")
        else:
            self.key = Fernet.generate_key()
            self.fernet = Fernet(self.key)
        
        self.logger.info("Encryption manager initialized")
    
    def encrypt(self, data: Union[str, Dict[str, Any]]) -> str:
        """
        Encrypt data.
        
        Args:
            data: Data to encrypt (string or dict)
            
        Returns:
            Base64 encoded encrypted data
        """
        try:
            if isinstance(data, dict):
                data = json.dumps(data)
            
            encrypted_data = self.fernet.encrypt(data.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
            raise SecurityError(f"Encryption failed: {e}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            
        Returns:
            Decrypted data as string
        """
        try:
            decoded_data = base64.b64decode(encrypted_data.encode())
            decrypted_data = self.fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            raise SecurityError(f"Decryption failed: {e}")
    
    def decrypt_json(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt data and parse as JSON.
        
        Args:
            encrypted_data: Base64 encoded encrypted JSON data
            
        Returns:
            Decrypted data as dictionary
        """
        try:
            decrypted_str = self.decrypt(encrypted_data)
            return json.loads(decrypted_str)
        except json.JSONDecodeError as e:
            raise SecurityError(f"Invalid JSON in decrypted data: {e}")
    
    def get_key_string(self) -> str:
        """Get the encryption key as a base64 string."""
        return self.key.decode()


class APIKeyManager(LoggerMixin):
    """Manages API keys with encryption and rotation."""
    
    def __init__(self, encryption_manager: EncryptionManager):
        """
        Initialize API key manager.
        
        Args:
            encryption_manager: Encryption manager instance
        """
        self.encryption_manager = encryption_manager
        self._api_keys: Dict[str, Dict[str, Any]] = {}
        self.logger.info("API key manager initialized")
    
    def store_api_key(
        self, 
        service_name: str, 
        api_key: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Store an API key with encryption.
        
        Args:
            service_name: Name of the service (e.g., 'alpha_vantage')
            api_key: The API key to store
            metadata: Optional metadata about the key
        """
        try:
            encrypted_key = self.encryption_manager.encrypt(api_key)
            
            self._api_keys[service_name] = {
                "encrypted_key": encrypted_key,
                "created_at": datetime.utcnow().isoformat(),
                "last_used": None,
                "usage_count": 0,
                "metadata": metadata or {}
            }
            
            self.logger.info(f"API key stored for service: {service_name}")
        except Exception as e:
            self.logger.error(f"Failed to store API key for {service_name}: {e}")
            raise SecurityError(f"Failed to store API key: {e}")
    
    def get_api_key(self, service_name: str) -> Optional[str]:
        """
        Retrieve and decrypt an API key.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Decrypted API key or None if not found
        """
        try:
            if service_name not in self._api_keys:
                return None
            
            key_data = self._api_keys[service_name]
            decrypted_key = self.encryption_manager.decrypt(key_data["encrypted_key"])
            
            # Update usage statistics
            key_data["last_used"] = datetime.utcnow().isoformat()
            key_data["usage_count"] += 1
            
            return decrypted_key
        except Exception as e:
            self.logger.error(f"Failed to retrieve API key for {service_name}: {e}")
            return None
    
    def rotate_api_key(self, service_name: str, new_api_key: str) -> None:
        """
        Rotate an API key.
        
        Args:
            service_name: Name of the service
            new_api_key: New API key
        """
        if service_name not in self._api_keys:
            raise SecurityError(f"No API key found for service: {service_name}")
        
        old_metadata = self._api_keys[service_name].get("metadata", {})
        old_metadata["rotated_at"] = datetime.utcnow().isoformat()
        
        self.store_api_key(service_name, new_api_key, old_metadata)
        self.logger.info(f"API key rotated for service: {service_name}")
    
    def list_services(self) -> Dict[str, Dict[str, Any]]:
        """
        List all services with their metadata (excluding keys).
        
        Returns:
            Dictionary of service metadata
        """
        result = {}
        for service_name, key_data in self._api_keys.items():
            result[service_name] = {
                "created_at": key_data["created_at"],
                "last_used": key_data["last_used"],
                "usage_count": key_data["usage_count"],
                "metadata": key_data["metadata"]
            }
        return result
    
    def remove_api_key(self, service_name: str) -> bool:
        """
        Remove an API key.
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if key was removed, False if not found
        """
        if service_name in self._api_keys:
            del self._api_keys[service_name]
            self.logger.info(f"API key removed for service: {service_name}")
            return True
        return False


class DataMasker(LoggerMixin):
    """Utility for masking sensitive data in logs and outputs."""
    
    SENSITIVE_PATTERNS = {
        'api_key': r'(?i)(api[_-]?key|apikey|key)["\s]*[:=]["\s]*([a-zA-Z0-9]{8,})',
        'token': r'(?i)(token|access[_-]?token)["\s]*[:=]["\s]*([a-zA-Z0-9]{8,})',
        'password': r'(?i)(password|passwd|pwd)["\s]*[:=]["\s]*([^\s"]{4,})',
        'secret': r'(?i)(secret|client[_-]?secret)["\s]*[:=]["\s]*([a-zA-Z0-9]{8,})',
        'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b'
    }
    
    @classmethod
    def mask_sensitive_data(cls, text: str, mask_char: str = "*") -> str:
        """
        Mask sensitive data in text.
        
        Args:
            text: Text to mask
            mask_char: Character to use for masking
            
        Returns:
            Text with sensitive data masked
        """
        import re
        
        masked_text = text
        
        for pattern_name, pattern in cls.SENSITIVE_PATTERNS.items():
            def replace_match(match):
                prefix = match.group(1)
                sensitive_value = match.group(2)
                
                if len(sensitive_value) <= 4:
                    masked_value = mask_char * len(sensitive_value)
                else:
                    # Show first 2 and last 2 characters
                    masked_value = sensitive_value[:2] + mask_char * (len(sensitive_value) - 4) + sensitive_value[-2:]
                
                return f"{prefix}={masked_value}"
            
            masked_text = re.sub(pattern, replace_match, masked_text)
        
        return masked_text
    
    @classmethod
    def mask_dict_values(cls, data: Dict[str, Any], sensitive_keys: Optional[list] = None) -> Dict[str, Any]:
        """
        Mask sensitive values in a dictionary.
        
        Args:
            data: Dictionary to mask
            sensitive_keys: List of keys to mask (case-insensitive)
            
        Returns:
            Dictionary with sensitive values masked
        """
        if sensitive_keys is None:
            sensitive_keys = ['api_key', 'apikey', 'key', 'token', 'password', 'secret', 'passwd']
        
        sensitive_keys_lower = [key.lower() for key in sensitive_keys]
        masked_data = {}
        
        for key, value in data.items():
            if key.lower() in sensitive_keys_lower:
                if isinstance(value, str) and len(value) > 4:
                    masked_data[key] = value[:2] + "*" * (len(value) - 4) + value[-2:]
                else:
                    masked_data[key] = "*" * len(str(value))
            elif isinstance(value, dict):
                masked_data[key] = cls.mask_dict_values(value, sensitive_keys)
            else:
                masked_data[key] = value
        
        return masked_data


class SecurityAuditor(LoggerMixin):
    """Security auditing and monitoring utilities."""
    
    def __init__(self):
        """Initialize security auditor."""
        self.audit_log: list = []
        self.failed_attempts: Dict[str, list] = {}
        self.logger.info("Security auditor initialized")
    
    def log_security_event(
        self, 
        event_type: str, 
        details: Dict[str, Any], 
        severity: str = "INFO"
    ) -> None:
        """
        Log a security event.
        
        Args:
            event_type: Type of security event
            details: Event details
            severity: Event severity (INFO, WARNING, ERROR, CRITICAL)
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "details": DataMasker.mask_dict_values(details)
        }
        
        self.audit_log.append(event)
        
        # Log to structured logger
        log_method = getattr(self.logger, severity.lower(), self.logger.info)
        log_method(f"Security event: {event_type}", **event["details"])
    
    def log_failed_attempt(self, identifier: str, attempt_type: str, details: Dict[str, Any]) -> None:
        """
        Log a failed security attempt.
        
        Args:
            identifier: Identifier for the source of the attempt
            attempt_type: Type of attempt (e.g., 'api_access', 'authentication')
            details: Attempt details
        """
        if identifier not in self.failed_attempts:
            self.failed_attempts[identifier] = []
        
        attempt = {
            "timestamp": datetime.utcnow().isoformat(),
            "attempt_type": attempt_type,
            "details": details
        }
        
        self.failed_attempts[identifier].append(attempt)
        
        # Clean old attempts (keep last 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self.failed_attempts[identifier] = [
            attempt for attempt in self.failed_attempts[identifier]
            if datetime.fromisoformat(attempt["timestamp"]) > cutoff_time
        ]
        
        self.log_security_event(
            "failed_attempt",
            {
                "identifier": identifier,
                "attempt_type": attempt_type,
                "attempt_count": len(self.failed_attempts[identifier]),
                **details
            },
            "WARNING"
        )
    
    def is_rate_limited(self, identifier: str, max_attempts: int = 5, window_hours: int = 1) -> bool:
        """
        Check if an identifier should be rate limited.
        
        Args:
            identifier: Identifier to check
            max_attempts: Maximum attempts allowed
            window_hours: Time window in hours
            
        Returns:
            True if rate limited
        """
        if identifier not in self.failed_attempts:
            return False
        
        cutoff_time = datetime.utcnow() - timedelta(hours=window_hours)
        recent_attempts = [
            attempt for attempt in self.failed_attempts[identifier]
            if datetime.fromisoformat(attempt["timestamp"]) > cutoff_time
        ]
        
        return len(recent_attempts) >= max_attempts
    
    def get_audit_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get audit summary for the specified time period.
        
        Args:
            hours: Number of hours to include in summary
            
        Returns:
            Audit summary
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        recent_events = [
            event for event in self.audit_log
            if datetime.fromisoformat(event["timestamp"]) > cutoff_time
        ]
        
        summary = {
            "period_hours": hours,
            "total_events": len(recent_events),
            "events_by_type": {},
            "events_by_severity": {},
            "failed_attempts_summary": {}
        }
        
        # Count events by type and severity
        for event in recent_events:
            event_type = event["event_type"]
            severity = event["severity"]
            
            summary["events_by_type"][event_type] = summary["events_by_type"].get(event_type, 0) + 1
            summary["events_by_severity"][severity] = summary["events_by_severity"].get(severity, 0) + 1
        
        # Failed attempts summary
        for identifier, attempts in self.failed_attempts.items():
            recent_attempts = [
                attempt for attempt in attempts
                if datetime.fromisoformat(attempt["timestamp"]) > cutoff_time
            ]
            if recent_attempts:
                summary["failed_attempts_summary"][identifier] = len(recent_attempts)
        
        return summary


class SecureConfigManager(LoggerMixin):
    """Secure configuration management with encryption."""
    
    def __init__(self, encryption_manager: EncryptionManager):
        """
        Initialize secure config manager.
        
        Args:
            encryption_manager: Encryption manager instance
        """
        self.encryption_manager = encryption_manager
        self._config: Dict[str, Any] = {}
        self.logger.info("Secure config manager initialized")
    
    def set_secure_value(self, key: str, value: Any, encrypt: bool = True) -> None:
        """
        Set a configuration value with optional encryption.
        
        Args:
            key: Configuration key
            value: Configuration value
            encrypt: Whether to encrypt the value
        """
        if encrypt:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            encrypted_value = self.encryption_manager.encrypt(str(value))
            self._config[key] = {"encrypted": True, "value": encrypted_value}
        else:
            self._config[key] = {"encrypted": False, "value": value}
        
        self.logger.debug(f"Configuration value set for key: {key} (encrypted: {encrypt})")
    
    def get_secure_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value with automatic decryption.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        if key not in self._config:
            return default
        
        config_item = self._config[key]
        
        if config_item["encrypted"]:
            try:
                decrypted_value = self.encryption_manager.decrypt(config_item["value"])
                # Try to parse as JSON if it looks like JSON
                if decrypted_value.startswith(("{", "[")):
                    try:
                        return json.loads(decrypted_value)
                    except json.JSONDecodeError:
                        pass
                return decrypted_value
            except Exception as e:
                self.logger.error(f"Failed to decrypt config value for key {key}: {e}")
                return default
        else:
            return config_item["value"]
    
    def export_config(self, include_encrypted: bool = False) -> Dict[str, Any]:
        """
        Export configuration.
        
        Args:
            include_encrypted: Whether to include encrypted values (still encrypted)
            
        Returns:
            Configuration dictionary
        """
        exported = {}
        
        for key, config_item in self._config.items():
            if config_item["encrypted"] and not include_encrypted:
                exported[key] = {"encrypted": True, "value": "[ENCRYPTED]"}
            else:
                exported[key] = config_item.copy()
        
        return exported


# Global security instances
_encryption_manager: Optional[EncryptionManager] = None
_api_key_manager: Optional[APIKeyManager] = None
_security_auditor: Optional[SecurityAuditor] = None


def get_encryption_manager() -> EncryptionManager:
    """Get global encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        encryption_key = os.getenv("ENCRYPTION_KEY")
        _encryption_manager = EncryptionManager(encryption_key)
    return _encryption_manager


def get_api_key_manager() -> APIKeyManager:
    """Get global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager(get_encryption_manager())
    return _api_key_manager


def get_security_auditor() -> SecurityAuditor:
    """Get global security auditor instance."""
    global _security_auditor
    if _security_auditor is None:
        _security_auditor = SecurityAuditor()
    return _security_auditor 