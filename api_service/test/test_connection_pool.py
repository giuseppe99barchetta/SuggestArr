import unittest
from api_service.db.database_manager import DatabaseManager
import time


class TestConnectionPool(unittest.TestCase):
    """Test database connection pooling functionality."""
    
    def setUp(self):
        """Set up test database manager."""
        # Use in-memory SQLite for testing
        import os
        
        # Clear any existing pool state - no longer needed
        
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
        pass  # No cleanup needed for direct connections
    
    def test_pool_initialization(self):
        """Test that database manager initializes correctly."""
        self.assertIsNotNone(self.db_manager.db_type)
        self.assertEqual(self.db_manager.db_type, 'sqlite')
        
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
        
        # Get multiple connections
        for i in range(3):
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                self.assertEqual(result[0], 1)
    
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
        """Test that database manager works correctly."""
        # Get pool stats from database manager
        stats = self.db_manager.get_pool_stats()
        self.assertIsInstance(stats, dict)
        
        # Verify status
        self.assertEqual(stats['status'], 'direct_connection')
    
    def cleanup_tests(self):
        """Clean up after tests."""
        if hasattr(self, 'db_manager'):
            try:
                self.db_manager.pool.close_all()
            except Exception:
                pass  # Ignore cleanup errors


if __name__ == '__main__':
    unittest.main()