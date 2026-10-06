"""Review tooling keeps draft outputs private and authenticates before DB writes."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from trend_agents.auth import Account

spec = importlib.util.spec_from_file_location("publication_cli", Path(__file__).resolve().parents[1] / "scripts/publication.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_inspect_uses_read_only_connection_and_prints_metadata_only(monkeypatch, tmp_path, capsys):
    class Connection:
        def close(self):
            pass

    out = tmp_path / "private-review.json"
    monkeypatch.setattr(sys, "argv", ["publication.py", "inspect", "--batch-id", "b", "--out", str(out)])
    monkeypatch.setattr(cli.db, "connect", lambda: pytest.fail("inspection must not migrate or write the database"))
    monkeypatch.setattr(cli.db, "connect_read_only", Connection)
    monkeypatch.setattr(cli.pub, "inspect", lambda *a: {"batch": {"generated_text": "PRIVATE DRAFT"},
                                                       "payload_sha256": "a" * 64, "status": "draft"})
    cli.main()
    assert "PRIVATE DRAFT" not in capsys.readouterr().out
    assert json.loads(out.read_text())["batch"]["generated_text"] == "PRIVATE DRAFT"
    assert out.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("account", [None, Account("reader", False)])
def test_approval_refuses_unknown_or_ordinary_account_before_opening_db(monkeypatch, account):
    monkeypatch.setattr(sys, "argv", ["publication.py", "review", "--batch-id", "b", "--sha256", "a" * 64,
                                     "--user", "reader", "--decision", "approve"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda *a: "input")
    monkeypatch.setattr(cli, "check_account", lambda *a: account)
    monkeypatch.setattr(cli.db, "connect", lambda: pytest.fail("unauthorized reviewer reached DB"))
    with pytest.raises(SystemExit, match="reviewer_authentication_required"):
        cli.main()


def test_approval_refuses_password_echo_fallback(monkeypatch):
    import warnings

    monkeypatch.setattr(sys, "argv", ["publication.py", "review", "--batch-id", "b", "--sha256", "a" * 64,
                                     "--user", "reviewer", "--decision", "approve"])

    def fallback(*args):
        warnings.warn("Password input may be echoed", cli.getpass.GetPassWarning)
        pytest.fail("must stop before echoed input")

    monkeypatch.setattr(cli.getpass, "getpass", fallback)
    monkeypatch.setattr(cli.db, "connect", lambda: pytest.fail("unsafe authentication reached DB"))
    with pytest.raises(SystemExit, match="secure_password_input_required"):
        cli.main()


def test_export_opens_read_only_db_and_keeps_source_out_of_stdout(monkeypatch, tmp_path, capsys):
    class Connection:
        def close(self):
            pass

    out = tmp_path / "terms.jsonl"
    monkeypatch.setattr(sys, "argv", ["publication.py", "export-translations", "--term-id", "t_one",
                                     "--snapshot-id", "fixed", "--snapshot-sha256", "a" * 64, "--out", str(out)])
    monkeypatch.setattr(cli.db, "connect", lambda: pytest.fail("export must not migrate or write"))
    monkeypatch.setattr(cli.db, "connect_read_only", Connection)
    monkeypatch.setattr(cli.inputs, "translation_inputs", lambda *a: b"PRIVATE SOURCE\n")
    cli.main()
    assert "PRIVATE SOURCE" not in capsys.readouterr().out
    assert out.read_bytes() == b"PRIVATE SOURCE\n" and out.stat().st_mode & 0o777 == 0o600


def test_pack_never_connects_to_db_or_overwrites_a_private_artifact(monkeypatch, tmp_path, capsys):
    from trend_agents.schemas import MeaningText

    files = [tmp_path / name for name in ("terms.jsonl", "translations.jsonl", "run.json")]
    for path in files:
        path.write_text("{}")
    out = tmp_path / "batch.json"
    batch = cli.pub.ChangeBatch(batch_id="packed", snapshot_id="s", snapshot_sha256="a" * 64,
                               model_id="mock", prompt_version="p", rule_version="r", items=[
        cli.pub.ChangeItem(term_id="t_one", expected_meaning_id="m_one", translations={"en":
            MeaningText(definition="PRIVATE GENERATED TEXT", origin="origin", nuance="nuance")}, derived_from_sha256="b" * 64)])
    monkeypatch.setattr(sys, "argv", ["publication.py", "pack-translations", "--input", str(files[0]),
                                     "--results", str(files[1]), "--run", str(files[2]), "--batch-id", "packed", "--out", str(out)])
    monkeypatch.setattr(cli.db, "connect", lambda: pytest.fail("packing must be offline"))
    monkeypatch.setattr(cli.db, "connect_read_only", lambda: pytest.fail("packing must be offline"))
    monkeypatch.setattr(cli.inputs, "pack_translations", lambda *a, **kw: (batch, 0))
    cli.main()
    assert "PRIVATE GENERATED TEXT" not in capsys.readouterr().out
    assert cli.pub.ChangeBatch.model_validate_json(out.read_bytes()) == batch
    assert out.stat().st_mode & 0o777 == 0o600
    with pytest.raises(SystemExit, match="invalid_translation_files_or_output"):
        cli.main()
    assert cli.pub.ChangeBatch.model_validate_json(out.read_bytes()) == batch
