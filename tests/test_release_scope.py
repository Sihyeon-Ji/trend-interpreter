import shutil

import pytest

from scripts.release_scope import ZERO_SHA, changed_files, classify


def test_release_scope_routes_services_and_checks():
    assert classify({"apps/trend-api/src/trend_agents/api/app.py"}) == {
        "full": True,
        "infra": False,
        "app": True,
        "relay": False,
    }
    assert classify({"apps/alert-relay/Dockerfile"}) == {
        "full": True,
        "infra": False,
        "app": False,
        "relay": True,
    }
    assert classify({"scripts/verify_alert_delivery.py"})["relay"] is True
    assert classify({"apps/trend-web/app/page.tsx", "apps/alert-relay/pyproject.toml"}) == {
        "full": True,
        "infra": False,
        "app": True,
        "relay": True,
    }
    assert classify({".dockerignore"})["app"] is True
    assert classify({"scripts/container-smoke.sh"})["app"] is True
    assert classify({".dockerignore"})["relay"] is True
    assert classify({"tests/test_api.py", "compose.yaml"}) == {
        "full": True,
        "infra": False,
        "app": False,
        "relay": False,
    }
    assert classify({"infra/gcp/main.tf"}) == {
        "full": False,
        "infra": True,
        "app": False,
        "relay": False,
    }
    assert classify({"docs/운영/GCP-운영.md", "README.md", "prototype/trend/main.py"}) == {
        "full": False,
        "infra": False,
        "app": False,
        "relay": False,
    }
    assert classify({"unknown.config"})["full"] is True
    assert classify(set(), "ops: 메인 서비스 재배포") == {
        "full": True,
        "infra": False,
        "app": True,
        "relay": False,
    }
    assert classify(set(), "ops: 알림 중계기 재배포")["relay"] is True
    assert classify(set(), "ops: 전체 서비스 재배포")["app"] is True
    assert classify(set(), "ops: 전체 서비스 재배포")["relay"] is True
    assert classify({"docs/README.md"}, "ops: 메인 서비스 재배포")["app"] is True
    assert classify({"scripts/release_recovery.py"})["app"] is True
    assert classify({"scripts/release_recovery.py"})["relay"] is True
    assert classify(None) == {"full": True, "infra": True, "app": True, "relay": True}


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is not installed in the check image")
def test_release_scope_reads_git_range_and_new_branch(tmp_path, monkeypatch):
    import subprocess

    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True)
    (tmp_path / "README.md").write_text("one")
    subprocess.run(["git", "add", "README.md"], check=True)
    subprocess.run(["git", "commit", "-qm", "first"], check=True)
    first = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert changed_files(ZERO_SHA, first) == {"README.md"}

    source = tmp_path / "apps" / "trend-api"
    source.mkdir(parents=True)
    (source / "main.py").write_text("pass")
    (tmp_path / "README.md").unlink()
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-qm", "second"], check=True)
    second = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert changed_files(first, second) == {"README.md", "apps/trend-api/main.py"}
    assert changed_files("f" * 40, second) is None
