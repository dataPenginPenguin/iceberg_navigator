import click
from iceberg_navigator.aws.glue import GlueCatalog
from iceberg_navigator.utils.display import show_snapshot_details

@click.command(name="show")
@click.argument("snapshot_id")
@click.option('--table', required=True, help="Table identifier, e.g. db.table")
def show_snapshot(table, snapshot_id):
    glue_catalog = GlueCatalog()
    snapshot = glue_catalog.show_snapshot(table, snapshot_id)
    if snapshot is None or "error" in snapshot:
        click.echo(f"Snapshot {snapshot_id} not found in table {table}.")
        return

    show_snapshot_details(snapshot)