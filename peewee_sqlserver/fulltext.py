"""
MSSQL Full-Text Search support for Peewee.

Provides CONTAINS, FREETEXT, and CONTAINSTABLE operations.
"""
from peewee import (
    Node,
    SQL,
    CommaNodeList,
    Value,
    ColumnBase,
    Expression,
    OP,
)
from peewee import __exception_wrapper__

__all__ = [
    'FullTextSearch',
    'FullTextIndex',
    'contains',
    'freetext',
    'contains_table',
    'freetext_table',
]


class FullTextSearch(ColumnBase):
    """
    Full-text search using CONTAINS predicate.
    
    CONTAINS is used to search for words, phrases, or proximity terms
    in full-text indexed columns.
    
    Example:
        from peewee_sqlserver import FullTextSearch
        
        # Search for exact word
        query = MyModel.select().where(
            FullTextSearch(MyModel.content, 'database')
        )
        
        # Search for phrase
        query = MyModel.select().where(
            FullTextSearch(MyModel.content, '"SQL Server"')
        )
        
        # Search with prefix
        query = MyModel.select().where(
            FullTextSearch(MyModel.content, 'dat*')
        )
        
        # Search with AND
        query = MyModel.select().where(
            FullTextSearch(MyModel.content, 'database AND server')
        )
    """
    
    def __init__(self, field, search_term, language=None):
        """
        Initialize full-text search.
        
        Args:
            field: Field to search in
            search_term: Search term or expression
            language: Optional language for word breaking
        """
        self.field = field
        self.search_term = search_term
        self.language = language
    
    def __sql__(self, ctx):
        ctx.literal('CONTAINS(')
        ctx.sql(self.field)
        ctx.literal(', ')
        ctx.literal(repr(self.search_term))
        if self.language is not None:
            ctx.literal(', ')
            ctx.literal(repr(self.language))
        ctx.literal(')')
        return ctx
    
    def __and__(self, other):
        return Expression(self, OP.AND, other)
    
    def __or__(self, other):
        return Expression(self, OP.OR, other)


class FreeText(ColumnBase):
    """
    Full-text search using FREETEXT predicate.
    
    FREETEXT is less precise than CONTAINS but easier to use.
    It searches for the meaning of the search terms rather than
    exact matches.
    
    Example:
        from peewee_sqlserver import freetext
        
        query = MyModel.select().where(
            freetext(MyModel.content, 'database performance tuning')
        )
    """
    
    def __init__(self, field, search_term, language=None):
        """
        Initialize freetext search.
        
        Args:
            field: Field to search in
            search_term: Search term(s)
            language: Optional language for word breaking
        """
        self.field = field
        self.search_term = search_term
        self.language = language
    
    def __sql__(self, ctx):
        ctx.literal('FREETEXT(')
        ctx.sql(self.field)
        ctx.literal(', ')
        ctx.literal(repr(self.search_term))
        if self.language is not None:
            ctx.literal(', ')
            ctx.literal(repr(self.language))
        ctx.literal(')')
        return ctx


class ContainsTable(ColumnBase):
    """
    Full-text search using CONTAINSTABLE function.
    
    CONTAINSTABLE returns a table with rank values that indicate
    how well each row matches the search criteria.
    
    Example:
        from peewee_sqlserver import contains_table
        
        # Search and get rank
        query = (MyModel
                 .select(MyModel, ContainsTable.rank.alias('rank'))
                 .join(contains_table(MyModel, 'database'))
                 .order_by(SQL('rank').desc()))
    """
    
    def __init__(self, table, columns, search_term, language=None, top_n=None):
        """
        Initialize CONTAINSTABLE.
        
        Args:
            table: Table to search
            columns: Column(s) to search in ('*' for all)
            search_term: Search term or expression
            language: Optional language
            top_n: Optional top N results
        """
        self.table = table
        self.columns = columns if isinstance(columns, (list, tuple)) else [columns]
        self.search_term = search_term
        self.language = language
        self.top_n = top_n
    
    @property
    def rank(self):
        """Get the RANK column."""
        return SQL('RANK')
    
    def __sql__(self, ctx):
        ctx.literal('CONTAINSTABLE(')
        ctx.sql(self.table)
        ctx.literal(', ')
        
        if self.columns == ['*']:
            ctx.literal('*')
        else:
            ctx.literal('(')
            ctx.sql(CommaNodeList([SQL(c) for c in self.columns]))
            ctx.literal(')')
        
        ctx.literal(', ')
        ctx.literal(repr(self.search_term))
        
        if self.language is not None:
            ctx.literal(', ')
            ctx.literal(repr(self.language))
        
        if self.top_n is not None:
            ctx.literal(', ')
            ctx.literal(str(self.top_n))
        
        ctx.literal(')')
        return ctx


class FreeTextTable(ColumnBase):
    """
    Full-text search using FREETEXTTABLE function.
    
    FREETEXTTABLE is similar to CONTAINSTABLE but uses FREETEXT
    semantics for more flexible matching.
    
    Example:
        from peewee_sqlserver import freetext_table
        
        query = (MyModel
                 .select(MyModel, FreeTextTable.rank.alias('rank'))
                 .join(freetext_table(MyModel, 'performance tuning'))
                 .order_by(SQL('rank').desc()))
    """
    
    def __init__(self, table, columns, search_term, language=None, top_n=None):
        """
        Initialize FREETEXTTABLE.
        
        Args:
            table: Table to search
            columns: Column(s) to search in ('*' for all)
            search_term: Search term(s)
            language: Optional language
            top_n: Optional top N results
        """
        self.table = table
        self.columns = columns if isinstance(columns, (list, tuple)) else [columns]
        self.search_term = search_term
        self.language = language
        self.top_n = top_n
    
    @property
    def rank(self):
        """Get the RANK column."""
        return SQL('RANK')
    
    def __sql__(self, ctx):
        ctx.literal('FREETEXTTABLE(')
        ctx.sql(self.table)
        ctx.literal(', ')
        
        if self.columns == ['*']:
            ctx.literal('*')
        else:
            ctx.literal('(')
            ctx.sql(CommaNodeList([SQL(c) for c in self.columns]))
            ctx.literal(')')
        
        ctx.literal(', ')
        ctx.literal(repr(self.search_term))
        
        if self.language is not None:
            ctx.literal(', ')
            ctx.literal(repr(self.language))
        
        if self.top_n is not None:
            ctx.literal(', ')
            ctx.literal(str(self.top_n))
        
        ctx.literal(')')
        return ctx


class FullTextIndex(Node):
    """
    Full-text index definition for SQL Server.
    
    Used to create and manage full-text indexes on tables.
    
    Example:
        from peewee_sqlserver import FullTextIndex
        
        # Define full-text index
        fti = FullTextIndex(
            table='articles',
            columns=['title', 'content'],
            unique_index=False,
            change_tracking='AUTO'
        )
        
        # Create the index
        fti.create(db)
    """
    
    def __init__(self, table, columns, unique_index=False, 
                 change_tracking='AUTO', stopwords=None):
        """
        Initialize full-text index.
        
        Args:
            table: Table name
            columns: Column(s) to index
            unique_index: Whether the index is unique
            change_tracking: Change tracking mode (AUTO, OFF, MANUAL)
            stopwords: Optional stopwords table
        """
        self.table = table
        self.columns = columns if isinstance(columns, (list, tuple)) else [columns]
        self.unique_index = unique_index
        self.change_tracking = change_tracking
        self.stopwords = stopwords
    
    def create_sql(self):
        """Generate CREATE FULLTEXT INDEX SQL."""
        parts = ['CREATE FULLTEXT INDEX ON %s' % self.table]
        parts.append('(')
        parts.append(', '.join(self.columns))
        parts.append(')')
        parts.append('KEY INDEX PK_%s' % self.table)
        parts.append('WITH CHANGE_TRACKING = %s' % self.change_tracking)
        
        if self.stopwords:
            parts.append('STOPLIST = %s' % self.stopwords)
        
        return ' '.join(parts)
    
    def drop_sql(self):
        """Generate DROP FULLTEXT INDEX SQL."""
        return 'DROP FULLTEXT INDEX ON %s' % self.table
    
    def create(self, db):
        """Create the full-text index."""
        db.execute_sql(self.create_sql())
    
    def drop(self, db):
        """Drop the full-text index."""
        db.execute_sql(self.drop_sql())


def contains(field, search_term, language=None):
    """
    CONTAINS predicate for full-text search.
    
    Args:
        field: Field to search in
        search_term: Search term or expression
        language: Optional language
    
    Returns:
        FullTextSearch expression
    
    Example:
        from peewee_sqlserver import contains
        
        query = MyModel.select().where(
            contains(MyModel.content, 'database AND server')
        )
    """
    return FullTextSearch(field, search_term, language=language)


def freetext(field, search_term, language=None):
    """
    FREETEXT predicate for full-text search.
    
    Args:
        field: Field to search in
        search_term: Search term(s)
        language: Optional language
    
    Returns:
        FreeText expression
    
    Example:
        from peewee_sqlserver import freetext
        
        query = MyModel.select().where(
            freetext(MyModel.content, 'database performance')
        )
    """
    return FreeText(field, search_term, language=language)


def contains_table(table, columns, search_term, language=None, top_n=None):
    """
    CONTAINSTABLE function for ranked full-text search.
    
    Args:
        table: Table to search
        columns: Column(s) to search in
        search_term: Search term or expression
        language: Optional language
        top_n: Optional top N results
    
    Returns:
        ContainsTable expression
    
    Example:
        from peewee_sqlserver import contains_table
        
        # Get top 10 results by rank
        query = (MyModel
                 .select(MyModel, contains_table.rank.alias('rank'))
                 .join(contains_table(MyModel, ('title', 'content'), 'database'))
                 .order_by(SQL('rank').desc())
                 .limit(10))
    """
    return ContainsTable(table, columns, search_term, language=language, top_n=top_n)


def freetext_table(table, columns, search_term, language=None, top_n=None):
    """
    FREETEXTTABLE function for ranked full-text search.
    
    Args:
        table: Table to search
        columns: Column(s) to search in
        search_term: Search term(s)
        language: Optional language
        top_n: Optional top N results
    
    Returns:
        FreeTextTable expression
    """
    return FreeTextTable(table, columns, search_term, language=language, top_n=top_n)
