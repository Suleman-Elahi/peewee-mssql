"""
MSSQL FOR UPDATE with table hints support.

Provides SQL Server-specific locking hints for SELECT statements.
"""
from peewee import (
    Node,
    SQL,
    CommaNodeList,
)

__all__ = [
    'ForUpdate',
    'with_nolock',
    'with_holdlock',
    'with_updlock',
    'with_readpast',
    'with_xlock',
    'with_tablock',
]


class ForUpdate(Node):
    """
    SQL Server FOR UPDATE with table hints.
    
    Extends Peewee's ForUpdate to support SQL Server-specific hints.
    
    Example:
        from peewee_sqlserver import ForUpdate
        
        # FOR UPDATE with HOLDLOCK
        query = MyModel.select().for_update(of=MyModel, holdlock=True)
        
        # FOR UPDATE with UPDLOCK and READPAST
        query = MyModel.select().for_update(
            of=MyModel, 
            updlock=True, 
            readpast=True
        )
    """
    
    def __init__(self, expr='FOR UPDATE', of=None, nowait=None, 
                 skip_locked=None, holdlock=None, updlock=None,
                 readpast=None, nolock=None, xlock=None, paglock=None,
                 tablock=None, tablockx=None):
        """
        Initialize FOR UPDATE clause.
        
        Args:
            expr: Base expression ('FOR UPDATE', 'FOR BROWSE', etc.)
            of: Table(s) to lock
            nowait: If True, fail immediately if locked
            skip_locked: If True, skip locked rows
            holdlock: HOLDLOCK hint (serializable isolation)
            updlock: UPDLOCK hint (update locks)
            readpast: READPAST hint (skip locked rows)
            nolock: NOLOCK hint (read uncommitted)
            xlock: XLOCK hint (exclusive lock)
            paglock: PAGLOCK hint (page lock)
            tablock: TABLOCK hint (table lock)
            tablockx: TABLOCKX hint (exclusive table lock)
        """
        self._expr = expr
        self._of = of
        self._nowait = nowait
        self._skip_locked = skip_locked
        self._holdlock = holdlock
        self._updlock = updlock
        self._readpast = readpast
        self._nolock = nolock
        self._xlock = xlock
        self._paglock = paglock
        self._tablock = tablock
        self._tablockx = tablockx
        
        # Collect all hints
        self._hints = []
        if holdlock:
            self._hints.append('HOLDLOCK')
        if updlock:
            self._hints.append('UPDLOCK')
        if readpast:
            self._hints.append('READPAST')
        if nolock:
            self._hints.append('NOLOCK')
        if xlock:
            self._hints.append('XLOCK')
        if paglock:
            self._hints.append('PAGLOCK')
        if tablock:
            self._hints.append('TABLOCK')
        if tablockx:
            self._hints.append('TABLOCKX')
    
    def __sql__(self, ctx):
        # Base expression
        ctx.literal(self._expr)
        
        # OF clause
        if self._of is not None:
            ctx.literal(' OF ')
            if isinstance(self._of, (list, tuple)):
                ctx.sql(CommaNodeList(self._of))
            else:
                ctx.sql(self._of)
        
        # NOWAIT or SKIP LOCKED
        if self._nowait:
            ctx.literal(' NOWAIT')
        elif self._skip_locked:
            ctx.literal(' SKIP LOCKED')
        
        # Table hints in WITH clause
        if self._hints:
            ctx.literal(' WITH (')
            ctx.literal(', '.join(self._hints))
            ctx.literal(')')
        
        return ctx


def with_nolock(*tables):
    """
    Create a NOLOCK hint clause.
    
    Args:
        *tables: Tables to apply NOLOCK to
    
    Returns:
        SQL expression with NOLOCK hint
    
    Example:
        from peewee_sqlserver import with_nolock
        
        query = MyModel.select().where(
            MyModel.id > 10
        ).nolock()  # Uses patched nolock()
    """
    if not tables:
        return SQL('WITH (NOLOCK)')
    
    hints = []
    for table in tables:
        hints.append('%s WITH (NOLOCK)' % table)
    
    return SQL(', '.join(hints))


def with_holdlock(*tables):
    """
    Create a HOLDLOCK hint clause.
    
    HOLDLOCK acquires and holds shared locks to the end of a transaction
    or until the end of the specified table name scope, whichever comes first.
    """
    if not tables:
        return SQL('WITH (HOLDLOCK)')
    
    hints = []
    for table in tables:
        hints.append('%s WITH (HOLDLOCK)' % table)
    
    return SQL(', '.join(hints))


def with_updlock(*tables):
    """
    Create an UPDLOCK hint clause.
    
    UPDLOCK acquires update locks and holds them until the end of the
    transaction or statement.
    """
    if not tables:
        return SQL('WITH (UPDLOCK)')
    
    hints = []
    for table in tables:
        hints.append('%s WITH (UPDLOCK)' % table)
    
    return SQL(', '.join(hints))


def with_readpast(*tables):
    """
    Create a READPAST hint clause.
    
    READPAST skips rows locked by other transactions.
    """
    if not tables:
        return SQL('WITH (READPAST)')
    
    hints = []
    for table in tables:
        hints.append('%s WITH (READPAST)' % table)
    
    return SQL(', '.join(hints))


def with_xlock(*tables):
    """
    Create an XLOCK hint clause.
    
    XLOCK acquires exclusive locks and holds them to the end of the transaction.
    """
    if not tables:
        return SQL('WITH (XLOCK)')
    
    hints = []
    for table in tables:
        hints.append('%s WITH (XLOCK)' % table)
    
    return SQL(', '.join(hints))


def with_tablock(*tables):
    """
    Create a TABLOCK hint clause.
    
    TABLOCK acquires a table lock and holds it until the end of the statement.
    """
    if not tables:
        return SQL('WITH (TABLOCK)')
    
    hints = []
    for table in tables:
        hints.append('%s WITH (TABLOCK)' % table)
    
    return SQL(', '.join(hints))
