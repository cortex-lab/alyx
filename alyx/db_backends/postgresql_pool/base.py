"""
Custom PostgreSQL database backend with psycopg_pool connection pooling.

This backend wraps Django's standard postgresql backend to use psycopg_pool
for connection pooling instead of Django's CONN_MAX_AGE.
"""
import threading
import logging
from django.db.backends.postgresql import base
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

# Global pool instance - one per database configuration
_pool_lock = threading.Lock()
_pools = {}


def get_pool(alias, conninfo, pool_kwargs):
    """Get or create a connection pool for the given database alias."""
    if alias not in _pools:
        with _pool_lock:
            if alias not in _pools:
                _pools[alias] = ConnectionPool(
                    conninfo=conninfo,
                    **pool_kwargs
                )
                # Register pool with Prometheus collector if available
                try:
                    from .prometheus_collector import pool_collector
                    pool_collector.register_pool(alias, _pools[alias])
                except ImportError:
                    logger.debug("Prometheus collector not available for connection pool")
    return _pools[alias]


class DatabaseWrapper(base.DatabaseWrapper):
    """PostgreSQL database wrapper with connection pooling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pool = None
    
    def get_new_connection(self, conn_params):
        """Get a connection from the pool instead of creating a new one."""
        # Initialize pool if needed
        if self._pool is None:
            pool_config = self.settings_dict.get('OPTIONS', {}).get('pool', {})
            
            # Build conninfo string from connection parameters
            conninfo_parts = []
            if 'dbname' in conn_params:
                conninfo_parts.append(f"dbname={conn_params['dbname']}")
            if 'user' in conn_params:
                conninfo_parts.append(f"user={conn_params['user']}")
            if 'password' in conn_params:
                conninfo_parts.append(f"password={conn_params['password']}")
            if 'host' in conn_params:
                conninfo_parts.append(f"host={conn_params['host']}")
            if 'port' in conn_params:
                conninfo_parts.append(f"port={conn_params['port']}")
            
            conninfo = ' '.join(conninfo_parts)
            
            # Get pool with configuration
            pool_kwargs = {
                'min_size': pool_config.get('min_size', 2),
                'max_size': pool_config.get('max_size', 10),
                'timeout': pool_config.get('timeout', 30),
                'max_idle': pool_config.get('max_idle', 600),
                'max_lifetime': pool_config.get('max_lifetime', 3600),
            }
            
            self._pool = get_pool(self.alias, conninfo, pool_kwargs)
        
        # Get connection from pool
        return self._pool.getconn()
    
    def close(self):
        """Override close to handle pool connection return."""
        if self.connection is not None and self._pool is not None:
            try:
                self._pool.putconn(self.connection)
            except Exception as e:
                logger.warning(f"Error returning connection to pool: {e}")
        self.connection = None
        self.closed_in_transaction = False
        self.needs_rollback = False
