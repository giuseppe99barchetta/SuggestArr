import unittest
from api_service.db.database_manager import DatabaseManager
from api_service.db.connection_pool import pool_manager, PoolConfig
import time


class TestConnectionPool(unittest.TestCase):
    """Test database connection pooling functionality."""
    
    def setUp(self):
        """Set up test database manager."""
        # Use in-memory SQLite for testing
        import os
        
        # Clear any existing pool state
        pool_manager.close_all_pools()
        
        # Set test environment variables
        os.environ['DB_TYPE'] = 'sqlite'
        os.environ.pop('DB_HOST', None)
        os.environ.pop('DB_PORT', None)
        os.environ.pop('DB_USER', None)
        os.environ.pop('DB_PASSWORD', None)
        os.environ.pop('DB_NAME', None)
        
        self.db_manager = DatabaseManager()
    
    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'db_manager'):
            try:
                self.db_manager.pool.close_all()
            except Exception:
                pass  # Ignore cleanup errors
    
    def test_pool_initialization(self):
        """Test that connection pool initializes correctly."""
        self.assertIsNotNone(self.db_manager.pool)
        self.assertEqual(self.db_manager.pool.db_type, 'sqlite')
        
    def test_basic_database_operation(self):
        """Test basic database operations with pooling."""
        # Initialize database
        self.db_manager.initialize_db()
        
        # Test connection context manager
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
    
    def test_pool_statistics(self):
        """Test that pool statistics are tracked."""
        stats = self.db_manager.get_pool_stats()
        
        # Verify required statistics fields
        required_fields = ['created', 'reused', 'expired', 'errors', 'active_connections']
        for field in required_fields:
            self.assertIn(field, stats)
    
    def test_multiple_connections(self):
        """Test that multiple connections can be obtained."""
        self.db_manager.initialize_db()
        
        connections = []
        try:
            # Get multiple connections
            for i in range(3):
                conn = self.db_manager.pool.get_connection()
                with conn as c:
                    cursor = c.cursor()
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    self.assertEqual(result[0], 1)
                    connections.append(i)
                    
        finally:
            # Clean up
            self.db_manager.pool.close_all()
    
    def test_connection_validation(self):
        """Test that connection validation works."""
        self.db_manager.initialize_db()
        
        # Get a connection and verify it works
        with self.db_manager.get_connection() as conn:
            self.assertIsNotNone(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
    
    def test_global_pool_manager(self):
        """Test that global pool manager works correctly."""
        # Get pool stats from global manager
        all_stats = pool_manager.get_all_stats()
        self.assertIsInstance(all_stats, dict)
        
        # Verify our database's pool is in the global manager
        self.assertTrue(len(all_stats) > 0)
    
    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'db_manager'):
            try:
                self.db_manager.pool.close_all()
            except Exception:
                pass  # Ignore cleanup errors


if __name__ == '__main__':
    unittest.main()