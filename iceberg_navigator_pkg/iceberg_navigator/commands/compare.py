import click
from iceberg_navigator.aws.glue import GlueCatalog
from iceberg_navigator.utils.display import compare_snapshot

@click.command(name="compare")
@click.argument("snapshot_id")
@click.option('--table', required=True, help="Table identifier, e.g. db.table")
def compare_snapshots(table, snapshot_id):
    glue_catalog = GlueCatalog()
    comparison_result = glue_catalog.compare_snapshots(table, snapshot_id)

    if comparison_result is None or "error" in comparison_result:
        click.echo(f"Snapshot {snapshot_id} not found in table {table}.")
        return

    compare_snapshot(comparison_result)