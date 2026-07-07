import asyncio
import collections
import contextvars
import logging

try:
    import aioodbc
except ImportError:
    aioodbc = None

from peewee import (
    ImproperlyConfigured,
    InterfaceError,
    OperationalError,
)
from peewee import __exception_wrapper__

from .database import MssqlDatabase

try:
    from greenlet import greenlet, getcurrent
except ImportError:
    greenlet = None
    getcurrent = None

__all__ = ['AsyncMssqlDatabase']


logger = logging.getLogger(__name__)


class MissingGreenletBridge(RuntimeError):
    pass


_BRIDGE_ERR_HINT = (
    ' Hint: in async code, run queries through the async API, e.g. '
    '`await Model.aget(...)`, `await query.aexecute()`, `await '
    'db.list(query)`, or wrap synchronous code with `await db.run(fn)`. '
    'For lazy foreign-key access use `await obj.afetch(Model.rel_field)`. See '
    'https://docs.peewee-orm.com/en/latest/peewee/asyncio.html#sharp-corners')


async def greenlet_spawn(fn, *args, **kwargs):
    if greenlet is None:
        raise ImportError('greenlet is required for async support')
    
    parent = getcurrent()
    result = None
    error = None

    def runner():
        nonlocal result, error
        try:
            result = fn(*args, **kwargs)
        except BaseException as exc:
            error = exc

    g = greenlet(runner, parent=parent)
    g.gr_context = parent.gr_context
    value = g.switch()
    while not g.dead:
        try:
            value = g.switch(await value)
        except BaseException as exc:
            value = g.throw(exc)

    if error:
        raise error
    return result


def await_(awaitable):
    current = getcurrent()
    parent = current.parent
    if parent is None:
        if asyncio.iscoroutine(awaitable):
            awaitable.close()
        errmsg = 'await_() called outside greenlet_spawn()' + _BRIDGE_ERR_HINT
        raise MissingGreenletBridge(errmsg)
    return parent.switch(awaitable)


class _State(object):
    __slots__ = ('conn', 'closed', 'transactions', 'ctx', '_task_id')

    def __init__(self):
        self._task_id = None
        self.reset()

    def reset(self):
        self.conn = None
        self.closed = True
        self.transactions = []
        self.ctx = []


class _ConnectionState(object):
    def __init__(self):
        self._cv = contextvars.ContextVar('pwasyncio_mssql_state')
        self._states = {}
        self._orphaned_conns = []

    def _current(self):
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError('Cannot determine current task')
        tid = id(task)

        try:
            state = self._cv.get()
            if state._task_id == tid:
                if tid not in self._states:
                    self._states[tid] = state
                return state
        except LookupError:
            pass

        if tid in self._states:
            state = self._states[tid]
        else:
            state = _State()
            state._task_id = tid
            self._states[tid] = state
            task.add_done_callback(self._on_task_done)

        self._cv.set(state)
        return state

    def _on_task_done(self, task):
        tid = id(task)
        state = self._states.pop(tid, None)
        if state is not None and state.conn is not None and not state.closed:
            self._orphaned_conns.append(state.conn)
            state.reset()

    @property
    def conn(self):
        return self._current().conn

    @property
    def closed(self):
        return self._current().closed

    @property
    def transactions(self):
        return self._current().transactions

    @property
    def ctx(self):
        return self._current().ctx

    def reset(self):
        try:
            state = self._current()
        except RuntimeError:
            return
        state.reset()

    def set_connection(self, conn):
        state = self._current()
        state.conn = conn
        state.closed = False


class CursorAdapter(object):
    """Wraps query results for Peewee compatibility."""
    
    DEFAULT_BUFFER_SIZE = 100

    def __init__(self, rows=None, lastrowid=None, rowcount=None,
                 description=None, fetch_many=None, cleanup=None,
                 buffer_size=None):
        self._rows = rows or []
        self._idx = 0
        self.lastrowid = lastrowid
        self.rowcount = rowcount if rowcount is not None else len(self._rows)
        self.description = description or []
        self._fetch_many = fetch_many
        self._cleanup = cleanup
        self._buffer_size = buffer_size or self.DEFAULT_BUFFER_SIZE
        self._buffer = collections.deque()
        self._exhausted = False
        self._closed = False

    def fetchone(self):
        if self._fetch_many is not None:
            return self._lazy_fetchone()
        if self._idx >= len(self._rows):
            return
        row = self._rows[self._idx]
        self._idx += 1
        return row

    def _lazy_fetchone(self):
        if not self._buffer:
            if self._exhausted:
                return None
            with __exception_wrapper__:
                rows = await_(self._fetch_many(self._buffer_size))
            if not rows:
                self._exhausted = True
                return None
            self._buffer.extend(rows)
        return self._buffer.popleft()

    def fetchall(self):
        if self._fetch_many is not None:
            return list(self)
        return self._rows

    def __iter__(self):
        if self._fetch_many is not None:
            return _lazy_cursor_iter(self)
        return iter(self._rows)

    def close(self):
        self._closed = True

    async def aclose(self):
        if self._closed:
            return
        self._closed = True
        if self._cleanup is not None:
            try:
                await self._cleanup()
            finally:
                self._cleanup = None
                self._fetch_many = None


def _lazy_cursor_iter(cursor):
    while True:
        row = cursor.fetchone()
        if row is None:
            return
        yield row


class AsyncMssqlConnection:
    """
    Async wrapper around aioodbc connection for MSSQL.
    
    Handles cursor lifecycle properly to avoid "connection busy" errors.
    """
    
    def __init__(self, conn):
        self.conn = conn
        self._lock = asyncio.Lock()
        self._active_cursor = None  # Track active cursor

    async def execute(self, sql, params=None):
        """
        Execute SQL and return results.
        
        Properly manages cursor lifecycle to prevent "connection busy" errors:
        1. Closes any previous active cursor
        2. Executes the query
        3. Fetches all results before closing cursor
        4. Returns wrapped results
        """
        async with self._lock:
            # Close any previously active cursor that wasn't properly closed
            if self._active_cursor is not None:
                try:
                    await self._active_cursor.close()
                except Exception:
                    pass
                self._active_cursor = None
            
            cursor = await self.conn.cursor()
            self._active_cursor = cursor
            
            try:
                await cursor.execute(sql, params or ())
                
                # For SELECT queries, fetch all results immediately
                # This ensures the cursor is ready for the next query
                try:
                    rows = await cursor.fetchall()
                except Exception:
                    # Not all queries return rows (INSERT, UPDATE, etc.)
                    rows = []
                
                lastrowid = cursor.lastrowid if hasattr(cursor, 'lastrowid') else None
                rowcount = cursor.rowcount
                description = cursor.description
                
                return CursorAdapter(
                    rows=rows,
                    lastrowid=lastrowid,
                    rowcount=rowcount,
                    description=description
                )
            except Exception:
                # On error, ensure cursor is closed
                raise
            finally:
                # Always close the cursor after query completes
                try:
                    await cursor.close()
                except Exception:
                    pass
                self._active_cursor = None

    async def close(self):
        """Close the connection, cleaning up any active cursors first."""
        if self.conn:
            # Close any active cursor first
            if self._active_cursor is not None:
                try:
                    await self._active_cursor.close()
                except Exception:
                    pass
                self._active_cursor = None
            
            try:
                await self.conn.close()
            except Exception:
                pass
            self.conn = None


class AsyncMssqlPool:
    """
    Async connection pool for MSSQL using aioodbc.
    
    Automatically enables MARS (Multiple Active Result Sets) for SQL Server
    to prevent "connection busy" errors.
    """
    
    def __init__(self, dsn, pool_size=5, **connect_kwargs):
        self._dsn = dsn
        self._pool_size = pool_size
        self._connect_kwargs = connect_kwargs
        self._pool = None
        self._closed = False

    async def initialize(self):
        # Enable MARS by default for SQL Server to prevent "connection busy" errors
        # MARS allows multiple active result sets on a single connection
        connect_kwargs = dict(self._connect_kwargs)
        
        # Add MARS connection parameter if not already set
        # This prevents "connection is busy with results of another command" errors
        if 'mars_connection' not in connect_kwargs:
            connect_kwargs['mars_connection'] = 'yes'
        elif connect_kwargs['mars_connection'] is True:
            connect_kwargs['mars_connection'] = 'yes'
        
        self._pool = await aioodbc.create_pool(
            dsn=self._dsn,
            min_size=1,
            max_size=self._pool_size,
            **connect_kwargs
        )
        return self

    async def acquire(self, timeout=None):
        if self._closed:
            raise InterfaceError('Pool is closed.')
        conn = await asyncio.wait_for(
            self._pool.acquire(),
            timeout=timeout
        )
        return AsyncMssqlConnection(conn)

    async def release(self, conn):
        if self._closed:
            return
        if conn.conn is not None:
            # Ensure any active cursor is closed before releasing
            if conn._active_cursor is not None:
                try:
                    await conn._active_cursor.close()
                except Exception:
                    pass
                conn._active_cursor = None
            
            self._pool.release(conn.conn)

    async def close(self):
        self._closed = True
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()


class AsyncMssqlDatabase(MssqlDatabase):
    """
    Async MSSQL database adapter using aioodbc.
    
    Requires aioodbc and greenlet packages.
    
    Features:
    - Automatic MARS (Multiple Active Result Sets) support
    - Proper cursor lifecycle management
    - Connection pooling with automatic cleanup
    - Prevents "connection busy" errors
    """
    
    def __init__(self, database, **kwargs):
        self._pool_size = kwargs.pop('pool_size', 10)
        self._pool_min_size = kwargs.pop('pool_min_size', 1)
        self._acquire_timeout = kwargs.pop('acquire_timeout', 10)
        
        # MARS support - enabled by default
        self._enable_mars = kwargs.pop('enable_mars', True)
        
        # Remove use_legacy_datetime from kwargs before passing to parent
        self._use_legacy_datetime = kwargs.get('use_legacy_datetime', False)
        
        super(AsyncMssqlDatabase, self).__init__(database, **kwargs)
        
        self._state = _ConnectionState()
        self._pool = None
        self._pool_lock = asyncio.Lock()
        self._closing = False

    def execute_sql(self, sql, params=None):
        try:
            return await_(self.aexecute_sql(sql, params or ()))
        except MissingGreenletBridge as exc:
            errmsg = f'Attempted query outside greenlet runner: {sql}.'
            raise MissingGreenletBridge(errmsg + _BRIDGE_ERR_HINT) from exc

    async def aexecute_sql(self, sql, params=None):
        """Execute SQL query asynchronously."""
        conn = await self.aconnect()
        with __exception_wrapper__:
            return await conn.execute(sql, params)

    def connect(self):
        return await_(self.aconnect())

    async def aconnect(self):
        """Get or create async database connection."""
        if self._closing:
            raise InterfaceError('Database pool is shutting down.')

        # Clean up orphaned connections
        while self._state._orphaned_conns:
            orphan = self._state._orphaned_conns.pop()
            await self._pool_release(orphan)

        conn = self._state.conn
        if conn is None or conn.conn is None:
            if conn is not None:
                await self._pool_release(conn)
            conn = await self._acquire_conn_async()
            self._state.set_connection(conn)
        return conn

    def close(self):
        return await_(self.aclose())

    async def aclose(self):
        """Close the database connection."""
        if self.in_transaction():
            raise OperationalError('Attempting to close database while '
                                   'transaction is open.')
        conn = self._state.conn
        if conn:
            self._state.reset()
            logger.debug('Releasing connection %s to pool.', id(conn))
            await self._pool_release(conn)

    async def _acquire_conn_async(self):
        """Acquire a connection from the pool."""
        async with self._pool_lock:
            if self._pool is None:
                self._pool = await self._create_pool_async()

        try:
            conn = await self._pool_acquire()
        except asyncio.TimeoutError:
            raise OperationalError(
                'Timed out acquiring connection from pool '
                '(acquire_timeout=%s).' % self._acquire_timeout) from None
        logger.debug('Acquired connection %s from pool.', id(conn))
        return conn

    async def _create_pool_async(self):
        """Create the async connection pool."""
        if aioodbc is None:
            raise ImproperlyConfigured(
                'aioodbc must be installed for async MSSQL. '
                'Install with: pip install aioodbc'
            )
        
        # Build DSN from connect_params
        dsn = self.database
        if not dsn:
            # Build DSN from individual parameters
            parts = []
            
            # Add driver if not specified
            if 'driver' not in self.connect_params:
                parts.append('driver={ODBC Driver 18 for SQL Server}')
            
            for key, value in self.connect_params.items():
                if isinstance(value, bool):
                    value = 'yes' if value else 'no'
                parts.append(f'{key}={value}')
            
            dsn = ';'.join(parts)
        
        # Separate pool-specific kwargs from connection kwargs
        pool_kwargs = {}
        conn_kwargs = {}
        
        for key, value in self.connect_params.items():
            if key in ('min_size', 'max_size', 'pool_size'):
                continue  # Handled separately
            conn_kwargs[key] = value
        
        return await AsyncMssqlPool(
            dsn=dsn,
            pool_size=self._pool_size,
            **conn_kwargs
        ).initialize()

    async def _pool_acquire(self):
        """Acquire connection from pool with timeout."""
        return await asyncio.wait_for(
            self._pool.acquire(timeout=self._acquire_timeout),
            timeout=self._acquire_timeout
        )

    async def _pool_release(self, conn):
        """Release connection back to pool."""
        if conn is not None:
            await self._pool.release(conn)

    async def close_pool(self):
        """Close all connections in the pool."""
        self._closing = True
        try:
            if self._pool:
                # Release connections held by any task still in the registry
                for state in list(self._state._states.values()):
                    if state.conn and not state.closed:
                        conn = state.conn
                        state.reset()
                        try:
                            await self._pool_release(conn)
                        except Exception:
                            logger.warning(
                                'Error releasing connection during pool close',
                                exc_info=True)
                self._state._states.clear()

                # Drain any orphaned connections
                while self._state._orphaned_conns:
                    orphan = self._state._orphaned_conns.pop()
                    try:
                        await self._pool_release(orphan)
                    except Exception:
                        logger.warning('Error releasing orphaned connection',
                                       exc_info=True)

                await self._pool.close()
                self._pool = None
        finally:
            self._closing = False

    async def __aenter__(self):
        await self.run(self.connect)
        return self

    async def __aexit__(self, exc_typ, exc, tb):
        await self.run(self.close)

    def is_closed(self):
        try:
            return self._state.closed
        except RuntimeError:
            return True

    async def run(self, fn, *args, **kwargs):
        """Run synchronous function in async context."""
        return await greenlet_spawn(fn, *args, **kwargs)
