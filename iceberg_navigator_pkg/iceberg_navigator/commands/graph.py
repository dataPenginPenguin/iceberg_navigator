import click
from iceberg_navigator.aws.glue import GlueCatalog
from iceberg_navigator.utils.display import build_snapshot_graph, draw_graph


@click.command("graph")
@click.option("--table", required=True, help="Table identifier, e.g. db.table")
@click.option("--output", default="snapshot_graph.png", show_default=True,
              help="Output file path")
@click.option("--limit", default=None, type=int,
              help="Show only the latest N snapshots (recommended for large tables)")
def graph_snapshots(table, output, limit):
    """Visualize snapshot lineage as a DAG."""
    glue = GlueCatalog()
    snapshots = glue.list_snapshots(table)
    if not snapshots:
        click.echo("No snapshots found.")
        return

    # Sort by timestamp ascending, apply limit if specified
    snapshots = sorted(snapshots, key=lambda s: s["timestamp"])
    if limit:
        snapshots = snapshots[-limit:]
        click.echo(f"Showing latest {limit} snapshots.")

    G = build_snapshot_graph(snapshots)
    draw_graph(G, output, snapshots)
    click.echo(f"Snapshot graph saved to {output}")
