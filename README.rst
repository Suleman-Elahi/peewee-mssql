peewee-sqlserver
################

Microsoft SQL Server adapter for Peewee ORM.

Provides both synchronous and async database access for SQL Server
using `pymssql <http://pymssql.org>`__ or `pyodbc <https://github.com/mkleehammer/pyodbc>`__ (sync)
and `aioodbc <https://github.com/aio-libs/aioodbc>`__ (async) drivers.

Features
========

- Full Peewee 4.x compatibility
- Multiple driver support (pymssql or pyodbc)
- Connection pooling (PooledMssqlDatabase)
- Async/await support via aioodbc
- Table introspection (get_tables, get_columns, get_indexes, etc.)
- MSSQL-specific SQL generation (TOP for LIMIT, OFFSET/FETCH NEXT for pagination)
- Table hints (NOLOCK, UPDLOCK, HOLDLOCK, etc.)
- Complete MSSQL data type support
- JSON support (JsonField for SQL Server 2016+)
- XML support (XmlField)
- MERGE statement for upserts
- Sequence support
- Schema migrations
- Full-text search (CONTAINS, FREETEXT)
- Computed columns

Requirements
============

- Python 3.8+
- Peewee 3.0+
- One of the following drivers:

  - pymssql (for MssqlDatabase)
  - pyodbc (for MssqlPyodbcDatabase, recommended)
  - aioodbc (for AsyncMssqlDatabase)

Installation
============

.. code-block:: console

    # With pymssql
    $ pip install peewee-sqlserver[pymssql]

    # With pyodbc (recommended)
    $ pip install peewee-sqlserver[pyodbc]

    # For async support
    $ pip install peewee-sqlserver[async]

    # All drivers
    $ pip install peewee-sqlserver[all]

Quick Start
===========

Using pymssql
-------------

.. code-block:: python

    from peewee_sqlserver import MssqlDatabase

    db = MssqlDatabase(
        'MyDatabase',
        server='host.example.com',
        user='domain\\username',
        password='password'
    )

Using pyodbc (recommended)
--------------------------

.. code-block:: python

    from peewee_sqlserver import MssqlPyodbcDatabase

    # With individual parameters
    db = MssqlPyodbcDatabase(
        'MyDatabase',
        driver='ODBC Driver 18 for SQL Server',
        server='host.example.com',
        trusted_connection='yes'
    )

    # Or with explicit connection string
    db = MssqlPyodbcDatabase(
        'MyDatabase',
        connection_string=(
            'DRIVER={ODBC Driver 18 for SQL Server};'
            'SERVER=host.example.com;'
            'DATABASE=MyDatabase;'
            'Trusted_Connection=yes;'
            'TrustServerCertificate=yes'
        )
    )

Defining Models
===============

.. code-block:: python

    from peewee import Model, CharField, IntegerField, DateTimeField, BooleanField
    from peewee_sqlserver import MssqlDatabase

    db = MssqlDatabase('MyDatabase', server='localhost')

    class BaseModel(Model):
        class Meta:
            database = db

    class User(BaseModel):
        username = CharField(unique=True, max_length=50)
        email = CharField(max_length=100)
        is_active = BooleanField(default=True)
        created_at = DateTimeField()

    class Post(BaseModel):
        title = CharField(max_length=200)
        content = CharField()
        author = ForeignKeyField(User, backref='posts')
        published = BooleanField(default=False)

CRUD Operations
===============

Create
------

.. code-block:: python

    # Create single record
    user = User.create(
        username='john_doe',
        email='john@example.com',
        is_active=True
    )
    print(f"Created user with id: {user.id}")

    # Create without saving (then save manually)
    user = User(username='jane_doe', email='jane@example.com')
    user.save()

    # Bulk create
    users = [
        User(username='user1', email='user1@example.com'),
        User(username='user2', email='user2@example.com'),
        User(username='user3', email='user3@example.com'),
    ]
    User.bulk_create(users)

    # Get or create
    user, created = User.get_or_create(
        username='john_doe',
        defaults={'email': 'john@example.com', 'is_active': True}
    )

Read
----

.. code-block:: python

    # Get single record by primary key
    user = User.get_by_id(1)

    # Get single record with where clause
    user = User.get(User.username == 'john_doe')

    # Get or None (returns None if not found)
    user = User.get_or_none(User.username == 'nonexistent')

    # Select multiple records
    active_users = User.select().where(User.is_active == True)

    for user in active_users:
        print(user.username, user.email)

    # Select with ordering
    users = User.select().order_by(User.username)

    # Select with limit
    users = User.select().limit(10)

    # Select with offset
    users = User.select().limit(10).offset(20)

    # Select specific columns
    users = User.select(User.username, User.email)

    # Count
    total_users = User.select().count()

    # Exists
    user_exists = User.select().where(User.username == 'john_doe').exists()

    # First/Last
    first_user = User.select().order_by(User.id).first()
    last_user = User.select().order_by(User.id.desc()).last()

    # Aggregate
    from peewee import fn
    active_count = User.select(fn.COUNT(User.id)).where(User.is_active == True).scalar()

Update
------

.. code-block:: python

    # Update single record
    user = User.get_by_id(1)
    user.email = 'newemail@example.com'
    user.save()

    # Update with where clause (bulk update)
    User.update(is_active=False).where(User.created_at < some_date).execute()

    # Update specific fields only
    User.update(email='new@example.com').where(User.id == 1).execute()

    # Update with returning (SQL Server 2014+)
    # Note: Returning is not supported in MSSQL, use OUTPUT clause instead

Delete
------

.. code-block:: python

    # Delete single record
    user = User.get_by_id(1)
    user.delete_instance()

    # Delete with where clause
    User.delete().where(User.is_active == False).execute()

    # Delete all records
    User.delete().execute()

    # Delete with cascade
    user.delete_instance(recursive=True)

Transactions
============

.. code-block:: python

    from peewee_sqlserver import MssqlDatabase

    db = MssqlDatabase('MyDatabase', server='localhost')

    # Context manager (auto-commit/rollback)
    with db.atomic():
        User.create(username='user1', email='user1@example.com')
        Post.create(title='Hello', content='World', author=user)

    # Manual transaction
    db.begin()
    try:
        User.create(username='user1', email='user1@example.com')
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Savepoints
    with db.atomic():
        user = User.create(username='user1', email='user1@example.com')
        with db.atomic():
            # This can be rolled back independently
            Post.create(title='Hello', content='World', author=user)

LIMIT and Pagination
====================

SQL Server uses ``TOP`` instead of ``LIMIT``. The adapter handles this
automatically:

.. code-block:: python

    # LIMIT is converted to TOP
    query = Product.select().limit(10)
    # SQL: SELECT TOP 10 * FROM products

    # LIMIT with ORDER BY
    query = Product.select().order_by(Product.price).limit(10)
    # SQL: SELECT TOP 10 * FROM products ORDER BY price

    # LIMIT with OFFSET uses FETCH NEXT (SQL Server 2012+)
    query = Product.select().order_by(Product.price).offset(20).limit(10)
    # SQL: SELECT * FROM products ORDER BY price
    #      OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY

    # LIMIT with WHERE
    query = Product.select().where(Product.price > 100).limit(5)
    # SQL: SELECT TOP 5 * FROM products WHERE price > 100

.. note::

    - ``TOP`` is used when there's no offset
    - ``OFFSET/FETCH NEXT`` is used with offset (requires SQL Server 2012+)
    - ``OFFSET/FETCH NEXT`` requires ``ORDER BY`` - if no order is specified,
      the adapter adds ``ORDER BY (SELECT NULL)``
    - For SQL Server 2005 and earlier, use ``TOP`` without offset

Table Hints
===========

SQL Server table hints are supported for read performance optimization:

.. code-block:: python

    from peewee_sqlserver import MSSQL_NOLOCK, MSSQL_UPDLOCK, MSSQL_HOLDLOCK

    # Simple NOLOCK hint (avoids locks for reads)
    query = User.select().nolock()

    # Custom hints
    query = User.select().hint(MSSQL_NOLOCK)
    query = User.select().hint(MSSQL_NOLOCK, MSSQL_UPDLOCK)

    # Available hints:
    # MSSQL_NOLOCK           - Read uncommitted (no shared locks)
    # MSSQL_UPDLOCK          - Update locks
    # MSSQL_HOLDLOCK         - Hold locks until transaction completes
    # MSSQL_READPAST         - Skip locked rows
    # MSSQL_XLOCK            - Exclusive locks
    # MSSQL_PAGLOCK          - Page locks
    # MSSQL_TABLOCK          - Table lock
    # MSSQL_TABLOCKX         - Exclusive table lock
    # MSSQL_READUNCOMMITTED  - Same as NOLOCK
    # MSSQL_READCOMMITTED    - Default isolation level
    # MSSQL_REPEATABLEREAD   - Repeatable read isolation
    # MSSQL_SERIALIZABLE     - Serializable isolation

    # Use with queries
    active_users = (User.select()
                    .where(User.is_active == True)
                    .nolock()
                    .order_by(User.username))

Connection Pooling
==================

.. code-block:: python

    from peewee_sqlserver import PooledMssqlDatabase

    db = PooledMssqlDatabase(
        'MyDatabase',
        server='host.example.com',
        max_connections=20,      # Maximum connections in pool
        stale_timeout=300,       # Close stale connections after 300s
        timeout=30               # Wait up to 30s for available connection
    )

    # Pool is managed automatically
    # Connections are reused across requests

Async Support
=============

.. code-block:: python

    import asyncio
    from peewee_sqlserver import AsyncMssqlDatabase

    async def main():
        db = AsyncMssqlDatabase(
            'MyDatabase',
            server='host.example.com',
            pool_size=10,
            pool_min_size=1,
            acquire_timeout=10,
            enable_mars=True  # Default: True - prevents "connection busy" errors
        )

        async with db:
            # Connect
            await db.connect()

            # Execute queries
            await db.aexecute_sql('SELECT 1')

            # Close
            await db.close()

    asyncio.run(main())

    # Or with context manager
    async def main():
        async with AsyncMssqlDatabase('MyDatabase', server='localhost') as db:
            # Use database
            pass

Important: MARS Support
-----------------------

The async adapter automatically enables **MARS** (Multiple Active Result Sets)
to prevent the common ``pyodbc.Error: connection is busy with results of
another command`` error.

What is MARS?
^^^^^^^^^^^^^

MARS allows multiple active result sets on a single database connection.
Without MARS, SQL Server requires all results from one query to be consumed
before executing another query on the same connection.

In async code, this often causes errors when:

- Executing multiple queries in sequence without consuming results
- Using ``joinedload()`` or other lazy-loading patterns
- Running queries inside loops or conditional blocks

The async adapter handles this automatically by:

1. Enabling MARS by default (``Mars_Connection=yes``)
2. Properly closing cursors after each query
3. Tracking active cursors and cleaning them up

.. code-block:: python

    # MARS is enabled by default (recommended)
    db = AsyncMssqlDatabase('MyDatabase', server='localhost')

    # Or explicitly control MARS
    db = AsyncMssqlDatabase(
        'MyDatabase',
        server='localhost',
        enable_mars=True  # Default: True
    )

    # Disable MARS if you have specific requirements
    db = AsyncMssqlDatabase(
        'MyDatabase',
        server='localhost',
        enable_mars=False  # Not recommended
    )

If you still encounter connection busy errors, add MARS to your connection
string explicitly:

.. code-block:: python

    db = AsyncMssqlDatabase(
        'MyDatabase',
        connection_string=(
            'DRIVER={ODBC Driver 18 for SQL Server};'
            'SERVER=localhost;'
            'DATABASE=MyDatabase;'
            'Mars_Connection=yes'
        )
    )

Data Types
==========

MSSQL-specific data types are supported:

.. code-block:: python

    from peewee import Model
    from peewee_sqlserver import MssqlDatabase

    class MyModel(Model):
        # Standard types
        bool_field = BooleanField()          # tinyint
        int_field = IntegerField()           # int
        big_int = BigIntegerField()          # bigint
        string = CharField()                 # nvarchar
        text = TextField()                   # nvarchar(max)
        blob = BlobField()                   # varbinary
        datetime = DateTimeField()           # datetime2
        date = DateField()                   # date
        time = TimeField()                   # time
        decimal = DecimalField()             # decimal
        float = FloatField()                 # float
        uuid = UUIDField()                   # nchar(40)

        # MSSQL-specific types
        money = CharField()                  # money (use CharField for precision)
        unique_id = UUIDField()              # uniqueidentifier
        xml_field = TextField()              # xml
        bit_field = BooleanField()           # bit

Table Introspection
===================

.. code-block:: python

    from peewee_sqlserver import MssqlDatabase

    db = MssqlDatabase('MyDatabase', server='localhost')

    # Get all tables
    tables = db.get_tables()
    tables_in_schema = db.get_tables(schema='dbo')

    # Get table columns
    columns = db.get_columns('users')
    # Returns: [ColumnMetadata(name, data_type, null, table, default, is_pk)]

    # Get indexes
    indexes = db.get_indexes('users')
    # Returns: [IndexMetadata(name, sql, columns, unique, table)]

    # Get primary keys
    pks = db.get_primary_keys('users')

    # Get foreign keys
    fks = db.get_foreign_keys('posts')
    # Returns: [ForeignKeyMetadata(name, src_table, src_column, dest_table, dest_column)]

    # Check if sequence exists
    exists = db.sequence_exists('users_id_seq')

Legacy DateTime Support
=======================

For SQL Server 2005 and earlier:

.. code-block:: python

    from peewee_sqlserver import MssqlDatabase

    db = MssqlDatabase(
        'MyDatabase',
        server='localhost',
        use_legacy_datetime=True
    )
    # datetime -> datetime
    # date -> nvarchar(15)
    # time -> nvarchar(10)

Error Handling
==============

.. code-block:: python

    from peewee import IntegrityError
    from peewee_sqlserver import MssqlDatabase

    db = MssqlDatabase('MyDatabase', server='localhost')

    try:
        User.create(username='duplicate', email='test@example.com')
        User.create(username='duplicate', email='test@example.com')  # Duplicate
    except IntegrityError as e:
        print(f"Duplicate key error: {e}")

    # Database errors
    from peewee import DatabaseError, OperationalError

    try:
        db.execute_sql('INVALID SQL')
    except DatabaseError as e:
        print(f"Database error: {e}")

Configuration Reference
=======================

MssqlDatabase Parameters
------------------------

- ``database`` - Database name
- ``server`` - Server hostname or IP
- ``user`` - Username (pymssql)
- ``password`` - Password (pymssql)
- ``trusted_connection`` - Use Windows authentication (pyodbc)
- ``driver`` - ODBC driver name (pyodbc, default: 'ODBC Driver 18 for SQL Server')
- ``connection_string`` - Full ODBC connection string (pyodbc)
- ``use_legacy_datetime`` - Use legacy datetime types (SQL Server 2005)
- ``autoconnect`` - Auto-connect on first query (default: True)
- ``thread_safe`` - Thread-safe connections (default: True)

PooledMssqlDatabase Additional Parameters
-----------------------------------------

- ``max_connections`` - Maximum pool size (default: 20)
- ``stale_timeout`` - Close stale connections after N seconds (default: None)
- ``timeout`` - Wait timeout for available connection (default: None)

AsyncMssqlDatabase Additional Parameters
----------------------------------------

- ``pool_size`` - Maximum pool size (default: 10)
- ``pool_min_size`` - Minimum pool size (default: 1)
- ``acquire_timeout`` - Timeout for acquiring connection (default: 10)

JSON Support
============

SQL Server 2016+ has native JSON support. Use ``JsonField`` to store and query JSON data:

.. code-block:: python

    from peewee import Model, CharField
    from peewee_sqlserver import MssqlDatabase, JsonField

    db = MssqlDatabase('MyDatabase', server='localhost')

    class User(Model):
        name = CharField()
        data = JsonField(default={})

        class Meta:
            database = db

    # Create with JSON data
    User.create(name='John', data={'age': 30, 'city': 'NYC'})

    # Query using JSON path
    users = User.select().where(User.data['name'] == 'John')
    users = User.select().where(User.data['age'] > 25)

    # Access nested values
    users = User.select().where(User.data['address']['city'] == 'NYC')

    # Update JSON values
    user = User.get_by_id(1)
    user.data['age'] = 31
    user.save()

XML Support
===========

Use ``XmlField`` for SQL Server XML data type:

.. code-block:: python

    from peewee_sqlserver import XmlField

    class Config(Model):
        settings = XmlField()

        class Meta:
            database = db

    # Query using XPath
    configs = Config.select().where(
        Config.settings.query('/root/element') == 'value'
    )

    # Extract value
    configs = Config.select().where(
        Config.settings.value('/root/@attr', 'nvarchar(100)') == 'test'
    )

    # Check existence
    configs = Config.select().where(
        Config.settings.exist('/root/element')
    )

Computed Columns
================

SQL Server supports computed (calculated) columns:

.. code-block:: python

    from peewee_sqlserver import ComputedField

    class OrderItem(Model):
        price = FloatField()
        quantity = IntegerField()
        total = ComputedField('price * quantity', persisted=True)

        class Meta:
            database = db

    # The 'total' column is automatically calculated
    item = OrderItem.create(price=10.0, quantity=5)
    print(item.total)  # 50.0

MERGE / Upsert
===============

SQL Server uses ``MERGE`` for upsert operations (INSERT or UPDATE):

.. code-block:: python

    from peewee_sqlserver import Merge, merge

    # Using Merge class
    merge_op = (Merge(target=User, source=staging)
                .on(User.id == staging.id)
                .when_matched_then_update(
                    name=staging.name,
                    email=staging.email
                )
                .when_not_matched_then_insert(
                    id=staging.id,
                    name=staging.name,
                    email=staging.email
                ))
    merge_op.execute()

    # Using convenience function
    merge(
        target=User,
        source=staging,
        on=User.id == staging.id,
        update={User.name: staging.name},
        insert={User.id: staging.id, User.name: staging.name}
    ).execute()

    # Simple single-row upsert
    upsert = UpsertQuery(
        model=User,
        source={'id': 1, 'name': 'John', 'email': 'john@example.com'},
        key_field='id'
    )
    upsert.execute()

Sequences
=========

SQL Server sequences for generating unique IDs:

.. code-block:: python

    from peewee_sqlserver import Sequence, next_value, create_sequence

    # Create a sequence
    user_seq = create_sequence('user_id_seq', start_with=1, increment_by=1)
    user_seq.create(db)

    # Get next value
    next_id = user_seq.next_value(db)

    # Use in queries
    query = User.select().where(User.id == next_value('user_id_seq'))

    # With ORDER BY for distributed sequences
    next_id = user_seq.next_value(db, over='created_at')

    # Reset sequence
    user_seq.reset(db, value=1)

    # Drop sequence
    user_seq.drop(db)

Schema Migrations
=================

Lightweight schema migrations for SQL Server:

.. code-block:: python

    from peewee_sqlserver import MSSQLMigrator, migrate

    db = MssqlDatabase('MyDatabase', server='localhost')
    migrator = MSSQLMigrator(db)

    # Add a column
    migrate(
        migrator.add_column('users', 'phone', CharField(max_length=20, null=True))
    )

    # Drop a column
    migrate(
        migrator.drop_column('users', 'phone')
    )

    # Rename a column
    migrate(
        migrator.rename_column('users', 'name', 'full_name')
    )

    # Add an index
    migrate(
        migrator.add_index('users', ('email',), unique=True)
    )

    # Drop an index
    migrate(
        migrator.drop_index('users', 'ix_users_email')
    )

    # Add NOT NULL constraint
    migrate(
        migrator.add_not_null('users', 'email')
    )

    # Multiple operations at once
    migrate(
        migrator.add_column('posts', 'title', CharField(max_length=200)),
        migrator.add_column('posts', 'content', TextField()),
        migrator.add_index('posts', ('title',)),
    )

Full-Text Search
================

SQL Server full-text search capabilities:

.. code-block:: python

    from peewee_sqlserver import contains, freetext, contains_table

    # CONTAINS - exact word matching
    articles = Article.select().where(
        contains(Article.content, 'database')
    )

    # CONTAINS with multiple terms
    articles = Article.select().where(
        contains(Article.content, 'database AND server')
    )

    # CONTAINS with phrase
    articles = Article.select().where(
        contains(Article.content, '"SQL Server"')
    )

    # CONTAINS with prefix
    articles = Article.select().where(
        contains(Article.content, 'dat*')
    )

    # FREETEXT - meaning-based search
    articles = Article.select().where(
        freetext(Article.content, 'database performance tuning')
    )

    # CONTAINSTABLE - ranked results
    from peewee_sqlserver import contains_table
    from peewee import SQL

    query = (Article
             .select(Article, contains_table.rank.alias('rank'))
             .join(contains_table(Article, ('title', 'content'), 'database'))
             .order_by(SQL('rank').desc())
             .limit(10))

Locking Hints
=============

SQL Server table hints for concurrency control:

.. code-block:: python

    from peewee_sqlserver import MSSQL_NOLOCK, MSSQL_HOLDLOCK, MSSQL_UPDLOCK

    # NOLOCK - read uncommitted
    query = User.select().nolock()

    # Multiple hints
    query = User.select().hint(MSSQL_NOLOCK, MSSQL_UPDLOCK)

    # HOLDLOCK - serializable isolation
    query = User.select().hint(MSSQL_HOLDLOCK)

    # Available hints:
    # MSSQL_NOLOCK, MSSQL_UPDLOCK, MSSQL_HOLDLOCK
    # MSSQL_READPAST, MSSQL_XLOCK, MSSQL_PAGLOCK
    # MSSQL_TABLOCK, MSSQL_TABLOCKX
    # MSSQL_READUNCOMMITTED, MSSQL_READCOMMITTED
    # MSSQL_REPEATABLEREAD, MSSQL_SERIALIZABLE

Changelog
=========

1.0.0
-----

- Initial release of modularized peewee-mssql
- Support for pymssql and pyodbc drivers
- Async support via aioodbc
- Connection pooling
- Table hints (NOLOCK, UPDLOCK, etc.)
- TOP/OFFSET pagination
- Full MSSQL data type support
- Table introspection

Troubleshooting
===============

"Connection is busy with results of another command"
-----------------------------------------------------

This error occurs when a previous query's results weren't consumed before
executing a new query. The async adapter handles this automatically by:

1. Enabling MARS (Multiple Active Result Sets) by default
2. Properly closing cursors after each query
3. Tracking active cursors and cleaning them up

If you still see this error:

.. code-block:: python

    # Ensure MARS is enabled
    db = AsyncMssqlDatabase('MyDatabase', server='localhost', enable_mars=True)

    # Or add MARS to your connection string
    db = AsyncMssqlDatabase(
        'MyDatabase',
        connection_string='DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=MyDatabase;Mars_Connection=yes'
    )

"Driver not found" error
-------------------------

If you see ``IM002`` or ``Data source name not found`` error:

1. Install the ODBC driver for your platform
2. Check installed drivers: ``odbcinst -q -d``

.. code-block:: console

    # Ubuntu/Debian
    $ sudo apt-get install msodbcsql18

    # RHEL/CentOS
    $ sudo yum install msodbcsql18

    # macOS (Homebrew)
    $ brew install microsoft-mssql-release

Connection timeout issues
-------------------------

If connections time out:

.. code-block:: python

    db = MssqlPyodbcDatabase(
        'MyDatabase',
        server='host.example.com',
        connection_timeout=30,  # seconds
        query_timeout=60,       # seconds
    )

License
=======

MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
