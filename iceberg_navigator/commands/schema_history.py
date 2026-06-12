import click
from iceberg_navigator.aws.glue import GlueCatalog
from iceberg_navigator.utils.display import show_schema_history


@click.command(name="schema-history")
@click.option("--table", required=True, help="Table identifier, e.g. db.table")
def schema_history(table):
    """Show all snapshots where schema changes occurred."""
    glue = GlueCatalog()
    snapshots = glue.list_snapshots(table)
    if not snapshots:
        click.echo("No snapshots found.")
        return

    results = glue.get_schema_history(table, snapshots)
    show_schema_history(results, table_identifier=table)
