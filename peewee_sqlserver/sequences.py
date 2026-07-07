"""
MSSQL SEQUENCE support for Peewee.

Provides sequence creation, management, and NEXT VALUE FOR usage.
"""
from peewee import (
    Node,
    SQL,
    CommaNodeList,
    Value,
    Field,
)
from peewee import __exception_wrapper__

__all__ = ['Sequence', 'next_value', 'create_sequence', 'drop_sequence']


class Sequence(Node):
    """
    SQL Server SEQUENCE object.
    
    Sequences are database objects that generate unique numeric values.
    They are useful for generating primary keys or unique identifiers.
    
    Example:
        from peewee_sqlserver import Sequence
        
        # Define a sequence
        user_id_seq = Sequence('user_id_seq', start_with=1, increment_by=1)
        
        # Create the sequence
        user_id_seq.create(db)
        
        # Get next value
        next_id = user_id_seq.next_value(db)
        
        # Drop the sequence
        user_id_seq.drop(db)
    """
    
    def __init__(self, name, start_with=1, increment_by=1, min_value=1,
                 max_value=None, cycle=False, cache=None, no_order=False):
        """
        Initialize sequence.
        
        Args:
            name: Sequence name
            start_with: Starting value (default: 1)
            increment_by: Increment value (default: 1)
            min_value: Minimum value (default: 1)
            max_value: Maximum value (default: no limit)
            cycle: Whether to cycle when max_value is reached
            cache: Number of values to cache (default: no cache)
            no_order: If True, values may be non-sequential (better performance)
        """
        self.name = name
        self.start_with = start_with
        self.increment_by = increment_by
        self.min_value = min_value
        self.max_value = max_value
        self.cycle = cycle
        self.cache = cache
        self.no_order = no_order
    
    def __sql__(self, ctx):
        ctx.literal(self.name)
        return ctx
    
    def create_sql(self):
        """Generate CREATE SEQUENCE SQL."""
        parts = ['CREATE SEQUENCE %s' % self.name]
        parts.append('AS INT')  # Default type
        parts.append('START WITH %d' % self.start_with)
        parts.append('INCREMENT BY %d' % self.increment_by)
        
        if self.min_value is not None:
            parts.append('MINVALUE %d' % self.min_value)
        
        if self.max_value is not None:
            parts.append('MAXVALUE %d' % self.max_value)
        else:
            parts.append('NO MAXVALUE')
        
        if self.cycle:
            parts.append('CYCLE')
        else:
            parts.append('NO CYCLE')
        
        if self.cache is not None:
            parts.append('CACHE %d' % self.cache)
        else:
            parts.append('NO CACHE')
        
        if self.no_order:
            parts.append('NO ORDER')
        
        return ' '.join(parts)
    
    def drop_sql(self):
        """Generate DROP SEQUENCE SQL."""
        return 'DROP SEQUENCE IF EXISTS %s' % self.name
    
    def next_value_sql(self, over=None):
        """Generate NEXT VALUE FOR SQL."""
        if over is not None:
            return 'NEXT VALUE FOR %s OVER (ORDER BY %s)' % (self.name, over)
        return 'NEXT VALUE FOR %s' % self.name
    
    def create(self, db):
        """Create the sequence in the database."""
        db.execute_sql(self.create_sql())
    
    def drop(self, db):
        """Drop the sequence from the database."""
        db.execute_sql(self.drop_sql())
    
    def next_value(self, db, over=None):
        """Get the next value from the sequence."""
        cursor = db.execute_sql(self.next_value_sql(over))
        return cursor.fetchone()[0]
    
    def current_value(self, db):
        """Get the current value of the sequence."""
        query = "SELECT current_value FROM sys.sequences WHERE name = '%s'" % self.name
        cursor = db.execute_sql(query)
        result = cursor.fetchone()
        return result[0] if result else None
    
    def reset(self, db, value=None):
        """Reset the sequence to a specific value."""
        if value is None:
            value = self.start_with
        db.execute_sql('ALTER SEQUENCE %s RESTART WITH %d' % (self.name, value))


def next_value(sequence_name, over=None):
    """
    Get next value from a sequence.
    
    Args:
        sequence_name: Name of the sequence
        over: Optional ORDER BY clause for distributed sequences
    
    Returns:
        SQL expression for NEXT VALUE FOR
    
    Example:
        from peewee_sqlserver import next_value
        
        # In a query
        query = MyModel.select().where(
            MyModel.id == next_value('my_sequence')
        )
        
        # With ORDER BY
        query = MyModel.select().where(
            MyModel.id == next_value('my_sequence', 'created_at')
        )
    """
    if over is not None:
        return SQL('NEXT VALUE FOR %s OVER (ORDER BY %s)' % (sequence_name, over))
    return SQL('NEXT VALUE FOR %s' % sequence_name)


def create_sequence(name, start_with=1, increment_by=1, min_value=1,
                    max_value=None, cycle=False, cache=None):
    """
    Create a sequence.
    
    Returns:
        Sequence object
    """
    seq = Sequence(
        name=name,
        start_with=start_with,
        increment_by=increment_by,
        min_value=min_value,
        max_value=max_value,
        cycle=cycle,
        cache=cache
    )
    return seq


def drop_sequence(name):
    """Drop a sequence."""
    return 'DROP SEQUENCE IF EXISTS %s' % name


class AutoSequence:
    """
    Automatically manages a sequence for primary key generation.
    
    This is useful for tables that need sequence-based IDs instead of
    IDENTITY columns.
    
    Example:
        from peewee_sqlserver import AutoSequence
        
        class MyModel(Model):
            id = IntegerField(primary_key=True)
            name = CharField()
            
            class Meta:
                database = db
                sequence_name = 'my_model_id_seq'
        
        # The sequence is created automatically
        AutoSequence(MyModel).create_if_not_exists(db)
    """
    
    def __init__(self, model, sequence_name=None):
        self.model = model
        self.sequence_name = sequence_name or '%s_id_seq' % model._meta.table_name
    
    def get_sequence(self):
        """Get the sequence object."""
        return Sequence(self.sequence_name)
    
    def create_if_not_exists(self, db):
        """Create the sequence if it doesn't exist."""
        # Check if sequence exists
        query = ("SELECT 1 FROM sys.sequences WHERE name = '%s'" 
                % self.sequence_name)
        cursor = db.execute_sql(query)
        if cursor.fetchone() is None:
            self.get_sequence().create(db)
    
    def next_value(self, db):
        """Get the next value for this model."""
        return self.get_sequence().next_value(db)
    
    def drop_if_exists(self, db):
        """Drop the sequence if it exists."""
        query = ("SELECT 1 FROM sys.sequences WHERE name = '%s'" 
                % self.sequence_name)
        cursor = db.execute_sql(query)
        if cursor.fetchone() is not None:
            self.get_sequence().drop(db)
