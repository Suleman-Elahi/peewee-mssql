from peewee import SQL, CommaNodeList, EnclosedNodeList, Node
from peewee import SCOPE_NORMAL, SCOPE_SOURCE, SCOPE_COLUMN

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


def mssql_apply_ordering(self, ctx):
    """
    Monkey-patch function for Select._apply_ordering.
    Uses OFFSET/FETCH NEXT for pagination (TOP is handled in __sql__).
    """
    if self._order_by:
        ctx.literal(' ORDER BY ').sql(CommaNodeList(self._order_by))
    
    if self._offset is not None:
        # OFFSET/FETCH NEXT syntax requires ORDER BY
        if not self._order_by:
            ctx.literal(' ORDER BY (SELECT NULL)')
        ctx.literal(' OFFSET ').sql(self._offset)
        ctx.literal(' ROWS')
        if self._limit is not None:
            ctx.literal(' FETCH NEXT ').sql(self._limit)
            ctx.literal(' ROWS ONLY')
    
    return ctx


def mssql_select_sql(self, ctx):
    """
    Monkey-patch function for Select.__sql__ to add:
    1. TOP N after SELECT (instead of LIMIT)
    2. Table hints (WITH NOLOCK, etc.)
    """
    from peewee import Select, CommaNodeList, EnclosedNodeList
    from peewee import SCOPE_COLUMN
    
    if ctx.scope == SCOPE_COLUMN:
        return self.apply_column(ctx)
    
    if self._lateral and ctx.scope == SCOPE_SOURCE:
        ctx.literal('LATERAL ')
    
    is_subquery = ctx.subquery
    state = {
        'converter': None,
        'in_function': False,
        'parentheses': is_subquery or (ctx.scope == SCOPE_SOURCE),
        'subquery': True,
    }
    if ctx.state.in_function and ctx.state.function_arg_count == 1:
        state['parentheses'] = False
    
    with ctx.scope_normal(**state):
        # Call parent __sql__ for CTEs
        super(Select, self).__sql__(ctx)
        
        ctx.literal('SELECT ')
        if self._simple_distinct or self._distinct is not None:
            ctx.literal('DISTINCT ')
            if self._distinct:
                (ctx
                 .literal('ON ')
                 .sql(EnclosedNodeList(self._distinct))
                 .literal(' '))
        
        # Add TOP N here (after SELECT DISTINCT, before columns)
        if self._offset is None and self._limit is not None:
            ctx.literal('TOP ').sql(self._limit).literal(' ')
        
        with ctx.scope_source():
            ctx = self.__sql_selection__(ctx, is_subquery)
        
        if self._from_list:
            with ctx.scope_source(parentheses=False):
                ctx.literal(' FROM ').sql(CommaNodeList(self._from_list))
        
        # Add table hints after FROM clause
        if hasattr(self, '_table_hints') and self._table_hints is not None:
            ctx.literal(' ')
            ctx.sql(self._table_hints)
        
        if self._where is not None:
            ctx.literal(' WHERE ').sql(self._where)
        
        if self._group_by:
            ctx.literal(' GROUP BY ').sql(CommaNodeList(self._group_by))
        
        if self._having is not None:
            ctx.literal(' HAVING ').sql(self._having)
        
        if self._windows is not None:
            ctx.literal(' WINDOW ')
            ctx.sql(CommaNodeList(self._windows))
        
        # Apply ORDER BY and OFFSET/FETCH NEXT
        self._apply_ordering(ctx)
        
        if self._for_update is not None:
            if not ctx.state.for_update:
                raise ValueError('FOR UPDATE specified but not supported '
                                 'by database.')
            ctx.literal(' ')
            ctx.sql(self._for_update)
    
    if ctx.state.in_function or (ctx.state.in_expr and
                                 self._alias is None):
        return ctx
    
    return self.apply_alias(ctx)
