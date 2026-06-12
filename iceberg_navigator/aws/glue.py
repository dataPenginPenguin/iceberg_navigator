from pyiceberg.catalog import load_catalog
import boto3
import json
from datetime import datetime


class GlueCatalog:
    def __init__(self, profile_name=None, region_name=None, catalog_id="AwsDataCatalog"):
        if not region_name:
            session = boto3.Session(profile_name=profile_name)
            region_name = session.region_name
            if not region_name:
                raise ValueError("region_name Error")
        self.region_name = region_name
        self.catalog_id = catalog_id

        session = boto3.Session(profile_name=profile_name, region_name=region_name)
        self.glue_client = session.client("glue", region_name=region_name)
        self.s3_client = session.client("s3", region_name=region_name)

    def _get_catalog(self):
        conf = {
            "type": "rest",
            "uri": f"https://glue.{self.region_name}.amazonaws.com/iceberg",
            "s3.region": self.region_name,
            "rest.sigv4-enabled": "true",
            "rest.signing-name": "glue",
            "rest.signing-region": self.region_name,
        }
        return load_catalog(**conf)

    def _read_s3_json(self, s3_uri):
        """Read JSON from an S3 URI in the format s3://bucket/key"""
        s3_uri = s3_uri.replace("s3://", "")
        bucket, key = s3_uri.split("/", 1)
        response = self.s3_client.get_object(Bucket=bucket, Key=key)
        return json.loads(response["Body"].read())

    def get_table_location(self, table_identifier: str) -> str:
        database, table = table_identifier.split(".", 1)
        resp = self.glue_client.get_table(DatabaseName=database, Name=table)
        return resp["Table"]["Parameters"]["metadata_location"]

    def list_snapshots(self, table_identifier: str):
        catalog = self._get_catalog()
        namespace, table_name = table_identifier.split(".", 1)
        table = catalog.load_table(f"{namespace}.{table_name}")

        raw = []
        for snap in table.snapshots():
            total_bytes = int(snap.summary.get("total-files-size") or 0) if snap.summary else 0
            total_records = int(snap.summary.get("total-records") or 0) if snap.summary else 0
            raw.append({
                "snapshot_id": str(snap.snapshot_id),
                "timestamp": snap.timestamp_ms,
                "operation": str(snap.summary.get("operation") or "").replace("Operation.", "") if snap.summary else None,
                "parent_id": str(snap.parent_snapshot_id) if snap.parent_snapshot_id else None,
                "total_size_mb": round(total_bytes / (1024 * 1024), 2),
                "record_count": total_records,
            })

        id_to_snap = {s["snapshot_id"]: s for s in raw}
        for snap in raw:
            parent_id = snap.get("parent_id")
            if parent_id and parent_id in id_to_snap:
                parent_records = id_to_snap[parent_id]["record_count"]
                if parent_records > 0:
                    change_pct = (snap["record_count"] - parent_records) / parent_records * 100
                else:
                    change_pct = None
            else:
                change_pct = None
            snap["record_change_pct"] = change_pct

        return raw

    def show_snapshot(self, table_identifier: str, snapshot_id: str):
        catalog = self._get_catalog()
        namespace, table_name = table_identifier.split(".", 1)
        table = catalog.load_table(f"{namespace}.{table_name}")

        snap = table.snapshot_by_id(int(snapshot_id))
        if not snap:
            return {"error": f"snapshot_id {snapshot_id} not found"}

        schema_columns = []
        for idx, col in enumerate(table.schema().columns, start=1):
            requiredness = "optional" if col.optional else "required"
            schema_columns.append(f"{idx}: {col.name}: {requiredness} {col.field_type}")

        summary_dict = {}
        if snap.summary:
            summary_dict["operation"] = snap.summary.operation
            if hasattr(snap.summary, "additional_properties"):
                summary_dict.update(snap.summary.additional_properties)

        return {
            "table": table_name,
            "snapshot_id": str(snap.snapshot_id),
            "timestamp": snap.timestamp_ms,
            "operation": summary_dict.get("operation"),
            "parent_id": str(snap.parent_snapshot_id) if snap.parent_snapshot_id else None,
            "manifest_list": snap.manifest_list,
            "schema": schema_columns,
            "summary": summary_dict,
        }

    def compare_snapshots(self, table_identifier: str, snapshot_id: str):
        catalog = self._get_catalog()
        namespace, table_name = table_identifier.split(".", 1)
        table = catalog.load_table(f"{namespace}.{table_name}")

        current_snap = table.snapshot_by_id(int(snapshot_id))
        if not current_snap:
            return {"error": f"snapshot_id {snapshot_id} not found"}

        parent_snap = table.snapshot_by_id(int(current_snap.parent_snapshot_id))
        if not parent_snap:
            return {"error": "parent_snapshot not found"}

        current_size = int(current_snap.summary.get("total-files-size") or 0)
        current_records = int(current_snap.summary.get("total-records") or 0)
        parent_size = int(parent_snap.summary.get("total-files-size") or 0)
        parent_records = int(parent_snap.summary.get("total-records") or 0)

        added = current_records - parent_records if current_records > parent_records else 0
        deleted = parent_records - current_records if parent_records > current_records else 0

        return {
            "current_snapshot_id": str(current_snap.snapshot_id),
            "current_size": current_size,
            "current_records": current_records,
            "parent_snapshot_id": str(parent_snap.snapshot_id),
            "parent_size": parent_size,
            "parent_records": parent_records,
            "added": added,
            "deleted": deleted,
        }

    def get_schema_diff(self, table_identifier: str, snapshot_id: str):
        catalog = self._get_catalog()
        namespace, table_name = table_identifier.split(".", 1)
        table = catalog.load_table(f"{namespace}.{table_name}")

        current_snap = table.snapshot_by_id(int(snapshot_id))
        if not current_snap:
            return {"error": f"snapshot_id {snapshot_id} not found"}
        if not current_snap.parent_snapshot_id:
            return {"error": "no parent snapshot"}

        schema_map = {
            s.schema_id: {col.name: str(col.field_type) for col in s.columns}
            for s in table.metadata.schemas
        }

        def _schema_columns(snap):
            sid = snap.schema_id
            if sid is not None and sid in schema_map:
                return schema_map[sid]
            return {col.name: str(col.field_type) for col in table.schema().columns}

        current_cols = _schema_columns(current_snap)
        parent_snap = table.snapshot_by_id(int(current_snap.parent_snapshot_id))
        parent_cols = _schema_columns(parent_snap)

        added = {k: v for k, v in current_cols.items() if k not in parent_cols}
        removed = {k: v for k, v in parent_cols.items() if k not in current_cols}
        type_changed = {
            k: {"from": parent_cols[k], "to": current_cols[k]}
            for k in current_cols
            if k in parent_cols and current_cols[k] != parent_cols[k]
        }

        return {
            "snapshot_id": snapshot_id,
            "parent_snapshot_id": str(current_snap.parent_snapshot_id),
            "added": added,
            "removed": removed,
            "type_changed": type_changed,
        }

    def get_schema_history(self, table_identifier: str, snapshots: list):
        """Detect schema changes by comparing metadata.json versions."""
        catalog = self._get_catalog()
        namespace, table_name = table_identifier.split(".", 1)
        table = catalog.load_table(f"{namespace}.{table_name}")

        metadata_files = [e.metadata_file for e in table.metadata.metadata_log]
        metadata_files.append(table.metadata_location)

        schema_versions = []
        schema_id_to_snapshot = {}
        seen_schema_ids = set()

        for path in metadata_files:
            try:
                raw = self._read_s3_json(path)
                ts = raw.get("last-updated-ms", 0)
                curr_schema_id = raw.get("current-schema-id")
                curr_snapshot_id = raw.get("current-snapshot-id")

                if curr_schema_id is not None and curr_schema_id not in schema_id_to_snapshot:
                    schema_id_to_snapshot[curr_schema_id] = str(curr_snapshot_id) if curr_snapshot_id else None

                for s in raw.get("schemas", []):
                    sid = s["schema-id"]
                    if sid not in seen_schema_ids:
                        seen_schema_ids.add(sid)
                        cols = {f["name"].lower(): f["type"] for f in s["fields"]}
                        schema_versions.append((ts, sid, cols))
            except Exception:
                continue

        schema_versions.sort(key=lambda x: x[1])

        results = []
        for i in range(1, len(schema_versions)):
            prev_ts, prev_sid, prev_cols = schema_versions[i - 1]
            curr_ts, curr_sid, curr_cols = schema_versions[i]

            added = {k: v for k, v in curr_cols.items() if k not in prev_cols}
            removed = {k: v for k, v in prev_cols.items() if k not in curr_cols}
            type_changed = {
                k: {"from": prev_cols[k], "to": curr_cols[k]}
                for k in curr_cols
                if k in prev_cols and curr_cols[k] != prev_cols[k]
            }

            if added or removed or type_changed:
                ts_str = datetime.utcfromtimestamp(curr_ts / 1000).strftime("%Y-%m-%dT%H:%M:%SZ") if curr_ts else "unknown"
                snap_id = schema_id_to_snapshot.get(curr_sid)
                results.append({
                    "snapshot_id": snap_id,
                    "schema_id": curr_sid,
                    "parent_schema_id": prev_sid,
                    "timestamp": ts_str,
                    "operation": "SCHEMA_CHANGE",
                    "added": added,
                    "removed": removed,
                    "type_changed": type_changed,
                })

        return results

    def get_schema_diff_by_id(self, table_identifier: str, schema_id: int):
        """Get schema diff for a given schema_id by reading metadata.json directly."""
        catalog = self._get_catalog()
        namespace, table_name = table_identifier.split(".", 1)
        table = catalog.load_table(f"{namespace}.{table_name}")

        metadata_files = [e.metadata_file for e in table.metadata.metadata_log]
        metadata_files.append(table.metadata_location)

        all_schemas = {}
        for path in metadata_files:
            try:
                raw = self._read_s3_json(path)
                for s in raw.get("schemas", []):
                    sid = s["schema-id"]
                    if sid not in all_schemas:
                        all_schemas[sid] = {
                            f["name"].lower(): f["type"] for f in s["fields"]
                        }
            except Exception:
                continue

        if schema_id not in all_schemas:
            return {"error": f"schema_id {schema_id} not found"}

        parent_id = schema_id - 1
        if parent_id not in all_schemas:
            return {"error": f"parent schema_id {parent_id} not found"}

        current_cols = all_schemas[schema_id]
        parent_cols = all_schemas[parent_id]

        added = {k: v for k, v in current_cols.items() if k not in parent_cols}
        removed = {k: v for k, v in parent_cols.items() if k not in current_cols}
        type_changed = {
            k: {"from": parent_cols[k], "to": current_cols[k]}
            for k in current_cols
            if k in parent_cols and current_cols[k] != parent_cols[k]
        }

        return {
            "snapshot_id": str(schema_id),
            "parent_snapshot_id": str(parent_id),
            "added": added,
            "removed": removed,
            "type_changed": type_changed,
            "before_cols": parent_cols,
            "after_cols": current_cols,
        }

