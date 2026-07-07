"""
MSSQL-specific fields for Peewee.

Provides JSON, XML, and computed column support for SQL Server.
"""
import json

from peewee import (
    Field,
    Node,
    ColumnBase,
    Expression,
    OP,
    SQL,
    Context,
)
from peewee import __exception_wrapper__

__all__ = [
    'JsonField',
    'XmlField',
    'ComputedField',
]


class MssqlJsonMethods:
    """JSON methods for SQL Server (2016+)."""
    
    def __init__(self, database):
        self.database = database
    
    def path(self, field, *keys):
        """Get JSON value at path using JSON_VALUE."""
        if not keys:
            return field
        path = '$.' + '.'.join(str(k) for k in keys)
        return SQL('JSON_VALUE(%s, %s)' % (field, path))
    
    def query(self, field, *keys):
        """Get JSON fragment at path using JSON_QUERY."""
        if not keys:
            return field
        path = '$.' + '.'.join(str(k) for k in keys)
        return SQL('JSON_QUERY(%s, %s)' % (field, path))
    
    def extract_text(self, field, keys):
        """Extract text value from JSON."""
        return self.path(field, *keys)
    
    def extract_value(self, field, keys):
        """Extract value from JSON."""
        return self.path(field, *keys)
    
    def contains(self, field, keys, value):
        """Check if JSON contains value."""
        path = '$.' + '.'.join(str(k) for k in keys) if keys else '$'
        return SQL("JSON_VALUE(%s, %s) = %s" % (field, path, value))
    
    def has_key(self, field, keys, key):
        """Check if JSON has key using JSON_VALUE."""
        path = '$.' + '.'.join(str(k) for k in keys if k) + '.' + key if keys else '$.' + key
        return SQL("JSON_VALUE(%s, %s) IS NOT NULL" % (field, path))
    
    def length(self, field, keys):
        """Get JSON array length using JSON_QUERY with OPENJSON."""
        path = '$.' + '.join(str(k) for k in keys)' if keys else '$'
        return SQL("(SELECT COUNT(*) FROM OPENJSON(%s, %s))" % (field, path))
    
    def append(self, field, keys, value):
        """Append value to JSON array using JSON_MODIFY."""
        path = '$.' + '.'.join(str(k) for k in keys) if keys else '$'
        value_str = json.dumps(value)
        return SQL("JSON_MODIFY(%s, '%s', JSON_QUERY(%s))" % (field, path, value_str))
    
    def update(self, field, keys, value):
        """Update JSON value using JSON_MODIFY."""
        path = '$.' + '.'.join(str(k) for k in keys) if keys else '$'
        value_str = json.dumps(value)
        return SQL("JSON_MODIFY(%s, '%s', %s)" % (field, path, value_str))
    
    def remove(self, field, keys):
        """Remove key from JSON using JSON_MODIFY with NULL."""
        path = '$.' + '.'.join(str(k) for k in keys) if keys else '$'
        return SQL("JSON_MODIFY(%s, '%s', NULL)" % (field, path))
    
    def merge(self, field, other):
        """Merge two JSON objects using OPENJSON."""
        return SQL("JSON_QUERY((SELECT * FROM OPENJSON(%s) WITH (%s)))" % (field, other))
    
    def type(self, field, *keys):
        """Get JSON value type using JSON_VALUE."""
        path = '$.' + '.'.join(str(k) for k in keys) if keys else '$'
        return SQL("JSON_VALUE(%s, '$.type') AS type" % field)
    
    def is_valid(self, field):
        """Check if string is valid JSON using ISJSON."""
        return SQL("ISJSON(%s) = 1" % field)
    
    def pretty(self, field):
        """Pretty print JSON using FOR JSON PATH with ROOT."""
        return SQL("CONVERT(NVARCHAR(MAX), %s, 1)" % field)


class JsonField(Field):
    """
    JSON field for SQL Server (2016+).
    
    Uses nvarchar(max) to store JSON strings.
    Provides path-based access to JSON values.
    
    Example:
        class MyModel(Model):
            data = JsonField(default={})
        
        # Access nested values
        query = MyModel.select().where(
            MyModel.data['name'] == 'John'
        )
        
        # Update JSON values
        MyModel.update(data=MyModel.data.update({'key': 'value'}))
    """
    
    field_type = 'NVARCHAR(MAX)'
    
    def __init__(self, dumps=None, loads=None, **kwargs):
        self._dumps = dumps or json.dumps
        self._loads = loads or json.loads
        super(JsonField, self).__init__(**kwargs)
    
    def db_value(self, value):
        if value is None or isinstance(value, Node):
            return value
        return self._dumps(value)
    
    def python_value(self, value):
        if value is None:
            return value
        if isinstance(value, str):
            try:
                return self._loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value
    
    def __getitem__(self, key):
        """Access JSON value at key."""
        return JsonPath(self, key)
    
    def path(self, *keys):
        """Access JSON value at path."""
        return JsonPath(self, keys)
    
    def contains(self, value):
        """Check if JSON contains value."""
        if isinstance(value, dict):
            conditions = []
            for k, v in value.items():
                conditions.append(self[k] == v)
            return reduce(lambda a, b: a & b, conditions)
        return self[None] == value
    
    def has_key(self, key):
        """Check if JSON has key."""
        return self[key].is_null() == False
    
    def is_valid(self):
        """Check if string is valid JSON."""
        return SQL("ISJSON(%s) = 1" % self)
    
    def update(self, value):
        """Update JSON with new values."""
        return JsonModify(self, value, 'update')
    
    def append(self, value):
        """Append value to JSON array."""
        return JsonModify(self, value, 'append')
    
    def remove(self, key):
        """Remove key from JSON."""
        return JsonModify(self, None, 'remove', key=key)


class JsonPath(ColumnBase):
    """Represents a path expression in a JSON field."""
    
    def __init__(self, field, key):
        self.field = field
        self.key = key
    
    def __sql__(self, ctx):
        if self.key is None:
            ctx.sql(self.field)
        elif isinstance(self.key, (list, tuple)):
            path = '$.' + '.'.join(str(k) for k in self.key)
            ctx.literal("JSON_VALUE(%s, '%s')" % (self.field, path))
        else:
            path = '$.%s' % self.key
            ctx.literal("JSON_VALUE(%s, '%s')" % (self.field, path))
        return ctx
    
    def __eq__(self, other):
        if other is None:
            return Expression(self, OP.IS, SQL('NULL'))
        return Expression(self, OP.EQ, other)
    
    def __ne__(self, other):
        if other is None:
            return Expression(self, OP.IS_NOT, SQL('NULL'))
        return Expression(self, OP.NE, other)
    
    def __lt__(self, other):
        return Expression(self, OP.LT, other)
    
    def __le__(self, other):
        return Expression(self, OP.LTE, other)
    
    def __gt__(self, other):
        return Expression(self, OP.GT, other)
    
    def __ge__(self, other):
        return Expression(self, OP.GTE, other)


class JsonModify(Node):
    """Represents a JSON_MODIFY operation."""
    
    def __init__(self, field, value, operation, key=None):
        self.field = field
        self.value = value
        self.operation = operation
        self.key = key
    
    def __sql__(self, ctx):
        if self.operation == 'update':
            ctx.literal("JSON_MODIFY(%s, '$', %s)" % (
                self.field, json.dumps(self.value)))
        elif self.operation == 'append':
            ctx.literal("JSON_MODIFY(%s, 'append $', %s)" % (
                self.field, json.dumps(self.value)))
        elif self.operation == 'remove':
            ctx.literal("JSON_MODIFY(%s, '%s', NULL)" % (
                self.field, self.key))
        return ctx


class XmlField(Field):
    """
    XML field for SQL Server.
    
    Uses xml data type to store XML data.
    Provides query and value extraction.
    
    Example:
        class MyModel(Model):
            config = XmlField()
        
        # Query XML
        query = MyModel.select().where(
            MyModel.config.query('/root/element') == 'value'
        )
    """
    
    field_type = 'XML'
    
    def __init__(self, **kwargs):
        super(XmlField, self).__init__(**kwargs)
    
    def db_value(self, value):
        if value is None or isinstance(value, Node):
            return value
        if isinstance(value, str):
            return value
        return str(value)
    
    def python_value(self, value):
        if value is None:
            return value
        return value
    
    def query(self, xpath):
        """Extract XML fragment using .query() method."""
        return XmlQuery(self, xpath)
    
    def value(self, xpath, data_type='nvarchar(4000)'):
        """Extract value using .value() method."""
        return XmlValue(self, xpath, data_type)
    
    def exist(self, xpath):
        """Check if XPath exists using .exist() method."""
        return XmlExist(self, xpath)
    
    def modify(self, xpath, new_value):
        """Modify XML using .modify() method."""
        return XmlModify(self, xpath, new_value)


class XmlQuery(ColumnBase):
    """Represents an XML query operation."""
    
    def __init__(self, field, xpath):
        self.field = field
        self.xpath = xpath
    
    def __sql__(self, ctx):
        ctx.literal("%s.query('%s')" % (self.field, self.xpath))
        return ctx


class XmlValue(ColumnBase):
    """Represents an XML value extraction."""
    
    def __init__(self, field, xpath, data_type):
        self.field = field
        self.xpath = xpath
        self.data_type = data_type
    
    def __sql__(self, ctx):
        ctx.literal("%s.value('%s', '%s')" % (
            self.field, self.xpath, self.data_type))
        return ctx


class XmlExist(ColumnBase):
    """Represents an XML existence check."""
    
    def __init__(self, field, xpath):
        self.field = field
        self.xpath = xpath
    
    def __sql__(self, ctx):
        ctx.literal("%s.exist('%s')" % (self.field, self.xpath))
        return ctx
    
    def __eq__(self, other):
        if other is True or other == 1:
            return Expression(self, OP.EQ, 1)
        elif other is False or other == 0:
            return Expression(self, OP.EQ, 0)
        return Expression(self, OP.EQ, other)
    
    def __bool__(self):
        raise TypeError("XmlExist cannot be used in boolean context")


class XmlModify(Node):
    """Represents an XML modify operation."""
    
    def __init__(self, field, xpath, new_value):
        self.field = field
        self.xpath = xpath
        self.new_value = new_value
    
    def __sql__(self, ctx):
        ctx.literal("%s.modify('insert %s as last into %s')" % (
            self.field, self.new_value, self.xpath))
        return ctx


class ComputedField(Field):
    """
    Computed/Persisted column for SQL Server.
    
    Creates a computed column that is automatically calculated.
    
    Example:
        class MyModel(Model):
            price = FloatField()
            quantity = IntegerField()
            total = ComputedField('price * quantity', persisted=True)
    """
    
    def __init__(self, expression, persisted=False, **kwargs):
        self.expression = expression
        self._persisted = persisted
        super(ComputedField, self).__init__(**kwargs)
    
    def sql(self, ctx):
        """Generate SQL for computed column definition."""
        ctx.literal(self.expression)
        if self._persisted:
            ctx.literal(' PERSISTED')
        return ctx
    
    def db_value(self, value):
        # Computed columns are read-only
        return None
    
    def python_value(self, value):
        return value


from functools import reduce
