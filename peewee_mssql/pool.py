import functools
import heapq
import logging
import threading
import time
from collections import namedtuple

from peewee import InterfaceError

from .database import MssqlDatabase

try:
    import pymssql
except ImportError:
    pymssql = None

__all__ = ['PooledMssqlDatabase']

logger = logging.getLogger('peewee_mssql.pool')


PoolConnection = namedtuple('PoolConnection', ('timestamp', 'connection',
                                               'checked_out'))


def locked(fn):
    @functools.wraps(fn)
    def inner(self, *args, **kwargs):
        with self._pool_lock:
            return fn(self, *args, **kwargs)
    return inner


class MaxConnectionsExceeded(ValueError):
    pass


class PooledMssqlDatabase(MssqlDatabase):
    """
    MSSQL database with connection pooling.
    
    Uses pymssql as the database driver with a thread-safe connection pool.
    """
    
    def __init__(self, database, max_connections=20, stale_timeout=None,
                 timeout=None, **kwargs):
        self._max_connections = self._make_int(max_connections)
        self._stale_timeout = self._make_int(stale_timeout)
        self._wait_timeout = self._make_int(timeout)
        if self._wait_timeout == 0:
            self._wait_timeout = float('inf')
        
        self._pool_lock = threading.RLock()
        self._pool_available = threading.Condition(self._pool_lock)
        self._connections = []
        self._heap_counter = 0
        self._in_use = {}
        self.conn_key = id
        
        super(PooledMssqlDatabase, self).__init__(database, **kwargs)
    
    @staticmethod
    def _make_int(val):
        if val is not None and not isinstance(val, (int, float)):
            return int(val)
        return val
    
    def init(self, database, max_connections=None, stale_timeout=None,
             timeout=None, **connect_kwargs):
        super(PooledMssqlDatabase, self).init(database, **connect_kwargs)
        if max_connections is not None:
            self._max_connections = self._make_int(max_connections)
        if stale_timeout is not None:
            self._stale_timeout = self._make_int(stale_timeout)
        if timeout is not None:
            self._wait_timeout = self._make_int(timeout)
            if self._wait_timeout == 0:
                self._wait_timeout = float('inf')
    
    def connect(self, reuse_if_open=False):
        if not self._wait_timeout:
            return super(PooledMssqlDatabase, self).connect(reuse_if_open)
        
        deadline = time.monotonic() + self._wait_timeout
        while True:
            try:
                return super(PooledMssqlDatabase, self).connect(reuse_if_open)
            except MaxConnectionsExceeded:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MaxConnectionsExceeded(
                        'Max connections exceeded, timed out attempting to '
                        'connect.')
                with self._pool_available:
                    self._pool_available.wait(timeout=min(remaining, 1.0))
    
    @locked
    def _connect(self):
        while self._connections:
            try:
                ts, _counter, conn = heapq.heappop(self._connections)
            except IndexError:
                break
            
            key = self.conn_key(conn)
            if self._is_closed(conn):
                logger.debug('Connection %s was closed, discarding.', key)
                continue
            
            if self._stale_timeout and self._is_stale(ts):
                logger.debug('Connection %s was stale, closing.', key)
                self._close_raw(conn)
                continue
            
            self._in_use[key] = PoolConnection(ts, conn, time.time())
            return conn
        
        if self._max_connections and (
                len(self._in_use) >= self._max_connections):
            raise MaxConnectionsExceeded('Exceeded maximum connections.')
        
        conn = super(PooledMssqlDatabase, self)._connect()
        ts = time.time()
        key = self.conn_key(conn)
        logger.debug('Created new connection %s.', key)
        self._in_use[key] = PoolConnection(ts, conn, time.time())
        return conn
    
    def _is_stale(self, timestamp):
        return (time.time() - timestamp) > self._stale_timeout
    
    def _is_closed(self, conn):
        """Check if a pymssql connection is closed."""
        try:
            # Try to check if connection is still alive
            if hasattr(conn, 'connection'):
                # pymssql connection object
                return conn.connection is None
            return False
        except Exception:
            return True
    
    def _can_reuse(self, conn):
        return True
    
    def _close_raw(self, conn):
        try:
            super(PooledMssqlDatabase, self)._close(conn)
        except Exception:
            logger.debug('Error closing connection %s.', self.conn_key(conn),
                         exc_info=True)
    
    @locked
    def _close(self, conn, close_conn=False):
        key = self.conn_key(conn)
        
        if close_conn:
            self._in_use.pop(key, None)
            self._close_raw(conn)
            return
        
        if key not in self._in_use:
            logger.debug('Connection %s not in use, ignoring close.', key)
            return
        
        pool_conn = self._in_use.pop(key)
        if self._stale_timeout and self._is_stale(pool_conn.timestamp):
            logger.debug('Closing stale connection %s on check-in.', key)
            self._close_raw(conn)
        elif not self._can_reuse(conn):
            logger.debug('Connection %s not reusable, closing.', key)
            self._close_raw(conn)
        else:
            logger.debug('Returning %s to pool.', key)
            self._heap_counter += 1
            heapq.heappush(self._connections,
                           (pool_conn.timestamp, self._heap_counter, conn))
        
        self._pool_available.notify()
    
    def manual_close(self):
        if self.is_closed():
            return False
        
        conn = self.connection()
        key = self.conn_key(conn)
        
        with self._pool_lock:
            self._in_use.pop(key, None)
        
        self.close()
        self._close_raw(conn)
    
    @locked
    def close_idle(self):
        idle = self._connections
        self._connections = []
        for _, _, conn in idle:
            self._close_raw(conn)
    
    @locked
    def close_stale(self, age=600):
        cutoff = time.time() - age
        n = 0
        for key, pool_conn in list(self._in_use.items()):
            if pool_conn.checked_out < cutoff:
                self._close_raw(pool_conn.connection)
                del self._in_use[key]
                n += 1
        
        self._pool_available.notify_all()
        return n
    
    def close_all(self):
        self.close()
        with self._pool_lock:
            self.close_idle()
            in_use, self._in_use = self._in_use, {}
            for pool_conn in in_use.values():
                self._close_raw(pool_conn.connection)
            
            self._pool_available.notify_all()
