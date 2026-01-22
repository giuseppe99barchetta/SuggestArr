"""
Tests for the new database adapter system.
"""
import unittest
import tempfile
import os

from api_service.db.adapters.sqlite_adapter import SQLiteAdapter
from api_service.db.adapter_factory import DatabaseAdapterFactory


class TestDatabaseAdapters(unittest.TestCase):
    """Test database adapters."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.test_config = {
            'db_path': self.temp_db.name
        }
    
    def tearDown(self):
        """Clean up test database."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_sqlite_adapter_creation(self):
        """Test SQLite adapter creation and connection."""
        adapter = SQLiteAdapter(self.test_config)
        
        # Should not be connected initially
        self.assertIsNone(adapter.connection)
        
        # Connect should work
        adapter.connect()
        self.assertIsNotNone(adapter.connection)
        
        # Disconnect should work
        adapter.disconnect()
        self.assertIsNone(adapter.connection)
    
    def test_sqlite_adapter_initialization(self):
        """Test SQLite adapter database initialization."""
        adapter = SQLiteAdapter(self.test_config)
        adapter.initialize_db()
        
        # Check if requests table exists
        result = adapter.fetch_all("SELECT name FROM sqlite_master WHERE type='table' AND name='requests'")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'requests')
    
    def test_sqlite_adapter_crud_operations(self):
        """Test SQLite adapter CRUD operations."""
        adapter = SQLiteAdapter(self.test_config)
        adapter.initialize_db()
        
        # Create a request
        insert_query = '''
        INSERT INTO requests (user_id, media_type, media_title, media_id)
        VALUES (?, ?, ?, ?)
        '''
        request_id = adapter.execute_query(insert_query, ('test_user', 'movie', 'Test Movie', '123'))
        self.assertIsNotNone(request_id)
        
        # Read the request
        request = adapter.fetch_one('SELECT * FROM requests WHERE id = ?', (request_id,))
        self.assertIsNotNone(request)
        self.assertEqual(request['user_id'], 'test_user')
        self.assertEqual(request['media_type'], 'movie')
        
        # Update the request
        adapter.execute_query('UPDATE requests SET request_status = ? WHERE id = ?', ('approved', request_id))
        updated_request = adapter.fetch_one('SELECT * FROM requests WHERE id = ?', (request_id,))
        self.assertEqual(updated_request['request_status'], 'approved')
        
        # Delete the request
        adapter.execute_query('DELETE FROM requests WHERE id = ?', (request_id,))
        deleted_request = adapter.fetch_one('SELECT * FROM requests WHERE id = ?', (request_id,))
        self.assertIsNone(deleted_request)
    
    def test_adapter_factory_sqlite(self):
        """Test adapter factory creates SQLite adapter correctly."""
        adapter = DatabaseAdapterFactory.create_adapter({
            'db_type': 'sqlite',
            'db_path': self.temp_db.name
        })
        
        self.assertIsInstance(adapter, SQLiteAdapter)
    
    def test_adapter_factory_env_config(self):
        """Test adapter factory loads from environment configuration."""
        adapter = DatabaseAdapterFactory.create_adapter()
        
        # Should create SQLite adapter by default
        self.assertIsInstance(adapter, SQLiteAdapter)


if __name__ == '__main__':
    unittest.main()