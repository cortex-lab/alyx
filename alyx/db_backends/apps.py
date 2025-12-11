"""
App configuration for the db_backends package.
Registers Prometheus metrics collectors.
"""
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class DBBackendsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'db_backends'
    
    def ready(self):
        """
        Initialize the application.
        Register Prometheus collector for connection pool metrics.
        """
        try:
            from db_backends.postgresql_pool.prometheus_collector import pool_collector
            pool_collector.register()
            logger.info("Database connection pool metrics registered with Prometheus")
        except Exception as e:
            logger.warning(f"Could not register connection pool metrics: {e}")
