import click
from iceberg_navigator.aws.glue import GlueCatalog
from iceberg_navigator.utils.display import format_snapshots_table


@click.command("list")
@click.option("--table", required=True, help="Table identifier, e.g. db.table")
@click.option("--threshold", default=None, type=float,
              help="Flag rows where record count changes by more than this % (e.g. 50)")
def list_snapshots(table, threshold):
    """List all snapshots with record change tracking."""
    glue = GlueCatalog()
    snapshots = glue.list_snapshots(table)
    if not snapshots:
        click.echo("No snapshots found.")
        return

    table_str = format_snapshots_table(snapshots, threshold=threshold)
    click.echo(table_str)
