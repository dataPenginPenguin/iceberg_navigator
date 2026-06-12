import click
from iceberg_navigator.aws.glue import GlueCatalog
from iceberg_navigator.utils.display import show_schema_diff


@click.command(name="schema-diff")
@click.argument("schema_id", type=int)
@click.option("--table", required=True, help="Table identifier, e.g. db.table")
def schema_diff(table, schema_id):
    """Show schema diff for a given schema ID (from schema-history output)."""
    glue = GlueCatalog()
    result = glue.get_schema_diff_by_id(table, schema_id)

    if result is None or "error" in result:
        msg = result.get("error") if result else "Unknown error"
        click.echo(f"Error: {msg}")
        return

    show_schema_diff(result)
