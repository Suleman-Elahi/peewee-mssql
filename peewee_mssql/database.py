from peewee import Database, ImproperlyConfigured, OP, SQL, CommaNodeList
from peewee import (
    ColumnMetadata,
    IndexMetadata,
    ForeignKeyMetadata,
    Node,
    Entity,
    Value,
)
from peewee import __exception_wrapper__

from .compiler import mssql_apply_ordering, mssql_select_sql


class TableHint(Node):
    """
    Represents a SQL Server table hint like NOLOCK, UPDLOCK, etc.
    
    Usage:
        from peewee_mssql import TableHint, MSSQL_NOLOCK
        
        # Query with NOLOCK hint
        query = (MyModel
                 .select()
                 .where(MyModel.id > 10)
                 .nolock())  # Adds WITH (NOLOCK)
        
        # Or manually:
        query = (MyModel
                 .select()
                 .where(MyModel.id > 10)
                 .hint(MSSQL_NOLOCK))
    """
    
    def __init__(self, *hints):
        self.hints = hints
    
    def __sql__(self, ctx):
        ctx.literal(' WITH (')
        for i, hint in enumerate(self.hints):
            if i > 0:
                ctx.literal(', ')
            ctx.literal(hint)
        ctx.literal(')')
        return ctx


# Common table hints
MSSQL_NOLOCK = 'NOLOCK'
MSSQL_UPDLOCK = 'UPDLOCK'
MSSQL_HOLDLOCK = 'HOLDLOCK'
MSSQL_READPAST = 'READPAST'
MSSQL_XLOCK = 'XLOCK'
MSSQL_PAGLOCK = 'PAGLOCK'
MSSQL_TABLOCK = 'TABLOCK'
MSSQL_TABLOCKX = 'TABLOCKX'
MSSQL_READUNCOMMITTED = 'READUNCOMMITTED'
MSSQL_READCOMMITTED = 'READCOMMITTED'
MSSQL_REPEATABLEREAD = 'REPEATABLEREAD'
MSSQL_SERIALIZABLE = 'SERIALIZABLE'
MSSQL_NOEXPAND = 'NOEXPAND'

# Common hint combinations
MSSQL_NOLOCK_UPDLOCK = (MSSQL_NOLOCK, MSSQL_UPDLOCK)
MSSQL_HOLDLOCK_READPAST = (MSSQL_HOLDLOCK, MSSQL_READPAST)

try:
    import pymssql
except ImportError:
    pymssql = None

try:
    import pyodbc
except ImportError:
    pyodbc = None

__all__ = ['MssqlDatabase', 'MssqlPyodbcDatabase']


class MssqlDatabase(Database):
    """
    Peewee database adapter for Microsoft SQL Server.
    
    Uses pymssql as the database driver by default.
    For pyodbc, use MssqlPyodbcDatabase instead.
    """
    
    field_types = {
        'BOOL': 'tinyint',
        'DOUBLE': 'float(53)',
        'FLOAT': 'float',
        'INT': 'int',
        'STRING': 'nvarchar',
        'FIXED_CHAR': 'nchar',
        'TEXT': 'nvarchar(max)',
        'BLOB': 'varbinary',
        'UUID': 'nchar(40)',
        'PRIMARY_KEY': 'int identity',
        'DATETIME': 'datetime2',
        'DATE': 'date',
        'TIME': 'time',
        'BIGINTEGER': 'bigint',
        'SMALLINTEGER': 'smallint',
        'DECIMAL': 'decimal',
        'BIT': 'bit',
        # MSSQL-specific types
        'MONEY': 'money',
        'SMALLMONEY': 'smallmoney',
        'DATETIMEOFFSET': 'datetimeoffset',
        'SMALLDATETIME': 'smalldatetime',
        'REAL': 'real',
        'UNIQUEIDENTIFIER': 'uniqueidentifier',
        'XML': 'xml',
        'ROWVERSION': 'rowversion',
        'SQL_VARIANT': 'sql_variant',
        'HIERARCHYID': 'nvarchar(892)',
        'GEOGRAPHY': 'geography',
        'GEOMETRY': 'geometry',
        # Deprecated but legacy support
        'IMAGE': 'image',
        'NTEXT': 'ntext',
        'TEXT_DBL': 'text',
    }
    
    operations = {
        'LIKE': 'LIKE BINARY',
        'ILIKE': 'LIKE',
    }
    
    param = '%s'
    quote = '""'
    for_update = True
    limit_max = 2 ** 31 - 1
    
    # Override _apply_ordering on Select class for MSSQL TOP syntax
    _patched = False
    
    def __init__(self, database, **kwargs):
        self._use_legacy_datetime = kwargs.pop('use_legacy_datetime', False)
        super(MssqlDatabase, self).__init__(database, **kwargs)
        self._patch_select_ordering()
        self._patch_query_hints()
    
    def _patch_select_ordering(self):
        """
        Monkey-patch Select._apply_ordering to use MSSQL TOP syntax.
        This is done once per class, not per instance.
        """
        if MssqlDatabase._patched:
            return
        
        from peewee import Select
        Select._original_apply_ordering = Select._apply_ordering
        Select._apply_ordering = mssql_apply_ordering
        MssqlDatabase._patched = True
    
    def _patch_query_hints(self):
        """
        Add nolock() and hint() methods to Select and ModelSelect.
        """
        from peewee import Select
        
        if hasattr(Select, '_mssql_hints_patched'):
            return
        
        def _nolock(self):
            """Add WITH (NOLOCK) hint to query."""
            self._table_hints = TableHint(MSSQL_NOLOCK)
            return self
        
        def _hint(self, *hints):
            """Add custom table hints to query.
            
            Args:
                *hints: One or more hint strings (e.g., MSSQL_NOLOCK, MSSQL_UPDLOCK)
            
            Returns:
                Self for chaining
            """
            self._table_hints = TableHint(*hints)
            return self
        
        # Patch Select class
        Select.nolock = _nolock
        Select.hint = _hint
        Select._table_hints = None
        Select._mssql_hints_patched = True
        
        # Patch __sql__ to include table hints
        if not hasattr(Select, '_original_sql'):
            Select._original_sql = Select.__sql__
            Select.__sql__ = mssql_select_sql
        
        # Also patch ModelSelect if it exists
        try:
            from peewee import ModelSelect
            if not hasattr(ModelSelect, '_mssql_hints_patched'):
                ModelSelect.nolock = _nolock
                ModelSelect.hint = _hint
                ModelSelect._table_hints = None
                ModelSelect._mssql_hints_patched = True
        except ImportError:
            pass
    
    def init(self, database, **kwargs):
        super(MssqlDatabase, self).init(database, **kwargs)
        if self._use_legacy_datetime:
            self.field_types['DATETIME'] = 'datetime'
            self.field_types['DATE'] = 'nvarchar(15)'
            self.field_types['TIME'] = 'nvarchar(10)'
    
    def _connect(self):
        if pymssql is None:
            raise ImproperlyConfigured('pymssql must be installed')
        
        return pymssql.connect(
            database=self.database,
            autocommit=True,
            **self.connect_params
        )
    
    def _set_server_version(self, conn):
        """Extract SQL Server version from connection."""
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT @@VERSION')
            version_str = cursor.fetchone()[0]
            # Parse version like "Microsoft SQL Server 2019 (RTM-GDR)..."
            import re
            match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_str)
            if match:
                self.server_version = tuple(int(x) for x in match.groups())
            else:
                self.server_version = (0, 0, 0)
        except Exception:
            self.server_version = (0, 0, 0)
    
    def get_tables(self, schema=None):
        if schema:
            query = ('SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE '
                     'TABLE_SCHEMA = %s AND TABLE_TYPE = %s ORDER BY TABLE_NAME')
            cursor = self.execute_sql(query, (schema, 'BASE TABLE'))
        else:
            query = ('SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE '
                     'TABLE_TYPE = %s ORDER BY TABLE_NAME')
            cursor = self.execute_sql(query, ('BASE TABLE',))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_indexes(self, table, schema=None):
        query = '''
            SELECT
                i.name AS index_name,
                i.is_unique,
                i.is_primary_key,
                STRING_AGG(c.name, ',') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns
            FROM sys.indexes i
            INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            INNER JOIN sys.tables t ON i.object_id = t.object_id
            WHERE t.name = %s
            GROUP BY i.name, i.is_unique, i.is_primary_key
        '''
        params = (table,)
        if schema:
            query = query.replace(
                "WHERE t.name = %s",
                "WHERE t.name = %s AND SCHEMA_NAME(t.schema_id) = %s"
            )
            params = (table, schema)
        
        cursor = self.execute_sql(query, params)
        return [
            IndexMetadata(
                name=row[0],
                sql='',
                columns=row[3].split(',') if row[3] else [],
                unique=row[1],
                table=table
            )
            for row in cursor.fetchall()
        ]
    
    def get_columns(self, table, schema=None):
        query = '''
            SELECT
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.IS_NULLABLE,
                c.COLUMN_DEFAULT,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS is_pk
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                    AND tc.TABLE_SCHEMA = ku.TABLE_SCHEMA
                WHERE tc.TABLE_NAME = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ) pk ON c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE c.TABLE_NAME = %s
        '''
        params = (table, table)
        if schema:
            query = query.replace(
                "WHERE c.TABLE_NAME = %s",
                "WHERE c.TABLE_NAME = %s AND c.TABLE_SCHEMA = %s"
            )
            params = (table, table, schema)
        
        cursor = self.execute_sql(query, params)
        return [
            ColumnMetadata(
                name=row[0],
                data_type=row[1],
                null=row[2] == 'YES',
                table=table,
                default=row[3],
                is_pk=bool(row[4])
            )
            for row in cursor.fetchall()
        ]
    
    def get_primary_keys(self, table, schema=None):
        query = '''
            SELECT ku.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                AND tc.TABLE_SCHEMA = ku.TABLE_SCHEMA
            WHERE tc.TABLE_NAME = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ORDER BY ku.ORDINAL_POSITION
        '''
        params = (table,)
        if schema:
            query = query.replace(
                "WHERE tc.TABLE_NAME = %s",
                "WHERE tc.TABLE_NAME = %s AND tc.TABLE_SCHEMA = %s"
            )
            params = (table, schema)
        
        cursor = self.execute_sql(query, params)
        return [row[0] for row in cursor.fetchall()]
    
    def get_foreign_keys(self, table, schema=None):
        query = '''
            SELECT
                fk.name AS fk_name,
                cp.name AS from_column,
                OBJECT_NAME(fk.referenced_object_id) AS to_table,
                cr.name AS to_column
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc
                ON fk.object_id = fkc.constraint_object_id
            JOIN sys.columns cp
                ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
            JOIN sys.columns cr
                ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
            WHERE OBJECT_NAME(fk.parent_object_id) = %s
        '''
        params = (table,)
        if schema:
            query = query.replace(
                "WHERE OBJECT_NAME(fk.parent_object_id) = %s",
                "WHERE OBJECT_NAME(fk.parent_object_id) = %s AND SCHEMA_NAME(fk.schema_id) = %s"
            )
            params = (table, schema)
        
        cursor = self.execute_sql(query, params)
        return [
            ForeignKeyMetadata(
                name=row[0],
                src_table=table,
                src_column=row[1],
                dest_table=row[2],
                dest_column=row[3]
            )
            for row in cursor.fetchall()
        ]
    
    def sequence_exists(self, seq):
        query = '''
            SELECT 1 FROM sys.sequences WHERE name = %s
        '''
        cursor = self.execute_sql(query, (seq,))
        return cursor.fetchone() is not None
    
    def conflict_statement(self, on_conflict, query):
        raise NotImplementedError(
            'MSSQL does not support ON CONFLICT. Use MERGE for upserts.'
        )
    
    def conflict_update(self, on_conflict, query):
        raise NotImplementedError(
            'MSSQL does not support ON CONFLICT. Use MERGE for upserts.'
        )
    
    def extract_date(self, date_part, date_field):
        return SQL('DATEPART(%s, %s)' % (date_part, date_field))
    
    def truncate_date(self, date_part, date_field):
        return SQL('DATEADD(%s, DATEDIFF(%s, 0, %s), 0)' % (
            date_part, date_part, date_field))
    
    def truncate_table(self, model, reset_seq=True):
        """
        Truncate table with optional sequence reset.
        """
        if reset_seq:
            return SQL('TRUNCATE TABLE %s' % model._meta.table.__sql__())
        else:
            return SQL('TRUNCATE TABLE %s' % model._meta.table.__sql__())


class MssqlPyodbcDatabase(MssqlDatabase):
    """
    Peewee database adapter for Microsoft SQL Server using pyodbc.
    
    pyodbc is more commonly used and better maintained than pymssql.
    It requires the Microsoft ODBC Driver for SQL Server.
    
    Usage:
        from peewee_mssql import MssqlPyodbcDatabase
        
        # With connection string
        db = MssqlPyodbcDatabase(
            'my_database',
            driver='ODBC Driver 18 for SQL Server',
            server='localhost',
            trusted_connection='yes'
        )
        
        # Or with explicit connection string
        db = MssqlPyodbcDatabase(
            connection_string='DRIVER={ODBC Driver 18 for SQL Server};'
                              'SERVER=localhost;DATABASE=my_database;'
                              'Trusted_Connection=yes'
        )
    """
    
    def __init__(self, database, **kwargs):
        self._connection_string = kwargs.pop('connection_string', None)
        self._driver = kwargs.pop('driver', 'ODBC Driver 18 for SQL Server')
        super(MssqlPyodbcDatabase, self).__init__(database, **kwargs)
    
    def _connect(self):
        if pyodbc is None:
            raise ImproperlyConfigured(
                'pyodbc must be installed. '
                'Install with: pip install pyodbc'
            )
        
        if self._connection_string:
            # Use provided connection string directly
            conn_str = self._connection_string
        else:
            # Build connection string from parameters
            parts = [f'DRIVER={{{self._driver}}}']
            
            if self.database:
                parts.append(f'DATABASE={self.database}')
            
            # Map common parameter names
            param_mapping = {
                'server': 'SERVER',
                'host': 'SERVER',
                'user': 'UID',
                'uid': 'UID',
                'password': 'PWD',
                'pwd': 'PWD',
                'trusted_connection': 'Trusted_Connection',
                'trustservercertificate': 'TrustServerCertificate',
                'encrypt': 'Encrypt',
                'connection_timeout': 'Connection Timeout',
                'query_timeout': 'Query Timeout',
            }
            
            for key, value in self.connect_params.items():
                odbc_key = param_mapping.get(key.lower(), key)
                if isinstance(value, bool):
                    value = 'yes' if value else 'no'
                parts.append(f'{odbc_key}={value}')
            
            conn_str = ';'.join(parts)
        
        conn = pyodbc.connect(conn_str, autocommit=True)
        return conn
    
    def _set_server_version(self, conn):
        """Extract SQL Server version from pyodbc connection."""
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT @@VERSION')
            version_str = cursor.fetchone()[0]
            import re
            match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_str)
            if match:
                self.server_version = tuple(int(x) for x in match.groups())
            else:
                self.server_version = (0, 0, 0)
        except Exception:
            self.server_version = (0, 0, 0)
