"""
Basic tests for peewee-mssql package structure.
"""
import pytest
from unittest.mock import MagicMock, patch


def test_imports():
    """Test that all modules can be imported."""
    from peewee_mssql import MssqlDatabase, PooledMssqlDatabase, AsyncMssqlDatabase
    from peewee_mssql.database import MssqlDatabase
    from peewee_mssql.pool import PooledMssqlDatabase
    from peewee_mssql.asyncio import AsyncMssqlDatabase
    from peewee_mssql.compiler import mssql_apply_ordering


def test_version():
    """Test version is defined."""
    from peewee_mssql import __version__
    assert __version__ == '1.0.0'


def test_database_field_types():
    """Test MSSQL field type mappings."""
    from peewee_mssql import MssqlDatabase
    
    db = MssqlDatabase('test_db', autoconnect=False)
    
    assert db.field_types['BOOL'] == 'tinyint'
    assert db.field_types['STRING'] == 'nvarchar'
    assert db.field_types['TEXT'] == 'nvarchar(max)'
    assert db.field_types['DATETIME'] == 'datetime2'


def test_database_operations():
    """Test MSSQL operation mappings."""
    from peewee_mssql import MssqlDatabase
    
    db = MssqlDatabase('test_db', autoconnect=False)
    
    from peewee import OP
    assert db.operations.get('LIKE') == 'LIKE BINARY'
    assert db.operations.get('ILIKE') == 'LIKE'


def test_database_params():
    """Test MSSQL parameter style."""
    from peewee_mssql import MssqlDatabase
    
    db = MssqlDatabase('test_db', autoconnect=False)
    
    assert db.param == '%s'
    assert db.quote == '""'


@patch('pymssql.connect')
def test_database_connect(mock_connect):
    """Test database connection with mocked pymssql."""
    from peewee_mssql import MssqlDatabase
    
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    
    db = MssqlDatabase('test_db', server='localhost', autoconnect=False)
    
    # Note: _connect is called internally by connect()
    # We're just testing the configuration is correct
    assert db.database == 'test_db'
    assert db.connect_params.get('server') == 'localhost'


def test_pooled_database_init():
    """Test pooled database initialization."""
    from peewee_mssql import PooledMssqlDatabase
    
    db = PooledMssqlDatabase(
        'test_db',
        server='localhost',
        max_connections=10,
        stale_timeout=300,
        timeout=30,
        autoconnect=False
    )
    
    assert db._max_connections == 10
    assert db._stale_timeout == 300
    assert db._wait_timeout == 30


def test_async_database_init():
    """Test async database initialization."""
    from peewee_mssql import AsyncMssqlDatabase
    
    db = AsyncMssqlDatabase(
        'test_db',
        server='localhost',
        pool_size=5,
        pool_min_size=1,
        autoconnect=False
    )
    
    assert db._pool_size == 5
    assert db._pool_min_size == 1


def test_legacy_datetime():
    """Test legacy datetime option."""
    from peewee_mssql import MssqlDatabase
    
    db = MssqlDatabase('test_db', use_legacy_datetime=True, autoconnect=False)
    
    assert db.field_types['DATETIME'] == 'datetime'
    assert db.field_types['DATE'] == 'nvarchar(15)'
    assert db.field_types['TIME'] == 'nvarchar(10)'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
