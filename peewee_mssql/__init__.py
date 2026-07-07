"""
peewee-mssql: Microsoft SQL Server adapter for Peewee ORM.

Provides both synchronous and async database access for SQL Server
using pymssql (sync) and aioodbc (async) drivers.

Usage:
    from peewee_mssql import MssqlDatabase

    db = MssqlDatabase('my_database', server='localhost')

    # Or with connection pooling:
    from peewee_mssql import PooledMssqlDatabase
    db = PooledMssqlDatabase('my_database', server='localhost')

    # For async:
    from peewee_mssql import AsyncMssqlDatabase
    db = AsyncMssqlDatabase('my_database', server='localhost')

    # With NOLOCK hint:
    query = MyModel.select().nolock()
    
    # Or with custom hints:
    from peewee_mssql import MSSQL_NOLOCK, MSSQL_UPDLOCK
    query = MyModel.select().hint(MSSQL_NOLOCK, MSSQL_UPDLOCK)
"""

from .database import MssqlDatabase, MssqlPyodbcDatabase, TableHint
from .pool import PooledMssqlDatabase
from .asyncio import AsyncMssqlDatabase
from .compiler import (
    MSSQL_NOLOCK,
    MSSQL_UPDLOCK,
    MSSQL_HOLDLOCK,
    MSSQL_READPAST,
    MSSQL_XLOCK,
    MSSQL_PAGLOCK,
    MSSQL_TABLOCK,
    MSSQL_TABLOCKX,
    MSSQL_READUNCOMMITTED,
    MSSQL_READCOMMITTED,
    MSSQL_REPEATABLEREAD,
    MSSQL_SERIALIZABLE,
    MSSQL_NOEXPAND,
    MSSQL_NOLOCK_UPDLOCK,
    MSSQL_HOLDLOCK_READPAST,
)

__version__ = '1.0.0'

__all__ = [
    'MssqlDatabase',
    'MssqlPyodbcDatabase',
    'PooledMssqlDatabase',
    'AsyncMssqlDatabase',
    'TableHint',
    'MSSQL_NOLOCK',
    'MSSQL_UPDLOCK',
    'MSSQL_HOLDLOCK',
    'MSSQL_READPAST',
    'MSSQL_XLOCK',
    'MSSQL_PAGLOCK',
    'MSSQL_TABLOCK',
    'MSSQL_TABLOCKX',
    'MSSQL_READUNCOMMITTED',
    'MSSQL_READCOMMITTED',
    'MSSQL_REPEATABLEREAD',
    'MSSQL_SERIALIZABLE',
    'MSSQL_NOEXPAND',
    'MSSQL_NOLOCK_UPDLOCK',
    'MSSQL_HOLDLOCK_READPAST',
]
