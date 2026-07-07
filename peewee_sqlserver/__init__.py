"""
peewee-sqlserver: Microsoft SQL Server adapter for Peewee ORM.

Provides both synchronous and async database access for SQL Server
using pymssql (sync), pyodbc (sync), and aioodbc (async) drivers.

Modules:
    - database: Core database classes (MssqlDatabase, MssqlPyodbcDatabase)
    - fields: MSSQL-specific fields (JsonField, XmlField, ComputedField)
    - merge: MERGE statement for upserts
    - sequences: SEQUENCE support
    - migrate: Schema migration operations
    - fulltext: Full-text search (CONTAINS, FREETEXT)
    - locking: FOR UPDATE with table hints
    - asyncio: Async database support
    - pool: Connection pooling

Example:
    from peewee_sqlserver import MssqlDatabase, JsonField, merge

    db = MssqlDatabase('my_database', server='localhost')

    class User(db.Model):
        username = CharField()
        data = JsonField()

    # Upsert using MERGE
    merge(
        target=User,
        source=staging_table,
        on=User.id == staging_table.id,
        update={User.name: staging_table.name},
        insert={User.id: staging_table.id, User.name: staging_table.name}
    ).execute()
"""

# Core database classes
from .database import (
    MssqlDatabase,
    MssqlPyodbcDatabase,
    TableHint,
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

# Connection pooling
from .pool import PooledMssqlDatabase

# Async support
from .asyncio import AsyncMssqlDatabase

# Fields
from .fields import (
    JsonField,
    XmlField,
    ComputedField,
)

# MERGE/Upsert
from .merge import (
    Merge,
    merge,
    UpsertQuery,
)

# Sequences
from .sequences import (
    Sequence,
    next_value,
    create_sequence,
    drop_sequence,
    AutoSequence,
)

# Migrations
from .migrate import (
    MSSQLMigrator,
    migrate,
    AddColumn,
    DropColumn,
    RenameColumn,
    AlterColumn,
    AddNotNull,
    DropNotNull,
    AddIndex,
    DropIndex,
    RenameTable,
    CreateTable,
    DropTable,
    AddConstraint,
    DropConstraint,
)

# Full-text search
from .fulltext import (
    FullTextSearch,
    FullTextIndex,
    contains,
    freetext,
    contains_table,
    freetext_table,
)

# Locking
from .locking import (
    ForUpdate,
    with_nolock,
    with_holdlock,
    with_updlock,
    with_readpast,
    with_xlock,
    with_tablock,
)

__version__ = '1.0.0'

__all__ = [
    # Database classes
    'MssqlDatabase',
    'MssqlPyodbcDatabase',
    'PooledMssqlDatabase',
    'AsyncMssqlDatabase',
    
    # Table hints
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
    
    # Fields
    'JsonField',
    'XmlField',
    'ComputedField',
    
    # MERGE/Upsert
    'Merge',
    'merge',
    'UpsertQuery',
    
    # Sequences
    'Sequence',
    'next_value',
    'create_sequence',
    'drop_sequence',
    'AutoSequence',
    
    # Migrations
    'MSSQLMigrator',
    'migrate',
    'AddColumn',
    'DropColumn',
    'RenameColumn',
    'AlterColumn',
    'AddNotNull',
    'DropNotNull',
    'AddIndex',
    'DropIndex',
    'RenameTable',
    'CreateTable',
    'DropTable',
    'AddConstraint',
    'DropConstraint',
    
    # Full-text search
    'FullTextSearch',
    'FullTextIndex',
    'contains',
    'freetext',
    'contains_table',
    'freetext_table',
    
    # Locking
    'ForUpdate',
    'with_nolock',
    'with_holdlock',
    'with_updlock',
    'with_readpast',
    'with_xlock',
    'with_tablock',
]
