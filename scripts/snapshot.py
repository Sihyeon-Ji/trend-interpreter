"""Capture, verify, publish and fetch a private, generation-pinned SQLite snapshot."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import google_crc32c

ROOT = "gs://copybara-team-shared-bucket/taewoo/trend-interpreter"
FILES = ("trend-latest.db.gz", "table-counts.txt", "updated_at.txt")
EXCLUDED = {"explain_cache", "lookups", "reader_prefs"}
CHUNK_SIZE = 1024 * 1024
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}")


def hashes(path: Path) -> dict:
    sha = hashlib.sha256()
    crc = google_crc32c.Checksum()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK_SIZE):
            sha.update(chunk)
            crc.update(chunk)
    return {"size": path.stat().st_size, "sha256": sha.hexdigest(),
            "crc32c": base64.b64encode(crc.digest()).decode("ascii")}


def inspect_database(directory: Path) -> dict:
    counts = {}
    for line in (directory / "table-counts.txt").read_text().splitlines():
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s+(\d+)", line.strip())
        if not match or match[1] in counts:
            raise ValueError("Invalid or duplicate table count")
        counts[match[1]] = int(match[2])
    if not counts or "terms" not in counts:
        raise ValueError("Missing terms count")
    updated = (directory / "updated_at.txt").read_text().strip().split()
    if len(updated) != 3 or not re.fullmatch(r"[a-f0-9]{7,40}", updated[1]):
        raise ValueError("Invalid collection metadata")
    if datetime.fromisoformat(updated[0]).tzinfo is None or updated[2] != f"terms={counts['terms']}":
        raise ValueError("Collection metadata does not match table counts")
    with tempfile.TemporaryDirectory() as work:
        path = Path(work) / "snapshot.db"
        with gzip.open(directory / FILES[0], "rb") as source, path.open("wb") as target:
            shutil.copyfileobj(source, target, CHUNK_SIZE)
        with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as con:
            if con.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite integrity check failed")
            tables = {row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if tables & EXCLUDED:
                raise ValueError("Snapshot contains excluded user tables")
            if tables != set(counts):
                raise ValueError("Table inventory does not match SQLite")
            for name, expected in counts.items():
                if con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] != expected:
                    raise ValueError(f"Table count mismatch for {name}")
            schema = con.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()
            version = con.execute("PRAGMA user_version").fetchone()[0]
    return {"collected_at": updated[0], "collector_commit": updated[1], "table_counts": counts,
            "excluded_tables": sorted(EXCLUDED), "input_schema_version": version,
            "schema_sha256": hashlib.sha256(json.dumps(schema).encode()).hexdigest()}


def validate_manifest(manifest: dict) -> None:
    if manifest.get("manifest_version") != 1 or not IDENTIFIER.fullmatch(manifest.get("snapshot_id", "")):
        raise ValueError("Invalid snapshot manifest")
    if manifest.get("state") not in {"captured", "published"}:
        raise ValueError("Invalid snapshot state")
    objects = manifest.get("objects", [])
    if len(objects) != len(FILES) or {item.get("name") for item in objects} != set(FILES):
        raise ValueError("Invalid snapshot object inventory")
    for item in objects:
        name = item["name"]
        prefix = f"{ROOT}/snapshots/{manifest['snapshot_id']}" if manifest["state"] == "published" else f"{ROOT}/db/latest"
        if item.get("uri") != f"{prefix}/{name}" or not re.fullmatch(r"[1-9]\d*", str(item.get("generation", ""))):
            raise ValueError("Invalid object location or generation")
        if not isinstance(item.get("size"), int) or item["size"] <= 0:
            raise ValueError("Invalid object size")
        if not re.fullmatch(r"[a-f0-9]{64}", item.get("sha256", "")):
            raise ValueError("Invalid object SHA-256")
        if not re.fullmatch(r"[A-Za-z0-9+/]{6}==", item.get("crc32c", "")):
            raise ValueError("Invalid object CRC32C")


def verify(manifest: dict, directory: Path) -> None:
    validate_manifest(manifest)
    for item in manifest["objects"]:
        if hashes(directory / item["name"]) != {key: item[key] for key in ("size", "sha256", "crc32c")}:
            raise ValueError(f"Object checksum mismatch for {item['name']}")
    actual = inspect_database(directory)
    if any(manifest.get(key) != value for key, value in actual.items()):
        raise ValueError("Database metadata does not match manifest")


def blob(client, uri: str, generation=None):
    bucket, name = uri.removeprefix("gs://").split("/", 1)
    return client.bucket(bucket).blob(name, generation=generation)


def download(item: dict, directory: Path, client) -> None:
    pinned = blob(client, item["uri"], int(item["generation"]))
    pinned.download_to_filename(str(directory / item["name"]),
                                if_generation_match=int(item["generation"]), checksum="crc32c")


def capture(snapshot_id: str, directory: Path, client) -> dict:
    if not IDENTIFIER.fullmatch(snapshot_id):
        raise ValueError("Invalid snapshot ID")
    directory.mkdir(parents=True, exist_ok=False)
    objects = []
    for name in FILES:
        current = blob(client, f"{ROOT}/db/latest/{name}")
        current.reload()
        objects.append({"name": name, "uri": f"{ROOT}/db/latest/{name}",
                        "generation": str(current.generation), "size": current.size, "crc32c": current.crc32c})
    for item in objects:
        download(item, directory, client)
        measured = hashes(directory / item["name"])
        if any(measured[key] != item[key] for key in ("size", "crc32c")):
            raise ValueError("Downloaded object does not match GCS metadata")
        item["sha256"] = measured["sha256"]
    metadata = inspect_database(directory)
    for item in objects:
        current = blob(client, item["uri"])
        current.reload()
        if str(current.generation) != item["generation"]:
            raise ValueError("Source changed during capture; retry with a new snapshot ID")
    manifest = {"manifest_version": 1, "snapshot_id": snapshot_id, "state": "captured",
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "source_consistency": "legacy-count-verified", "objects": objects, **metadata}
    verify(manifest, directory)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def publish(manifest: dict, directory: Path, client) -> dict:
    verify(manifest, directory)
    if manifest["state"] != "captured":
        raise ValueError("Only a captured snapshot can be published")
    published = {**manifest, "state": "published", "objects": []}
    for item in manifest["objects"]:
        uri = f"{ROOT}/snapshots/{manifest['snapshot_id']}/{item['name']}"
        target = blob(client, uri)
        target.upload_from_filename(str(directory / item["name"]), if_generation_match=0, checksum="crc32c")
        if target.size != item["size"] or target.crc32c != item["crc32c"]:
            raise ValueError("Uploaded object does not match snapshot")
        published["objects"].append({**item, "uri": uri, "generation": str(target.generation),
                                     "source_uri": item["uri"], "source_generation": item["generation"]})
    verify(published, directory)
    target = blob(client, f"{ROOT}/manifests/{manifest['snapshot_id']}.json")
    target.upload_from_string(json.dumps(published, indent=2) + "\n", content_type="application/json",
                              if_generation_match=0, checksum="crc32c")
    (directory / "published-manifest.json").write_text(json.dumps(published, indent=2) + "\n")
    return published


def fetch(manifest: dict, directory: Path, client) -> None:
    validate_manifest(manifest)
    if manifest["state"] != "published":
        raise ValueError("Fetch requires a published snapshot, never db/latest")
    directory.mkdir(parents=True, exist_ok=False)
    for item in manifest["objects"]:
        download(item, directory, client)
    verify(manifest, directory)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def storage_client():
    """Application Default Credentials, or a short-lived token from GOOGLE_OAUTH_ACCESS_TOKEN so no credential file is written."""
    from google.cloud import storage

    token = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN")
    if not token:
        return storage.Client()
    from google.oauth2.credentials import Credentials

    return storage.Client(project=os.environ["GOOGLE_CLOUD_PROJECT"], credentials=Credentials(token))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    intake = commands.add_parser("capture")
    intake.add_argument("--snapshot-id", required=True)
    intake.add_argument("--directory", type=Path, required=True)
    for name in ("verify", "publish", "fetch"):
        command = commands.add_parser(name)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "capture":
            manifest = capture(args.snapshot_id, args.directory, storage_client())
        else:
            manifest = json.loads(args.manifest.read_text())
            if args.command == "verify":
                verify(manifest, args.directory)
            elif args.command == "publish":
                manifest = publish(manifest, args.directory, storage_client())
            else:
                fetch(manifest, args.directory, storage_client())
        print(json.dumps({"snapshot_id": manifest["snapshot_id"], "operation": args.command,
                          "state": manifest["state"], "terms": manifest["table_counts"]["terms"]}))
    except Exception as error:
        # Cloud exceptions can include request headers or source content.
        print(json.dumps({"operation": args.command, "error_code": type(error).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
