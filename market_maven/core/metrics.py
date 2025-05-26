"""
Metrics collection and monitoring for the stock agent.
"""

import time
from typing import Dict, Any, Optional
from contextlib import contextmanager
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from .logging import LoggerMixin


class MetricsCollector(LoggerMixin):
    """Centralized metrics collection for monitoring and observability."""
    
    def __init__(self) -> None:
        # Tool execution metrics
        self.tool_executions = Counter(
            'market_maven_tool_executions_total',
            'Total number of tool executions',
            ['tool_name', 'status']
        )
        
        self.tool_duration = Histogram(
            'market_maven_tool_duration_seconds',
            'Time spent executing tools',
            ['tool_name']
        )
        
        # Data fetching metrics
        self.data_fetch_requests = Counter(
            'market_maven_data_fetch_requests_total',
            'Total number of data fetch requests',
            ['source', 'symbol', 'status']
        )
        
        self.data_fetch_duration = Histogram(
            'market_maven_data_fetch_duration_seconds',
            'Time spent fetching data',
            ['source']
        )
        
        # Analysis metrics
        self.analysis_requests = Counter(
            'market_maven_analysis_requests_total',
            'Total number of analysis requests',
            ['analysis_type', 'symbol', 'status']
        )
        
        self.analysis_duration = Histogram(
            'market_maven_analysis_duration_seconds',
            'Time spent on analysis',
            ['analysis_type']
        )
        
        self.analysis_confidence = Histogram(
            'market_maven_analysis_confidence',
            'Confidence scores of analysis results',
            ['analysis_type', 'recommendation']
        )
        
        # Trading metrics
        self.trade_requests = Counter(
            'market_maven_trade_requests_total',
            'Total number of trade requests',
            ['symbol', 'action', 'status']
        )
        
        self.trade_volume = Histogram(
            'market_maven_trade_volume',
            'Volume of trades executed',
            ['symbol', 'action']
        )
        
        self.trade_value = Histogram(
            'market_maven_trade_value_usd',
            'Value of trades executed in USD',
            ['symbol', 'action']
        )
        
        # System metrics
        self.active_connections = Gauge(
            'market_maven_active_connections',
            'Number of active broker connections'
        )
        
        # Enhanced cache metrics
        self.cache_operations = Counter(
            'market_maven_cache_operations_total',
            'Total number of cache operations',
            ['cache_type', 'operation', 'status']
        )
        
        self.cache_duration = Histogram(
            'market_maven_cache_duration_seconds',
            'Time spent on cache operations',
            ['cache_type', 'operation']
        )
        
        # Error metrics
        self.error_counter = Counter(
            'market_maven_errors_total',
            'Total number of errors',
            ['operation', 'error_type', 'severity']
        )
    
    @contextmanager
    def time_operation(self, metric: Histogram, **labels: str):
        """Context manager to time operations."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            metric.labels(**labels).observe(duration)
    
    def record_tool_execution(
        self, 
        tool_name: str, 
        status: str, 
        duration: Optional[float] = None
    ) -> None:
        """Record tool execution metrics."""
        self.tool_executions.labels(tool_name=tool_name, status=status).inc()
        if duration is not None:
            self.tool_duration.labels(tool_name=tool_name).observe(duration)
        
        self.logger.info(
            "Tool execution recorded",
            tool_name=tool_name,
            status=status,
            duration=duration
        )
    
    def record_data_fetch(
        self, 
        source: str, 
        symbol: str, 
        status: str,
        duration: Optional[float] = None
    ) -> None:
        """Record data fetching metrics."""
        self.data_fetch_requests.labels(
            source=source, 
            symbol=symbol, 
            status=status
        ).inc()
        
        if duration is not None:
            self.data_fetch_duration.labels(source=source).observe(duration)
        
        self.logger.info(
            "Data fetch recorded",
            source=source,
            symbol=symbol,
            status=status,
            duration=duration
        )
    
    def record_analysis(
        self, 
        analysis_type: str, 
        symbol: str, 
        status: str,
        confidence: Optional[float] = None,
        recommendation: Optional[str] = None,
        duration: Optional[float] = None
    ) -> None:
        """Record analysis metrics."""
        self.analysis_requests.labels(
            analysis_type=analysis_type,
            symbol=symbol,
            status=status
        ).inc()
        
        if duration is not None:
            self.analysis_duration.labels(analysis_type=analysis_type).observe(duration)
        
        if confidence is not None and recommendation is not None:
            self.analysis_confidence.labels(
                analysis_type=analysis_type,
                recommendation=recommendation
            ).observe(confidence)
        
        self.logger.info(
            "Analysis recorded",
            analysis_type=analysis_type,
            symbol=symbol,
            status=status,
            confidence=confidence,
            recommendation=recommendation,
            duration=duration
        )
    
    def record_trade(
        self, 
        symbol: str, 
        action: str, 
        status: str,
        volume: Optional[int] = None,
        value: Optional[float] = None
    ) -> None:
        """Record trading metrics."""
        self.trade_requests.labels(
            symbol=symbol,
            action=action,
            status=status
        ).inc()
        
        if volume is not None:
            self.trade_volume.labels(symbol=symbol, action=action).observe(volume)
        
        if value is not None:
            self.trade_value.labels(symbol=symbol, action=action).observe(value)
        
        self.logger.info(
            "Trade recorded",
            symbol=symbol,
            action=action,
            status=status,
            volume=volume,
            value=value
        )
    
    def record_cache_event(
        self, 
        cache_type: str, 
        hit: bool, 
        duration: Optional[float] = None,
        operation: str = "get",
        error: bool = False
    ) -> None:
        """Record cache event with enhanced metrics."""
        if error:
            status = "error"
        else:
            status = "hit" if hit else "miss"
        
        self.cache_operations.labels(
            cache_type=cache_type,
            operation=operation,
            status=status
        ).inc()
        
        if duration is not None:
            self.cache_duration.labels(
                cache_type=cache_type,
                operation=operation
            ).observe(duration)
    
    def record_error(
        self,
        operation: str,
        error_type: str,
        severity: str = "info"
    ) -> None:
        """Record error metrics."""
        self.error_counter.labels(
            operation=operation,
            error_type=error_type,
            severity=severity
        ).inc()
    
    def set_active_connections(self, count: int) -> None:
        """Set the number of active broker connections."""
        self.active_connections.set(count)
    
    def start_metrics_server(self, port: int = 8000) -> None:
        """Start Prometheus metrics server."""
        start_http_server(port)
        self.logger.info("Metrics server started", port=port)


# Global metrics instance
metrics = MetricsCollector() 