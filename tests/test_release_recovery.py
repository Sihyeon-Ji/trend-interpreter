import pytest

from scripts import release_recovery as recovery
from scripts.release_summary import format_summary


def revision(service="trend-production-api", version="1", ready=True):
    variable, secret = recovery.SECRETS[service]
    return {
        "metadata": {
            "name": f"{service}-00001-test",
            "labels": {"serving.knative.dev/service": service},
        },
        "status": {"conditions": [{"type": "Ready", "status": "True" if ready else "False"}]},
        "spec": {
            "containers": [
                {
                    "image": "example.test/app@sha256:abc",
                    "env": [
                        {
                            "name": variable,
                            "valueFrom": {"secretKeyRef": {"name": secret, "key": version}},
                        }
                    ],
                }
            ]
        },
    }


def test_revision_preflight_rejects_wrong_service_unready_or_unpinned_secret():
    assert recovery.validate_revision("trend-production-api", revision()) == (
        "example.test/app@sha256:abc",
        "1",
    )
    for target in (
        revision("builder-cup-alert-relay"),
        revision(ready=False),
        revision(version="latest"),
    ):
        with pytest.raises(recovery.RecoveryError):
            recovery.validate_revision("trend-production-api", target)


def test_revision_preflight_resolves_secret_aliases():
    target = revision()
    variable, secret = recovery.SECRETS["trend-production-api"]
    target["metadata"]["annotations"] = {
        "run.googleapis.com/secrets": f"secret-alias-2:projects/p/secrets/other,secret-alias-1:projects/p/secrets/{secret}"
    }
    target["spec"]["containers"][0]["env"][0]["valueFrom"]["secretKeyRef"]["name"] = "secret-alias-1"
    assert recovery.validate_revision("trend-production-api", target)[1] == "1"
    target["spec"]["containers"][0]["env"][0]["valueFrom"]["secretKeyRef"]["name"] = "secret-alias-2"
    with pytest.raises(recovery.RecoveryError):
        recovery.validate_revision("trend-production-api", target)


def test_relay_invoker_policy_must_stay_private():
    push = f"serviceAccount:builder-cup-alert-push@{recovery.PROJECT_ID}.iam.gserviceaccount.com"
    recovery.validate_relay_iam({"bindings": [{"role": "roles/run.invoker", "members": [push]}]})
    with pytest.raises(recovery.RecoveryError):
        recovery.validate_relay_iam(
            {"bindings": [{"role": "roles/run.invoker", "members": [push, "allUsers"]}]}
        )


def test_check_mode_never_changes_traffic(monkeypatch):
    monkeypatch.setattr(recovery, "preflight", lambda *_: ("current", "image@sha256:abc", "1"))
    monkeypatch.setattr(recovery, "command", lambda *_: pytest.fail("traffic must not change"))
    monkeypatch.setattr(
        recovery, "service_snapshot", lambda _: {"status": {"url": "https://example.test"}}
    )
    checked = []
    monkeypatch.setattr(recovery, "verify_http", lambda *args: checked.append(args))
    recovery.recover("trend-production-api", "current", apply=False)
    assert checked == [("trend-production-api", "https://example.test")]


def test_failed_postcheck_restores_previous_revision(monkeypatch):
    monkeypatch.setattr(recovery, "preflight", lambda *_: ("previous", "image@sha256:abc", "1"))
    commands = []
    monkeypatch.setattr(recovery, "command", lambda *args: commands.append(args))
    monkeypatch.setattr(
        recovery,
        "service_snapshot",
        lambda _: {
            "status": {
                "url": "https://example.test",
                "traffic": [{"revisionName": "target", "percent": 100}],
            }
        },
    )
    monkeypatch.setattr(
        recovery,
        "verify_http",
        lambda *_: (_ for _ in ()).throw(recovery.RecoveryError("health failed")),
    )
    with pytest.raises(recovery.RecoveryError, match="health failed"):
        recovery.recover("trend-production-api", "target", apply=True)
    assert any("--to-revisions=target=100" in args for args in commands)
    assert any("--to-revisions=previous=100" in args for args in commands)


def test_release_report_contains_metadata_without_secret_value():
    result = format_summary(
        "trend-production-api",
        "previous",
        "current",
        "image@sha256:abc",
        "builder-cup-demo-key:1",
        "gemini-3.5-flash",
        "health 200",
        "commit123",
    )
    assert all(
        value in result for value in ("previous", "current", "builder-cup-demo-key:1", "commit123")
    )
    assert "secret value" not in result


def test_trend_services_use_their_own_health_contract(monkeypatch):
    import io
    import json as jsonlib

    seen = []

    class Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        url = request if isinstance(request, str) else request.full_url
        seen.append((url, getattr(request, "headers", {})))
        body = {"ok": True, "terms": 3} if url.endswith("/health") else {}
        return Response(jsonlib.dumps(body).encode())

    monkeypatch.setattr(recovery.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("HEALTH_ID_TOKEN", "synthetic")
    recovery.verify_http("trend-production-api", "https://api.example")
    recovery.verify_http("trend-production-web", "https://web.example")
    assert seen[0][0] == "https://api.example/health" and seen[0][1] == {"Authorization": "Bearer synthetic"}
    assert seen[1][0] == "https://web.example/"

    monkeypatch.setattr(recovery.urllib.request, "urlopen", lambda request, timeout: Response(b'{"ok": true, "terms": 0}'))
    with pytest.raises(recovery.RecoveryError):
        recovery.verify_http("trend-production-api", "https://api.example")
