import click
from datetime import datetime, timezone
from iceberg_navigator.aws.glue import GlueCatalog
from iceberg_navigator.utils.display import show_snapshot_details


@click.command(name="find-snapshot")
@click.option("--table", required=True, help="Table identifier, e.g. db.table")
@click.option("--at", required=True,
              help="Datetime in ISO 8601 format, e.g. 2026-06-12T05:20:00+00:00")
def find_snapshot(table, at):
    """Find the snapshot that was current at a given datetime."""
    try:
        target_dt = datetime.fromisoformat(at)
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=timezone.utc)
        target_ms = int(target_dt.timestamp() * 1000)
    except ValueError:
        click.echo(f"Invalid datetime format: {at}")
        click.echo("Use ISO 8601 format, e.g. 2026-06-12T05:20:00+00:00")
        return

    glue = GlueCatalog()
    snapshots = glue.list_snapshots(table)
    if not snapshots:
        click.echo("No snapshots found.")
        return

    # Sort by timestamp_ms ascending, return the last snapshot at or before target_ms
    sorted_snaps = sorted(snapshots, key=lambda s: s["timestamp"])
    candidate = None
    for snap in sorted_snaps:
        if snap["timestamp"] <= target_ms:
            candidate = snap
        else:
            break

    if candidate is None:
        click.echo(f"No snapshot found at or before {at}.")
        first_ts = datetime.utcfromtimestamp(sorted_snaps[0]["timestamp"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ")
        click.echo(f"Earliest snapshot: {first_ts}")
        return

    # Show details in the same format as the show command
    result = glue.show_snapshot(table, candidate["snapshot_id"])
    if result is None or "error" in result:
        click.echo("Failed to retrieve snapshot details.")
        return

    click.echo(f"Snapshot at {at}:\n")
    show_snapshot_details(result)
