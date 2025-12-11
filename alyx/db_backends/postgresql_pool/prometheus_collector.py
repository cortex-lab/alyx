"""
Prometheus metrics collector for psycopg_pool connection pools.

This module provides Prometheus metrics for monitoring PostgreSQL connection pools
in Django applications using psycopg_pool.
"""

from prometheus_client import Gauge
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY
import logging

logger = logging.getLogger(__name__)


class ConnectionPoolCollector:
    """
    Prometheus collector for psycopg_pool connection pool metrics.
    
    Exposes the following metrics:
    - db_pool_size: Current number of connections in the pool
    - db_pool_available: Number of available connections
    - db_pool_waiting: Number of requests waiting for a connection
    - db_pool_min_size: Configured minimum pool size
    - db_pool_max_size: Configured maximum pool size
    """
    
    def __init__(self):
        self._pools = {}
        self._registered = False
    
    def register_pool(self, alias, pool):
        """Register a connection pool for monitoring."""
        self._pools[alias] = pool
        logger.info(f"Registered connection pool '{alias}' for Prometheus monitoring")
    
    def collect(self):
        """Collect metrics from all registered pools."""
        if not self._pools:
            return
        
        # Create metric families
        pool_size = GaugeMetricFamily(
            'django_db_pool_size',
            'Current number of connections in the pool',
            labels=['database']
        )
        
        pool_available = GaugeMetricFamily(
            'django_db_pool_available',
            'Number of available connections in the pool',
            labels=['database']
        )
        
        pool_waiting = GaugeMetricFamily(
            'django_db_pool_waiting',
            'Number of requests waiting for a connection',
            labels=['database']
        )
        
        pool_min_size = GaugeMetricFamily(
            'django_db_pool_min_size',
            'Configured minimum pool size',
            labels=['database']
        )
        
        pool_max_size = GaugeMetricFamily(
            'django_db_pool_max_size',
            'Configured maximum pool size',
            labels=['database']
        )
        
        # Collect metrics from each pool
        for alias, pool in self._pools.items():
            try:
                # Get pool statistics
                stats = pool.get_stats()
                
                # Add metrics
                pool_size.add_metric([alias], stats.get('pool_size', 0))
                pool_available.add_metric([alias], stats.get('pool_available', 0))
                pool_waiting.add_metric([alias], stats.get('requests_waiting', 0))
                pool_min_size.add_metric([alias], pool.min_size)
                pool_max_size.add_metric([alias], pool.max_size)
                
            except Exception as e:
                logger.error(f"Error collecting metrics for pool '{alias}': {e}")
                continue
        
        # Yield all metrics
        yield pool_size
        yield pool_available
        yield pool_waiting
        yield pool_min_size
        yield pool_max_size
    
    def register(self):
        """Register this collector with Prometheus."""
        if not self._registered:
            try:
                REGISTRY.register(self)
                self._registered = True
                logger.info("ConnectionPoolCollector registered with Prometheus")
            except Exception as e:
                logger.warning(f"Failed to register ConnectionPoolCollector: {e}")


# Global collector instance
pool_collector = ConnectionPoolCollector()
