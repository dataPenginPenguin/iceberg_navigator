import click
from iceberg_navigator.commands import list as list_cmd
from iceberg_navigator.commands import show
from iceberg_navigator.commands import graph
from iceberg_navigator.commands import compare
from iceberg_navigator.commands import diagnose
from iceberg_navigator.commands import schema_diff
from iceberg_navigator.commands import find_snapshot
from iceberg_navigator.commands import schema_history


@click.group()
def main():
    """Iceberg Navigator CLI — inspect and diagnose Iceberg snapshot histories."""
    pass


main.add_command(list_cmd.list_snapshots)
main.add_command(show.show_snapshot)
main.add_command(compare.compare_snapshots)
main.add_command(graph.graph_snapshots)
main.add_command(diagnose.diagnose)
main.add_command(schema_diff.schema_diff)
main.add_command(find_snapshot.find_snapshot)
main.add_command(schema_history.schema_history)
