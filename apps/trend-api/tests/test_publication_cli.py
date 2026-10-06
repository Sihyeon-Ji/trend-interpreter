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
