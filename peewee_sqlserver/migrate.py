"""
MSSQL Migration support for Peewee.

Provides schema migration operations for SQL Server.
"""
from peewee import (
    Node,
    SQL,
    CommaNodeList,
    Field,
    CharField,
    TextField,
    IntegerField,
    BooleanField,
    DateTimeField,
    DateField,
    FloatField,
    DecimalField,
)
from peewee import __exception_wrapper__

__all__ = [
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
]


class MigrationOperation:
    """Base class for migration operations."""
    
    def __init__(self, table):
        self.table = table
    
    def sql(self):
        raise NotImplementedError


class AddColumn(MigrationOperation):
    """Add a column to a table."""
    
    def __init__(self, table, column_name, field, default=None, null=True):
        super(AddColumn, self).__init__(table)
        self.column_name = column_name
        self.field = field
        self.default = default
        self.null = null
    
    def __str__(self):
        return self.sql()
    
    def sql(self):
        parts = ['ALTER TABLE %s ADD' % self.table]
        parts.append(self.column_name)
        parts.append(self._get_column_type())
        
        if not self.null:
            parts.append('NOT NULL')
        
        if self.default is not None:
            parts.append('DEFAULT %s' % self._format_default())
        
        return ' '.join(parts)
    
    def _get_column_type(self):
        """Get the SQL column type for the field."""
        if isinstance(self.field, CharField):
            max_length = self.field.max_length or 255
            return 'NVARCHAR(%d)' % max_length
        elif isinstance(self.field, TextField):
            return 'NVARCHAR(MAX)'
        elif isinstance(self.field, IntegerField):
            return 'INT'
        elif isinstance(self.field, BooleanField):
            return 'BIT'
        elif isinstance(self.field, DateTimeField):
            return 'DATETIME2'
        elif isinstance(self.field, DateField):
            return 'DATE'
        elif isinstance(self.field, FloatField):
            return 'FLOAT'
        elif isinstance(self.field, DecimalField):
            return 'DECIMAL(%d, %d)' % (self.field.max_digits, self.field.decimal_places)
        else:
            return 'NVARCHAR(MAX)'
    
    def _format_default(self):
        """Format the default value."""
        if isinstance(self.default, str):
            return "'%s'" % self.default
        elif self.default is None:
            return 'NULL'
        return str(self.default)


class DropColumn(MigrationOperation):
    """Drop a column from a table."""
    
    def __init__(self, table, column_name):
        super(DropColumn, self).__init__(table)
        self.column_name = column_name
    
    def sql(self):
        return 'ALTER TABLE %s DROP COLUMN %s' % (self.table, self.column_name)
    
    def __str__(self):
        return self.sql()


class RenameColumn(MigrationOperation):
    """Rename a column in a table."""
    
    def __init__(self, table, old_name, new_name):
        super(RenameColumn, self).__init__(table)
        self.old_name = old_name
        self.new_name = new_name
    
    def __str__(self):
        return self.sql()
    
    def sql(self):
        return 'EXEC sp_rename \'%s.%s\', \'%s\', \'COLUMN\'' % (
            self.table, self.old_name, self.new_name)


class AlterColumn(MigrationOperation):
    """Alter a column definition."""
    
    def __init__(self, table, column_name, field):
        super(AlterColumn, self).__init__(table)
        self.column_name = column_name
        self.field = field
    
    def sql(self):
        # SQL Server doesn't support ALTER COLUMN with all changes
        # This generates a basic ALTER statement
        return 'ALTER TABLE %s ALTER COLUMN %s %s' % (
            self.table, self.column_name, self._get_column_type())
    
    def _get_column_type(self):
        """Get the SQL column type for the field."""
        if isinstance(self.field, CharField):
            max_length = self.field.max_length or 255
            return 'NVARCHAR(%d)' % max_length
        elif isinstance(self.field, TextField):
            return 'NVARCHAR(MAX)'
        elif isinstance(self.field, IntegerField):
            return 'INT'
        elif isinstance(self.field, BooleanField):
            return 'BIT'
        elif isinstance(self.field, DateTimeField):
            return 'DATETIME2'
        elif isinstance(self.field, DateField):
            return 'DATE'
        elif isinstance(self.field, FloatField):
            return 'FLOAT'
        elif isinstance(self.field, DecimalField):
            return 'DECIMAL(%d, %d)' % (self.field.max_digits, self.field.decimal_places)
        else:
            return 'NVARCHAR(MAX)'


class AddNotNull(MigrationOperation):
    """Add NOT NULL constraint to a column."""
    
    def __init__(self, table, column_name):
        super(AddNotNull, self).__init__(table)
        self.column_name = column_name
    
    def sql(self):
        # SQL Server requires column type when adding NOT NULL
        # This is a simplified version - in practice, you'd need to know the type
        return 'ALTER TABLE %s ALTER COLUMN %s NVARCHAR(255) NOT NULL' % (
            self.table, self.column_name)


class DropNotNull(MigrationOperation):
    """Drop NOT NULL constraint from a column."""
    
    def __init__(self, table, column_name):
        super(DropNotNull, self).__init__(table)
        self.column_name = column_name
    
    def sql(self):
        return 'ALTER TABLE %s ALTER COLUMN %s NVARCHAR(255) NULL' % (
            self.table, self.column_name)


class AddIndex(MigrationOperation):
    """Add an index to a table."""
    
    def __init__(self, table, columns, unique=False, name=None):
        super(AddIndex, self).__init__(table)
        self.columns = columns if isinstance(columns, (list, tuple)) else [columns]
        self.unique = unique
        self.name = name
    
    def sql(self):
        index_name = self.name or 'ix_%s_%s' % (
            self.table, '_'.join(self.columns))
        
        unique_str = 'UNIQUE ' if self.unique else ''
        columns_str = ', '.join(self.columns)
        
        return 'CREATE %sINDEX %s ON %s (%s)' % (
            unique_str, index_name, self.table, columns_str)


class DropIndex(MigrationOperation):
    """Drop an index from a table."""
    
    def __init__(self, table, index_name):
        super(DropIndex, self).__init__(table)
        self.index_name = index_name
    
    def sql(self):
        return 'DROP INDEX IF EXISTS %s ON %s' % (self.index_name, self.table)


class RenameTable(MigrationOperation):
    """Rename a table."""
    
    def __init__(self, old_name, new_name):
        super(RenameTable, self).__init__(old_name)
        self.new_name = new_name
    
    def sql(self):
        return 'EXEC sp_rename \'%s\', \'%s\'' % (self.table, self.new_name)


class CreateTable(MigrationOperation):
    """Create a table."""
    
    def __init__(self, table, columns, primary_key=None, constraints=None):
        super(CreateTable, self).__init__(table)
        self.columns = columns
        self.primary_key = primary_key
        self.constraints = constraints or []
    
    def sql(self):
        parts = ['CREATE TABLE %s (' % self.table]
        
        column_defs = []
        for name, field in self.columns.items():
            col_def = '%s %s' % (name, self._get_column_type(field))
            if not field.null:
                col_def += ' NOT NULL'
            column_defs.append(col_def)
        
        if self.primary_key:
            column_defs.append('PRIMARY KEY (%s)' % ', '.join(self.primary_key))
        
        parts.append(', '.join(column_defs))
        parts.append(')')
        
        return ' '.join(parts)
    
    def _get_column_type(self, field):
        """Get the SQL column type for the field."""
        if isinstance(field, CharField):
            max_length = field.max_length or 255
            return 'NVARCHAR(%d)' % max_length
        elif isinstance(field, TextField):
            return 'NVARCHAR(MAX)'
        elif isinstance(field, IntegerField):
            return 'INT'
        elif isinstance(field, BooleanField):
            return 'BIT'
        elif isinstance(field, DateTimeField):
            return 'DATETIME2'
        elif isinstance(field, DateField):
            return 'DATE'
        elif isinstance(field, FloatField):
            return 'FLOAT'
        elif isinstance(field, DecimalField):
            return 'DECIMAL(%d, %d)' % (field.max_digits, field.decimal_places)
        else:
            return 'NVARCHAR(MAX)'


class DropTable(MigrationOperation):
    """Drop a table."""
    
    def __init__(self, table, if_exists=True):
        super(DropTable, self).__init__(table)
        self.if_exists = if_exists
    
    def sql(self):
        if self.if_exists:
            return 'DROP TABLE IF EXISTS %s' % self.table
        return 'DROP TABLE %s' % self.table


class AddConstraint(MigrationOperation):
    """Add a constraint to a table."""
    
    def __init__(self, table, constraint_name, constraint_type, columns):
        super(AddConstraint, self).__init__(table)
        self.constraint_name = constraint_name
        self.constraint_type = constraint_type  # 'UNIQUE', 'CHECK', 'FOREIGN KEY'
        self.columns = columns if isinstance(columns, (list, tuple)) else [columns]
    
    def sql(self):
        if self.constraint_type == 'UNIQUE':
            return 'ALTER TABLE %s ADD CONSTRAINT %s UNIQUE (%s)' % (
                self.table, self.constraint_name, ', '.join(self.columns))
        elif self.constraint_type == 'CHECK':
            # CHECK constraints need a condition
            return 'ALTER TABLE %s ADD CONSTRAINT %s CHECK (%s)' % (
                self.table, self.constraint_name, self.columns)
        elif self.constraint_type == 'FOREIGN KEY':
            # FOREIGN KEY needs referenced table and column
            return 'ALTER TABLE %s ADD CONSTRAINT %s FOREIGN KEY (%s)' % (
                self.table, self.constraint_name, ', '.join(self.columns))
        else:
            raise ValueError('Unsupported constraint type: %s' % self.constraint_type)


class DropConstraint(MigrationOperation):
    """Drop a constraint from a table."""
    
    def __init__(self, table, constraint_name):
        super(DropConstraint, self).__init__(table)
        self.constraint_name = constraint_name
    
    def sql(self):
        return 'ALTER TABLE %s DROP CONSTRAINT IF EXISTS %s' % (
            self.table, self.constraint_name)


class MSSQLMigrator:
    """
    MSSQL Schema Migrator for Peewee.
    
    Provides methods to generate and execute migration operations.
    
    Example:
        from peewee_sqlserver import MSSQLMigrator, migrate
        
        db = MssqlDatabase('mydb', server='localhost')
        migrator = MSSQLMigrator(db)
        
        # Run migrations
        migrate(
            migrator.add_column('users', 'email', CharField(max_length=255)),
            migrator.rename_column('users', 'name', 'full_name'),
            migrator.add_index('users', ('email',), unique=True),
        )
    """
    
    def __init__(self, database):
        self.database = database
    
    def add_column(self, table, column_name, field, default=None, null=True):
        """Add a column to a table."""
        return AddColumn(table, column_name, field, default=default, null=null)
    
    def drop_column(self, table, column_name):
        """Drop a column from a table."""
        return DropColumn(table, column_name)
    
    def rename_column(self, table, old_name, new_name):
        """Rename a column in a table."""
        return RenameColumn(table, old_name, new_name)
    
    def alter_column(self, table, column_name, field):
        """Alter a column definition."""
        return AlterColumn(table, column_name, field)
    
    def add_not_null(self, table, column_name):
        """Add NOT NULL constraint to a column."""
        return AddNotNull(table, column_name)
    
    def drop_not_null(self, table, column_name):
        """Drop NOT NULL constraint from a column."""
        return DropNotNull(table, column_name)
    
    def add_index(self, table, columns, unique=False, name=None):
        """Add an index to a table."""
        return AddIndex(table, columns, unique=unique, name=name)
    
    def drop_index(self, table, index_name):
        """Drop an index from a table."""
        return DropIndex(table, index_name)
    
    def rename_table(self, old_name, new_name):
        """Rename a table."""
        return RenameTable(old_name, new_name)
    
    def create_table(self, table, columns, primary_key=None):
        """Create a table."""
        return CreateTable(table, columns, primary_key=primary_key)
    
    def drop_table(self, table, if_exists=True):
        """Drop a table."""
        return DropTable(table, if_exists=if_exists)
    
    def add_constraint(self, table, constraint_name, constraint_type, columns):
        """Add a constraint to a table."""
        return AddConstraint(table, constraint_name, constraint_type, columns)
    
    def drop_constraint(self, table, constraint_name):
        """Drop a constraint from a table."""
        return DropConstraint(table, constraint_name)


def migrate(*operations):
    """
    Execute migration operations.
    
    Args:
        *operations: MigrationOperation instances to execute
    
    Example:
        from peewee_sqlserver import MSSQLMigrator, migrate
        
        db = MssqlDatabase('mydb', server='localhost')
        migrator = MSSQLMigrator(db)
        
        migrate(
            migrator.add_column('users', 'email', CharField(max_length=255)),
            migrator.add_index('users', ('email',), unique=True),
        )
    """
    # This would execute the operations against the database
    # For now, we just collect them
    results = []
    for op in operations:
        if isinstance(op, MigrationOperation):
            results.append(op.sql())
    return results
