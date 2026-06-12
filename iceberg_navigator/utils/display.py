from tabulate import tabulate
from datetime import datetime
import click
import networkx as nx
import matplotlib.pyplot as plt


# ──────────────────────────────────────────
# list
# ──────────────────────────────────────────

def format_snapshots_table(snapshots, threshold=None):
    headers = ["", "Snapshot ID", "Timestamp", "Operation", "Parent Snapshot ID",
               "Total Size (MB)", "Record Count", "Change (%)"]
    rows = []
    for snap in snapshots:
        ts = datetime.utcfromtimestamp(snap["timestamp"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ")
        change_pct = snap.get("record_change_pct")

        if change_pct is None:
            change_str = "-"
            flag = ""
        else:
            change_str = f"{change_pct:+.1f}%"
            flag = ""
            if threshold is not None and abs(change_pct) >= threshold:
                flag = "⚠"

        rows.append([
            flag,
            snap["snapshot_id"],
            ts,
            str(snap.get("operation") or "").replace("Operation.", ""),
            snap["parent_id"] or "null",
            format_number(snap["total_size_mb"]),
            format_number(snap["record_count"]),
            change_str,
        ])
    colalign = ("center", "left", "left", "left", "left", "right", "right", "right")
    return tabulate(rows, headers=headers, tablefmt="github", floatfmt=".2f", colalign=colalign)


# ──────────────────────────────────────────
# show
# ──────────────────────────────────────────

def show_snapshot_details(snapshot):
    ts = datetime.utcfromtimestamp(snapshot["timestamp"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ")

    click.echo(f"Table: {snapshot.get('table', 'Unknown')}\n")
    click.echo(f"Snapshot ID: {snapshot['snapshot_id']}")
    click.echo(f"Timestamp: {ts}")
    click.echo(f"Operation: {snapshot['operation']}")
    click.echo(f"Parent Snapshot ID: {snapshot['parent_id'] or 'None'}")
    click.echo(f"Manifest List: {snapshot['manifest_list']}\n")

    click.echo("Schema:")
    for col in snapshot["schema"]:
        click.echo(f"  {col}")
    click.echo("")

    click.echo("Summary:")
    summary_keys = [
        "added-data-files",
        "total-equality-deletes",
        "added-records",
        "total-position-deletes",
        "added-files-size",
        "total-delete-files",
        "total-files-size",
        "total-data-files",
        "total-records",
    ]
    summary = snapshot.get("summary", {})
    printed_any = False
    for key in summary_keys:
        value = summary.get(key)
        if value is not None:
            click.echo(f"  {key}: {value}")
            printed_any = True
    if not printed_any:
        click.echo("  (No summary data)")


# ──────────────────────────────────────────
# compare
# ──────────────────────────────────────────

def compare_snapshot(result):
    click.echo("-" * 40)
    click.echo("Parent Snapshot")
    click.echo("-" * 40)
    click.echo(f"ID:         {result['parent_snapshot_id']}")
    click.echo(f"File Size:  {format_mb(result['parent_size'])} MB")
    click.echo(f"Records:    {format_number(result['parent_records'])}")
    click.echo("")

    click.echo("-" * 40)
    click.echo("Current Snapshot")
    click.echo("-" * 40)
    click.echo(f"ID:         {result['current_snapshot_id']}")
    click.echo(f"File Size:  {format_mb(result['current_size'])} MB")
    click.echo(f"Records:    {format_number(result['current_records'])}")
    click.echo("")

    click.echo("=" * 40)
    click.echo("Summary")
    click.echo("=" * 40)
    click.echo(f"Added Records:   {format_number(result['added'])}")
    click.echo(f"Deleted Records: {format_number(result['deleted'])}")
    click.echo("")


# ──────────────────────────────────────────
# diagnose
# ──────────────────────────────────────────

def show_diagnose(snapshots, threshold):
    click.echo(f"Anomaly threshold: ±{threshold:.0f}% record change\n")

    sorted_snaps = sorted(snapshots, key=lambda s: s["timestamp"])
    anomalies = []

    for snap in sorted_snaps:
        ts = datetime.utcfromtimestamp(snap["timestamp"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ")
        change_pct = snap.get("record_change_pct")
        op = str(snap.get("operation") or "-").replace("Operation.", "")

        if change_pct is None:
            flag = "  "
            change_str = "-"
        else:
            change_str = f"{change_pct:+.1f}%"
            if abs(change_pct) >= threshold:
                flag = "⚠ "
                anomalies.append(snap)
            else:
                flag = "  "

        click.echo(f"{flag}{ts}  {op:<12}  records: {format_number(snap['record_count']):>12}  change: {change_str:>8}  [{snap['snapshot_id']}]")

    click.echo("")
    if anomalies:
        click.echo(f"{'=' * 60}")
        click.echo(f"⚠  {len(anomalies)} anomaly(ies) detected (threshold: ±{threshold:.0f}%)")
        click.echo(f"{'=' * 60}")
        for snap in anomalies:
            ts = datetime.utcfromtimestamp(snap["timestamp"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ")
            change_pct = snap["record_change_pct"]
            click.echo(f"  {ts}  {str(snap.get("operation") or "").replace("Operation.", ""):<12}  {change_pct:+.1f}%  [{snap["snapshot_id"]}]")
            click.echo(f"  → Run: iceberg-navigator compare {snap['snapshot_id']} --table <db.table>")
            click.echo("")
    else:
        click.echo(f"No anomalies detected (threshold: ±{threshold:.0f}%)")


# ──────────────────────────────────────────
# schema-diff
# ──────────────────────────────────────────

def show_schema_diff(result):
    from_id = result["parent_snapshot_id"]
    to_id = result["snapshot_id"]
    click.echo(f"Schema diff: schema_id {from_id} -> {to_id}\n")

    added = result.get("added", {})
    removed = result.get("removed", {})
    type_changed = result.get("type_changed", {})
    before_cols = result.get("before_cols", {})
    after_cols = result.get("after_cols", {})

    if not added and not removed and not type_changed:
        click.echo("No schema changes detected.")
        return

    all_col_names = list(dict.fromkeys(list(before_cols.keys()) + list(after_cols.keys())))
    w = max((len(n) for n in all_col_names), default=10) + 2

    click.echo(f"  {'Column':<{w}}  {'Before':<20}  {'After':<20}  Change")
    click.echo("  " + "-" * (w + 48))

    for name in all_col_names:
        before_type = before_cols.get(name, "-")
        after_type = after_cols.get(name, "-")

        if name in added:
            mark = "+ ADDED"
        elif name in removed:
            mark = "- REMOVED"
        elif name in type_changed:
            mark = "~ TYPE CHANGED"
        else:
            mark = ""

        click.echo(f"  {name:<{w}}  {before_type:<20}  {after_type:<20}  {mark}")

    click.echo("")


# ──────────────────────────────────────────
# graph
# ──────────────────────────────────────────

def build_snapshot_graph(snapshots):
    G = nx.DiGraph()
    for idx, snap in enumerate(snapshots, start=1):
        op = snap.get("operation", "") or ""
        op_short = str(op).replace("Operation.", "")
        ts = datetime.utcfromtimestamp(snap["timestamp"] / 1000).strftime("%m/%d %H:%M")
        label = f"{op_short}\n{ts}"
        G.add_node(snap["snapshot_id"], label=label, operation=op_short, idx=idx,
                   timestamp=snap["timestamp"])
    for snap in snapshots:
        parent_id = snap.get("parent_id")
        if parent_id and G.has_node(parent_id):
            G.add_edge(parent_id, snap["snapshot_id"])
    return G


def draw_graph(G, output_file, snapshots):
    if len(G.nodes) == 0:
        return

    # Timeline layout: Y=timestamp (newer at top), X=branch spread
    sorted_nodes = sorted(G.nodes, key=lambda n: G.nodes[n].get("timestamp", 0))
    ts_list = [G.nodes[n]["timestamp"] for n in sorted_nodes]
    ts_min, ts_max = min(ts_list), max(ts_list)
    ts_range = ts_max - ts_min if ts_max != ts_min else 1

    # X position: spread nodes with the same timestamp bucket horizontally
    from collections import defaultdict
    ts_bucket = defaultdict(list)
    for n in sorted_nodes:
        bucket = round((G.nodes[n]["timestamp"] - ts_min) / ts_range * 100)
        ts_bucket[bucket].append(n)

    # Y axis: equal spacing by bucket index (not time normalization)
    sorted_buckets = sorted(ts_bucket.keys())
    pos = {}
    for y_idx, bucket in enumerate(sorted_buckets):
        nodes = ts_bucket[bucket]
        for i, n in enumerate(nodes):
            x = (i - (len(nodes) - 1) / 2) * 0.4
            pos[n] = (x, y_idx)

    # Color by operation type
    color_map = {"APPEND": "#4C9BE8", "DELETE": "#E85C5C", "REPLACE": "#56C27A"}
    node_colors = [
        color_map.get(G.nodes[n].get("operation", ""), "#AAAAAA")
        for n in G.nodes
    ]

    labels = nx.get_node_attributes(G, "label")
    n = len(G.nodes)
    node_size = max(200, min(800, 8000 // n))
    font_size = max(4, min(8, 80 // n))
    max_bucket_size = max((len(v) for v in ts_bucket.values()), default=1)
    figw = max(14, max_bucket_size * 2.5)
    figh = max(8, len(ts_bucket) * 1.2)

    plt.figure(figsize=(figw, figh))
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_size, alpha=0.9)
    nx.draw_networkx_edges(G, pos, arrows=True, arrowstyle="-|>", arrowsize=10,
                           edge_color="#888888", width=0.8)
    nx.draw_networkx_labels(G, pos, labels, font_size=font_size,
                            font_weight="bold", verticalalignment="center")

    # Legend
    from matplotlib.patches import Patch
    legend = [
        Patch(color="#4C9BE8", label="APPEND"),
        Patch(color="#E85C5C", label="DELETE"),
        Patch(color="#56C27A", label="REPLACE"),
    ]
    plt.legend(handles=legend, loc="upper left", fontsize=8)
    plt.title(f"Iceberg Snapshot Lineage ({n} snapshots)")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close()


# ──────────────────────────────────────────
# helpers
# ──────────────────────────────────────────

def format_number(n):
    return f"{n:,}"


def format_mb(bytes_val):
    return f"{bytes_val / (1024 * 1024):.2f}"

# ──────────────────────────────────────────
# schema-history
# ──────────────────────────────────────────

def show_schema_history(results, table_identifier="<db.table>"):
    if not results:
        click.echo("No schema changes found.")
        return

    click.echo(f"{len(results)} schema change(s) detected:\n")
    for r in results:
        click.echo(f"{'=' * 60}")
        click.echo(f"Schema ID   : {r['parent_schema_id']} -> {r['schema_id']}")
        click.echo(f"Timestamp   : {r['timestamp']}")
        click.echo("")

        if r['added']:
            click.echo("  Added columns:")
            for name, dtype in r['added'].items():
                click.echo(f"    + {name}: {dtype}")

        if r['removed']:
            click.echo("  Removed columns:")
            for name, dtype in r['removed'].items():
                click.echo(f"    - {name}: {dtype}")

        if r['type_changed']:
            click.echo("  Type changes:")
            for name, change in r['type_changed'].items():
                click.echo(f"    ~ {name}: {change['from']} -> {change['to']}")

        click.echo("")
        click.echo(f"  -> Run: iceberg-navigator schema-diff {r['schema_id']} --table {table_identifier}")
        click.echo("")

