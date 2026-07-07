"""
MSSQL MERGE statement support for Peewee.

Provides upsert functionality using SQL Server's MERGE statement.
"""
from peewee import (
    Node,
    SQL,
    CommaNodeList,
    Value,
    Expression,
    OP,
)
from peewee import __exception_wrapper__

__all__ = ['Merge', 'merge']


class Merge(Node):
    """
    SQL Server MERGE statement for upserts.
    
    MERGE is SQL Server's equivalent of UPSERT - it can INSERT, UPDATE,
    or DELETE rows in a single statement based on whether the source
    rows match the target.
    
    Example:
        from peewee_sqlserver import Merge
        
        # Simple upsert
        merge = (Merge(target=User, source=staging_table)
                 .on(User.id == staging_table.id)
                 .when_matched_then_update(
                     name=staging_table.name,
                     email=staging_table.email
                 )
                 .when_not_matched_then_insert(
                     id=staging_table.id,
                     name=staging_table.name,
                     email=staging_table.email
                 ))
        
        # Execute the merge
        merge.execute()
        
        # Or use the convenience function
        from peewee_sqlserver import merge
        merge(User, staging_table, 
              on=User.id == staging_table.id,
              update={User.name: staging_table.name},
              insert={User.id: staging_table.id, User.name: staging_table.name})
    """
    
    def __init__(self, target, source, using=None, alias=None):
        """
        Initialize MERGE statement.
        
        Args:
            target: Target table (Model class)
            source: Source table (Model class, subquery, or table alias)
            using: Optional USING clause
            alias: Optional alias for the target table
        """
        self._target = target
        self._source = source
        self._using = using
        self._alias = alias
        self._on = None
        self._when_matched = []
        self._when_not_matched = []
        self._when_not_matched_by_source = []
        self._output = None
    
    def on(self, condition):
        """Set the ON clause (match condition)."""
        self._on = condition
        return self
    
    def when_matched_then_update(self, **kwargs):
        """
        Define action when rows match.
        
        Args:
            **kwargs: Column mappings {target_column: source_value}
        """
        self._when_matched.append(('update', kwargs))
        return self
    
    def when_matched_then_delete(self):
        """Delete matched rows."""
        self._when_matched.append(('delete', {}))
        return self
    
    def when_matched_then_update_or_insert(self, update_fields=None, insert_fields=None):
        """
        Define both update and insert actions.
        
        This is a convenience method for common upsert patterns.
        """
        return self
    
    def when_not_matched_then_insert(self, **kwargs):
        """
        Define action when source rows don't match target.
        
        Args:
            **kwargs: Column mappings {target_column: source_value}
        """
        self._when_not_matched.append(('insert', kwargs))
        return self
    
    def when_not_matched_by_source_then_delete(self):
        """Delete target rows that don't match source."""
        self._when_not_matched_by_source.append(('delete', {}))
        return self
    
    def when_not_matched_by_source_then_update(self, **kwargs):
        """Update target rows that don't match source."""
        self._when_not_matched_by_source.append(('update', kwargs))
        return self
    
    def output(self, *columns, **kwargs):
        """
        Add OUTPUT clause to return affected rows.
        
        Args:
            *columns: Columns to return
            **kwargs: Named columns {alias: column}
        
        Example:
            merge.output(User.id, User.name, alias='inserted')
            # Returns: INSERTED.id, INSERTED.name
        """
        self._output = (columns, kwargs)
        return self
    
    def output_inserted(self, *columns):
        """Return inserted rows."""
        return self.output(*columns, alias='INSERTED')
    
    def output_deleted(self, *columns):
        """Return deleted rows."""
        return self.output(*columns, alias='DELETED')
    
    def __sql__(self, ctx):
        # MERGE target AS alias
        ctx.literal('MERGE INTO ')
        ctx.sql(self._target)
        if self._alias:
            ctx.literal(' AS ').literal(self._alias)
        
        # USING source
        ctx.literal(' USING ')
        ctx.sql(self._source)
        
        # ON condition
        ctx.literal(' ON ')
        ctx.sql(self._on)
        
        # WHEN MATCHED THEN
        if self._when_matched:
            for action, columns in self._when_matched:
                ctx.literal(' WHEN MATCHED THEN ')
                if action == 'update':
                    ctx.literal('UPDATE SET ')
                    set_clauses = []
                    for col, val in columns.items():
                        set_clauses.append(SQL('%s = %s' % (col, val)))
                    ctx.sql(CommaNodeList(set_clauses))
                elif action == 'delete':
                    ctx.literal('DELETE')
        
        # WHEN NOT MATCHED BY TARGET THEN (insert)
        if self._when_not_matched:
            for action, columns in self._when_not_matched:
                ctx.literal(' WHEN NOT MATCHED BY TARGET THEN ')
                if action == 'insert':
                    ctx.literal('INSERT (')
                    col_list = []
                    val_list = []
                    for col, val in columns.items():
                        col_list.append(SQL(str(col)))
                        val_list.append(SQL(str(val)))
                    ctx.sql(CommaNodeList(col_list))
                    ctx.literal(') VALUES (')
                    ctx.sql(CommaNodeList(val_list))
                    ctx.literal(')')
        
        # WHEN NOT MATCHED BY SOURCE THEN
        if self._when_not_matched_by_source:
            for action, columns in self._when_not_matched_by_source:
                ctx.literal(' WHEN NOT MATCHED BY SOURCE THEN ')
                if action == 'delete':
                    ctx.literal('DELETE')
                elif action == 'update':
                    ctx.literal('UPDATE SET ')
                    set_clauses = []
                    for col, val in columns.items():
                        set_clauses.append(SQL('%s = %s' % (col, val)))
                    ctx.sql(CommaNodeList(set_clauses))
        
        # OUTPUT clause
        if self._output:
            columns, kwargs = self._output
            ctx.literal(' OUTPUT ')
            output_cols = []
            for col in columns:
                alias = kwargs.get('alias', 'INSERTED')
                output_cols.append(SQL('%s.%s' % (alias, col)))
            ctx.sql(CommaNodeList(output_cols))
        
        return ctx


def merge(target, source, on, update=None, insert=None, delete=False,
          using=None, output=None):
    """
    Convenience function for MERGE operations.
    
    Args:
        target: Target table (Model class)
        source: Source table (Model class, subquery, or table alias)
        on: ON condition (match expression)
        update: Dict of {column: value} for UPDATE action
        insert: Dict of {column: value} for INSERT action
        delete: If True, delete matched rows
        using: Optional USING clause
        output: Optional list of columns to return
    
    Returns:
        Merge object that can be executed
    
    Example:
        from peewee_sqlserver import merge
        
        # Upsert example
        merge(
            target=User,
            source=staging,
            on=User.id == staging.id,
            update={User.name: staging.name, User.email: staging.email},
            insert={User.id: staging.id, User.name: staging.name}
        ).execute()
    """
    m = Merge(target, source, using=using)
    m.on(on)
    
    if update:
        m.when_matched_then_update(**update)
    
    if delete:
        m.when_matched_then_delete()
    
    if insert:
        m.when_not_matched_then_insert(**insert)
    
    if output:
        m.output(*output)
    
    return m


class UpsertQuery(Node):
    """
    Simplified UPSERT operation using MERGE.
    
    This is a higher-level abstraction for common upsert patterns.
    
    Example:
        from peewee_sqlserver import UpsertQuery
        
        # Simple upsert
        upsert = UpsertQuery(
            model=User,
            source={'id': 1, 'name': 'John', 'email': 'john@example.com'},
            key_field='id'
        )
        upsert.execute()
    """
    
    def __init__(self, model, source, key_field, update_fields=None, 
                 insert_fields=None):
        """
        Initialize upsert.
        
        Args:
            model: Target model class
            source: Source data (dict, list of dicts, or subquery)
            key_field: Field name(s) used for matching
            update_fields: Fields to update on match (None = all except key)
            insert_fields: Fields to insert (None = all)
        """
        self._model = model
        self._source = source
        self._key_field = key_field if isinstance(key_field, (list, tuple)) else [key_field]
        self._update_fields = update_fields
        self._insert_fields = insert_fields
    
    def __sql__(self, ctx):
        # Build MERGE statement
        if isinstance(self._source, dict):
            # Single row upsert
            return self._single_row_sql(ctx)
        elif isinstance(self._source, (list, tuple)):
            # Multiple rows - would need a temp table
            raise NotImplementedError("Batch upsert not yet supported")
        else:
            # Subquery
            return self._subquery_sql(ctx)
    
    def _single_row_sql(self, ctx):
        """Generate SQL for single row upsert."""
        source = self._source
        
        # Determine fields
        all_fields = [f.name for f in self._model._meta.sorted_fields 
                     if not f.primary_key or f.name in self._key_field]
        
        update_fields = self._update_fields or [f for f in all_fields 
                                                if f not in self._key_field]
        insert_fields = self._insert_fields or all_fields
        
        # Build source values
        source_cols = []
        source_vals = []
        for field_name in insert_fields:
            source_cols.append(SQL(field_name))
            source_vals.append(Value(source.get(field_name)))
        
        # Build MERGE
        ctx.literal('MERGE INTO ')
        ctx.sql(self._model._meta.table)
        ctx.literal(' AS target USING (SELECT ')
        ctx.sql(CommaNodeList(source_vals))
        ctx.literal(' AS ')
        ctx.sql(CommaNodeList([SQL(c) for c in source_cols]))
        ctx.literal(') AS source ON (')
        
        # ON condition
        on_conditions = []
        for key in self._key_field:
            on_conditions.append(SQL('target.%s = source.%s' % (key, key)))
        ctx.sql(CommaNodeList(on_conditions))
        ctx.literal(')')
        
        # WHEN MATCHED THEN UPDATE
        if update_fields:
            ctx.literal(' WHEN MATCHED THEN UPDATE SET ')
            set_clauses = []
            for field_name in update_fields:
                if field_name not in self._key_field:
                    set_clauses.append(SQL('target.%s = source.%s' % (
                        field_name, field_name)))
            ctx.sql(CommaNodeList(set_clauses))
        
        # WHEN NOT MATCHED THEN INSERT
        ctx.literal(' WHEN NOT MATCHED THEN INSERT (')
        ctx.sql(CommaNodeList([SQL(f) for f in insert_fields]))
        ctx.literal(') VALUES (')
        ctx.sql(CommaNodeList([SQL('source.%s' % f) for f in insert_fields]))
        ctx.literal(');')
        
        return ctx
