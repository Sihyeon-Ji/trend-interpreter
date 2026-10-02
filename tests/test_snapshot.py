import copy
import gzip
import json
import sqlite3
from pathlib import Path

import pytest

from scripts import snapshot


class FakeBlob:
    def __init__(self, cloud, name, generation=None):
        self.cloud = cloud
        self.name = name
        self.generation = generation

    def reload(self):
        stored = self.cloud.objects[self.name]
        self.generation = stored["generation"]
        self.size = stored["size"]
        self.crc32c = stored["crc32c"]

    def download_to_filename(self, filename, *, if_generation_match, checksum):
        stored = self.cloud.versions[self.name, int(self.generation)]
        assert int(self.generation) == if_generation_match
        assert checksum == "crc32c"
        Path(filename).write_bytes(stored["content"])
        self.cloud.downloads.append((self.name, if_generation_match))
        if self.cloud.change_during_download:
            self.cloud.objects[self.name] = {**stored, "generation": stored["generation"] + 1}

    def upload_from_filename(self, filename, *, if_generation_match, checksum):
        assert if_generation_match == 0
        assert checksum == "crc32c"
        if self.name == self.cloud.fail_upload:
            raise RuntimeError("Upload failed")
        if self.name in self.cloud.objects:
            raise RuntimeError("Precondition failed")
        self.cloud.store(self.name, Path(filename))
        self.reload()
        self.cloud.uploads.append(self.name)

    def upload_from_string(self, content, **kwargs):
        assert kwargs["if_generation_match"] == 0
        if self.name in self.cloud.objects:
            raise RuntimeError("Precondition failed")
        self.cloud.manifests[self.name] = json.loads(content)
        self.cloud.uploads.append(self.name)


class FakeCloud:
    def __init__(self, directory):
        self.objects = {}
        self.versions = {}
        self.manifests = {}
        self.downloads = []
        self.uploads = []
        self.change_during_download = False
        self.fail_upload = None
        for name in snapshot.FILES:
            self.store(f"taewoo/trend-interpreter/db/latest/{name}", directory / name)

    def store(self, name, path):
        item = {**snapshot.hashes(path), "generation": len(self.versions) + 100,
                "content": path.read_bytes()}
        self.objects[name] = item
        self.versions[name, item["generation"]] = item

    def bucket(self, name):
        assert name == "copybara-team-shared-bucket"
        return self

    def blob(self, name, generation=None):
        return FakeBlob(self, name, generation)


@pytest.fixture
def source(tmp_path):
    directory = tmp_path / "source"
    directory.mkdir()
    path = directory / "trend.db"
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE terms (term_id TEXT PRIMARY KEY)")
        con.execute("INSERT INTO terms VALUES ('test-term')")
    with path.open("rb") as data, gzip.open(directory / snapshot.FILES[0], "wb") as target:
        target.write(data.read())
    (directory / "table-counts.txt").write_text("terms 1\n")
    (directory / "updated_at.txt").write_text("2026-10-01T22:45:11+09:00 e56b90d terms=1\n")
    return directory


def test_capture_publish_and_fetch_keep_old_generation(tmp_path, source):
    cloud = FakeCloud(source)
    captured = tmp_path / "captured"
    manifest = snapshot.capture("20261001-test", captured, cloud)
    assert cloud.uploads == []
    assert len(cloud.downloads) == 3
    published = snapshot.publish(manifest, captured, cloud)
    assert cloud.uploads[-1] == "taewoo/trend-interpreter/manifests/20261001-test.json"
    assert cloud.manifests[cloud.uploads[-1]] == published
    for item in published["objects"]:
        name = item["uri"].split("/", 3)[3]
        cloud.objects[name] = {**cloud.objects[name], "generation": 999}
    restored = tmp_path / "restored"
    snapshot.fetch(published, restored, cloud)
    assert (restored / snapshot.FILES[0]).read_bytes() == (captured / snapshot.FILES[0]).read_bytes()
    assert cloud.downloads[-3:][0][1] == int(published["objects"][0]["generation"])
    with pytest.raises(RuntimeError):
        snapshot.publish(manifest, captured, cloud)


def test_capture_rejects_concurrent_latest_update(tmp_path, source):
    cloud = FakeCloud(source)
    cloud.change_during_download = True
    directory = tmp_path / "mixed"
    with pytest.raises(ValueError, match="Source changed"):
        snapshot.capture("test", directory, cloud)
    assert not (directory / "manifest.json").exists()


def test_failed_upload_does_not_publish_manifest(tmp_path, source):
    cloud = FakeCloud(source)
    directory = tmp_path / "capture"
    manifest = snapshot.capture("test", directory, cloud)
    cloud.fail_upload = "taewoo/trend-interpreter/snapshots/test/table-counts.txt"
    with pytest.raises(RuntimeError):
        snapshot.publish(manifest, directory, cloud)
    assert cloud.manifests == {}


def test_checksum_failure_prevents_any_publication(tmp_path, source):
    cloud = FakeCloud(source)
    directory = tmp_path / "capture"
    manifest = snapshot.capture("test", directory, cloud)
    (directory / "table-counts.txt").write_text("terms 99\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        snapshot.publish(manifest, directory, cloud)
    assert cloud.uploads == []


@pytest.mark.parametrize("change", ["terms 2\n", "terms 1\nterms 1\n", "terms 1\nmissing 0\n"])
def test_mixed_or_invalid_counts_are_rejected(source, change):
    (source / "table-counts.txt").write_text(change)
    with pytest.raises(ValueError):
        snapshot.inspect_database(source)


@pytest.mark.parametrize("name", sorted(snapshot.EXCLUDED))
def test_even_empty_user_tables_are_rejected(source, name):
    path = source / "trend.db"
    with sqlite3.connect(path) as con:
        con.execute(f"CREATE TABLE {name} (text TEXT)")
    with gzip.open(source / snapshot.FILES[0], "wb") as target:
        target.write(path.read_bytes())
    with pytest.raises(ValueError, match="excluded user tables"):
        snapshot.inspect_database(source)


@pytest.mark.parametrize("field,value", [
    ("name", "../../credentials.json"), ("generation", 0), ("sha256", "invalid"),
    ("uri", "gs://another-bucket/private"), ("size", -1), ("crc32c", "invalid"),
])
def test_untrusted_manifest_paths_and_metadata_are_rejected(tmp_path, source, field, value):
    cloud = FakeCloud(source)
    manifest = snapshot.capture("test", tmp_path / "capture", cloud)
    bad = copy.deepcopy(manifest)
    bad["objects"][0][field] = value
    with pytest.raises(ValueError):
        snapshot.fetch(bad, tmp_path / "fetch", cloud)
    assert not (tmp_path / "fetch").exists()


def test_captured_latest_is_not_a_durable_fetch_target(tmp_path, source):
    cloud = FakeCloud(source)
    manifest = snapshot.capture("test", tmp_path / "capture", cloud)
    with pytest.raises(ValueError, match="published snapshot"):
        snapshot.fetch(manifest, tmp_path / "fetch", cloud)
