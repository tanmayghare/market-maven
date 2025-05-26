"""
Advanced error handling and resilience patterns for the stock agent.
"""

import time
import asyncio
from typing import Dict, Any, Optional, Callable, Type, Union, List
from functools import wraps
from datetime import datetime, timedelta
from enum import Enum

from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log
)

from market_maven.core.exceptions import (
    StockAgentError, 
    DataFetchError, 
    RateLimitError,
    TradingError,
    AnalysisError
)
from market_maven.core.logging import LoggerMixin, get_logger
from market_maven.core.metrics import metrics

logger = get_logger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker implementation for external service calls."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply circuit breaker to a function."""
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info(f"Circuit breaker half-open for {func.__name__}")
                else:
                    raise StockAgentError(
                        f"Circuit breaker is OPEN for {func.__name__}",
                        error_code="CIRCUIT_BREAKER_OPEN"
                    )
            
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
                
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit breaker."""
        if self.last_failure_time is None:
            return True
        
        return (datetime.utcnow() - self.last_failure_time).total_seconds() > self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        logger.debug("Circuit breaker reset to CLOSED")
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(
                f"Circuit breaker OPEN after {self.failure_count} failures",
                failure_threshold=self.failure_threshold
            )


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 10.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_exceptions: List[Type[Exception]] = None
    ):
        self.max_attempts = max_attempts
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_exceptions = retry_exceptions or [
            DataFetchError,
            RateLimitError,
            ConnectionError,
            TimeoutError
        ]


class ErrorHandler(LoggerMixin):
    """Centralized error handling with context and recovery strategies."""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.last_errors: Dict[str, datetime] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def get_circuit_breaker(
        self, 
        name: str, 
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception
            )
        return self.circuit_breakers[name]
    
    def create_retry_decorator(self, config: RetryConfig) -> Callable:
        """Create a retry decorator with the given configuration."""
        
        return retry(
            stop=stop_after_attempt(config.max_attempts),
            wait=wait_exponential(
                multiplier=config.min_wait,
                min=config.min_wait,
                max=config.max_wait,
                exp_base=config.exponential_base
            ),
            retry=retry_if_exception_type(tuple(config.retry_exceptions)),
            before_sleep=before_sleep_log(logger, log_level="WARNING")
        )
    
    async def handle_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        operation: str,
        recovery_strategy: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Handle an error with context and optional recovery."""
        
        error_key = f"{operation}:{type(error).__name__}"
        
        # Track error frequency
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_errors[error_key] = datetime.utcnow()
        
        # Log error with context
        error_logger = self.log_operation(
            "error_handling",
            operation=operation,
            error_type=type(error).__name__,
            error_message=str(error),
            error_count=self.error_counts[error_key],
            **context
        )
        
        # Determine error severity
        severity = self._determine_severity(error, self.error_counts[error_key])
        
        if severity == "critical":
            error_logger.error("Critical error occurred")
        elif severity == "warning":
            error_logger.warning("Warning-level error occurred")
        else:
            error_logger.info("Recoverable error occurred")
        
        # Record metrics
        metrics.record_error(
            operation=operation,
            error_type=type(error).__name__,
            severity=severity
        )
        
        # Attempt recovery if strategy provided
        recovery_result = None
        if recovery_strategy:
            try:
                recovery_result = await recovery_strategy(error, context)
                error_logger.info("Recovery strategy executed successfully")
            except Exception as recovery_error:
                error_logger.error(
                    "Recovery strategy failed",
                    recovery_error=str(recovery_error)
                )
        
        return {
            "error": {
                "type": type(error).__name__,
                "message": str(error),
                "severity": severity,
                "count": self.error_counts[error_key],
                "timestamp": datetime.utcnow().isoformat()
            },
            "context": context,
            "recovery_attempted": recovery_strategy is not None,
            "recovery_result": recovery_result
        }
    
    def _determine_severity(self, error: Exception, count: int) -> str:
        """Determine error severity based on type and frequency."""
        
        # Critical errors
        if isinstance(error, (TradingError, SecurityError)):
            return "critical"
        
        # High frequency errors become critical
        if count >= 10:
            return "critical"
        
        # Rate limit and data fetch errors are warnings
        if isinstance(error, (RateLimitError, DataFetchError)):
            return "warning" if count < 5 else "critical"
        
        # Analysis errors are usually recoverable
        if isinstance(error, AnalysisError):
            return "info" if count < 3 else "warning"
        
        # Default classification
        if count >= 5:
            return "warning"
        
        return "info"
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        
        total_errors = sum(self.error_counts.values())
        recent_errors = {
            key: count for key, count in self.error_counts.items()
            if key in self.last_errors and 
            (datetime.utcnow() - self.last_errors[key]).total_seconds() < 3600
        }
        
        return {
            "total_errors": total_errors,
            "recent_errors_1h": sum(recent_errors.values()),
            "error_types": dict(self.error_counts),
            "circuit_breaker_states": {
                name: cb.state.value 
                for name, cb in self.circuit_breakers.items()
            }
        }


# Predefined retry configurations
RETRY_CONFIGS = {
    "data_fetch": RetryConfig(
        max_attempts=3,
        min_wait=1.0,
        max_wait=10.0,
        retry_exceptions=[DataFetchError, ConnectionError, TimeoutError]
    ),
    "api_call": RetryConfig(
        max_attempts=5,
        min_wait=0.5,
        max_wait=5.0,
        retry_exceptions=[RateLimitError, ConnectionError]
    ),
    "analysis": RetryConfig(
        max_attempts=2,
        min_wait=2.0,
        max_wait=8.0,
        retry_exceptions=[AnalysisError]
    ),
    "trading": RetryConfig(
        max_attempts=1,  # No retries for trading operations
        retry_exceptions=[]
    )
}


# Global error handler instance
error_handler = ErrorHandler()


# Convenience decorators
def with_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: Type[Exception] = Exception
):
    """Decorator to add circuit breaker to a function."""
    def decorator(func: Callable) -> Callable:
        circuit_breaker = error_handler.get_circuit_breaker(
            name, failure_threshold, recovery_timeout, expected_exception
        )
        return circuit_breaker(func)
    return decorator


def with_retry(config_name: str = "api_call"):
    """Decorator to add retry logic to a function."""
    def decorator(func: Callable) -> Callable:
        config = RETRY_CONFIGS.get(config_name, RETRY_CONFIGS["api_call"])
        retry_decorator = error_handler.create_retry_decorator(config)
        return retry_decorator(func)
    return decorator


def with_error_handling(
    operation: str,
    recovery_strategy: Optional[Callable] = None
):
    """Decorator to add comprehensive error handling to a function."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                context = {
                    "function": func.__name__,
                    "args": str(args)[:200],  # Truncate for logging
                    "kwargs": {k: str(v)[:100] for k, v in kwargs.items()}
                }
                
                error_result = await error_handler.handle_error(
                    e, context, operation, recovery_strategy
                )
                
                # Re-raise the original exception
                raise e
        
        return wrapper
    return decorator 