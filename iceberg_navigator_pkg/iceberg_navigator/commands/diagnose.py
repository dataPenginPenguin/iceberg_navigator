import click
from iceberg_navigator.aws.glue import GlueCatalog
from iceberg_navigator.utils.display import show_diagnose


@click.command(name="diagnose")
@click.option("--table", required=True, help="Table identifier, e.g. db.table")
@click.option("--threshold", default=50.0, show_default=True,
              help="Record count change threshold (%) to flag as anomaly")
def diagnose(table, threshold):
    """Show a timeline of operations and flag anomalies."""
    glue = GlueCatalog()
    snapshots = glue.list_snapshots(table)
    if not snapshots:
        click.echo("No snapshots found.")
        return

    show_diagnose(snapshots, threshold)
