"""
Performance optimization utilities for the stock agent.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Callable, TypeVar, Generic
from functools import wraps, lru_cache
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from contextlib import asynccontextmanager
import threading
from queue import Queue, Empty

import aiohttp
from aiohttp import ClientSession, TCPConnector
import numpy as np
import pandas as pd

from market_maven.core.logging import get_logger
from market_maven.core.metrics import metrics
from market_maven.core.cache import cache_manager, CacheKeyBuilder

logger = get_logger(__name__)

T = TypeVar('T')


class ConnectionPool:
    """HTTP connection pool for efficient API requests."""
    
    def __init__(
        self,
        max_connections: int = 100,
        max_connections_per_host: int = 30,
        timeout: int = 30,
        keepalive_timeout: int = 30
    ):
        self.max_connections = max_connections
        self.max_connections_per_host = max_connections_per_host
        self.timeout = timeout
        self.keepalive_timeout = keepalive_timeout
        self._session: Optional[ClientSession] = None
        self._lock = asyncio.Lock()
    
    async def get_session(self) -> ClientSession:
        """Get or create aiohttp session with connection pooling."""
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    connector = TCPConnector(
                        limit=self.max_connections,
                        limit_per_host=self.max_connections_per_host,
                        keepalive_timeout=self.keepalive_timeout,
                        force_close=False,
                        enable_cleanup_closed=True
                    )
                    
                    timeout_config = aiohttp.ClientTimeout(total=self.timeout)
                    
                    self._session = ClientSession(
                        connector=connector,
                        timeout=timeout_config,
                        headers={
                            'User-Agent': 'StockAgent/1.0',
                            'Accept': 'application/json'
                        }
                    )
                    
                    logger.info(
                        "Created new HTTP session",
                        max_connections=self.max_connections,
                        max_per_host=self.max_connections_per_host
                    )
        
        return self._session
    
    async def close(self):
        """Close the session and cleanup connections."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("Closed HTTP session")
    
    @asynccontextmanager
    async def request(self, method: str, url: str, **kwargs):
        """Make an HTTP request with the pooled session."""
        session = await self.get_session()
        
        start_time = time.time()
        try:
            async with session.request(method, url, **kwargs) as response:
                duration = time.time() - start_time
                
                metrics.record_tool_execution(
                    tool_name="http_request",
                    status="success",
                    duration=duration
                )
                
                yield response
                
        except Exception as e:
            duration = time.time() - start_time
            
            metrics.record_tool_execution(
                tool_name="http_request",
                status="error",
                duration=duration
            )
            
            logger.error(f"HTTP request failed: {e}", url=url, method=method)
            raise


class BatchProcessor(Generic[T]):
    """Generic batch processor for efficient bulk operations."""
    
    def __init__(
        self,
        batch_size: int = 50,
        max_wait_time: float = 1.0,
        processor_func: Callable[[List[T]], Any] = None
    ):
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.processor_func = processor_func
        
        self._queue: Queue[T] = Queue()
        self._results: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread = None
    
    def start(self):
        """Start the batch processor worker thread."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._worker_thread = threading.Thread(target=self._worker, daemon=True)
            self._worker_thread.start()
            logger.info("Started batch processor")
    
    def stop(self):
        """Stop the batch processor."""
        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("Stopped batch processor")
    
    def add_item(self, item: T, item_id: str = None) -> str:
        """Add an item to the batch queue."""
        if item_id is None:
            item_id = str(time.time())
        
        self._queue.put((item_id, item))
        return item_id
    
    def get_result(self, item_id: str, timeout: float = 10.0) -> Any:
        """Get the result for a specific item."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self._lock:
                if item_id in self._results:
                    return self._results.pop(item_id)
            
            time.sleep(0.1)
        
        raise TimeoutError(f"Result not available for item {item_id}")
    
    def _worker(self):
        """Worker thread that processes batches."""
        batch = []
        batch_ids = []
        last_process_time = time.time()
        
        while not self._stop_event.is_set():
            try:
                # Try to get an item with timeout
                item_id, item = self._queue.get(timeout=0.1)
                batch.append(item)
                batch_ids.append(item_id)
                
                # Process batch if it's full or timeout reached
                should_process = (
                    len(batch) >= self.batch_size or
                    (time.time() - last_process_time) >= self.max_wait_time
                )
                
                if should_process and batch:
                    self._process_batch(batch, batch_ids)
                    batch = []
                    batch_ids = []
                    last_process_time = time.time()
                    
            except Empty:
                # Process any remaining items if timeout reached
                if batch and (time.time() - last_process_time) >= self.max_wait_time:
                    self._process_batch(batch, batch_ids)
                    batch = []
                    batch_ids = []
                    last_process_time = time.time()
    
    def _process_batch(self, batch: List[T], batch_ids: List[str]):
        """Process a batch of items."""
        try:
            start_time = time.time()
            
            if self.processor_func:
                results = self.processor_func(batch)
                
                # Store results
                with self._lock:
                    for i, item_id in enumerate(batch_ids):
                        if isinstance(results, list) and i < len(results):
                            self._results[item_id] = results[i]
                        else:
                            self._results[item_id] = results
            
            duration = time.time() - start_time
            logger.info(
                f"Processed batch of {len(batch)} items",
                duration=duration
            )
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            
            # Store error for all items
            with self._lock:
                for item_id in batch_ids:
                    self._results[item_id] = {"error": str(e)}


class DataFrameOptimizer:
    """Optimize pandas DataFrame operations for performance."""
    
    @staticmethod
    def optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
        """Optimize DataFrame data types to reduce memory usage."""
        optimized_df = df.copy()
        
        # Optimize numeric columns
        for col in optimized_df.select_dtypes(include=['int']).columns:
            optimized_df[col] = pd.to_numeric(optimized_df[col], downcast='integer')
        
        for col in optimized_df.select_dtypes(include=['float']).columns:
            optimized_df[col] = pd.to_numeric(optimized_df[col], downcast='float')
        
        # Convert object columns to category if appropriate
        for col in optimized_df.select_dtypes(include=['object']).columns:
            num_unique_values = len(optimized_df[col].unique())
            num_total_values = len(optimized_df[col])
            
            if num_unique_values / num_total_values < 0.5:
                optimized_df[col] = optimized_df[col].astype('category')
        
        # Log memory reduction
        original_memory = df.memory_usage(deep=True).sum()
        optimized_memory = optimized_df.memory_usage(deep=True).sum()
        reduction_pct = (1 - optimized_memory / original_memory) * 100
        
        logger.info(
            f"DataFrame memory optimized: {reduction_pct:.1f}% reduction",
            original_mb=original_memory / 1024 / 1024,
            optimized_mb=optimized_memory / 1024 / 1024
        )
        
        return optimized_df
    
    @staticmethod
    def chunk_dataframe(df: pd.DataFrame, chunk_size: int = 10000) -> List[pd.DataFrame]:
        """Split DataFrame into chunks for processing."""
        return [df[i:i+chunk_size] for i in range(0, len(df), chunk_size)]
    
    @staticmethod
    def parallel_apply(
        df: pd.DataFrame,
        func: Callable,
        axis: int = 1,
        n_workers: int = 4
    ) -> pd.Series:
        """Apply function to DataFrame in parallel."""
        chunks = DataFrameOptimizer.chunk_dataframe(df, len(df) // n_workers)
        
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            results = list(executor.map(lambda chunk: chunk.apply(func, axis=axis), chunks))
        
        return pd.concat(results)


class ComputationCache:
    """Cache for expensive computations with TTL and size limits."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key in self._cache:
                # Check if expired
                if time.time() - self._cache[key]['timestamp'] > self.ttl_seconds:
                    del self._cache[key]
                    del self._access_times[key]
                    return None
                
                # Update access time
                self._access_times[key] = time.time()
                return self._cache[key]['value']
        
        return None
    
    def set(self, key: str, value: Any):
        """Set value in cache."""
        with self._lock:
            # Evict least recently used if at capacity
            if len(self._cache) >= self.max_size:
                lru_key = min(self._access_times, key=self._access_times.get)
                del self._cache[lru_key]
                del self._access_times[lru_key]
            
            self._cache[key] = {
                'value': value,
                'timestamp': time.time()
            }
            self._access_times[key] = time.time()
    
    def clear(self):
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()


# Performance decorators
def memoize(ttl_seconds: int = 300):
    """Memoize function results with TTL."""
    cache = ComputationCache(ttl_seconds=ttl_seconds)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Compute and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            
            return result
        
        return wrapper
    
    return decorator


def profile_performance(func):
    """Profile function performance and log metrics."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = 0  # Would use psutil.Process().memory_info().rss in production
        
        try:
            result = await func(*args, **kwargs)
            
            duration = time.time() - start_time
            
            logger.info(
                f"Performance profile for {func.__name__}",
                duration_seconds=duration,
                args_count=len(args),
                kwargs_count=len(kwargs)
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                f"Function {func.__name__} failed",
                duration_seconds=duration,
                error=str(e)
            )
            
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            
            duration = time.time() - start_time
            
            logger.info(
                f"Performance profile for {func.__name__}",
                duration_seconds=duration
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                f"Function {func.__name__} failed",
                duration_seconds=duration,
                error=str(e)
            )
            
            raise
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


# Global instances
connection_pool = ConnectionPool()
computation_cache = ComputationCache()


# Utility functions
async def fetch_multiple_urls(
    urls: List[str],
    max_concurrent: int = 10
) -> List[Dict[str, Any]]:
    """Fetch multiple URLs concurrently with rate limiting."""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_with_semaphore(url: str) -> Dict[str, Any]:
        async with semaphore:
            try:
                async with connection_pool.request('GET', url) as response:
                    return {
                        'url': url,
                        'status': response.status,
                        'data': await response.json() if response.status == 200 else None,
                        'error': None
                    }
            except Exception as e:
                return {
                    'url': url,
                    'status': None,
                    'data': None,
                    'error': str(e)
                }
    
    tasks = [fetch_with_semaphore(url) for url in urls]
    return await asyncio.gather(*tasks)


def optimize_numpy_operations(arr: np.ndarray) -> np.ndarray:
    """Optimize numpy array operations."""
    # Use in-place operations when possible
    if arr.flags['WRITEABLE']:
        # Example: normalize in-place
        arr -= arr.mean()
        arr /= arr.std()
        return arr
    else:
        # Create optimized copy
        optimized = np.empty_like(arr)
        np.subtract(arr, arr.mean(), out=optimized)
        np.divide(optimized, arr.std(), out=optimized)
        return optimized 