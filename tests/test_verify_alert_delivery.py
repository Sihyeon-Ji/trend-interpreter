import json

from scripts.verify_alert_delivery import delivered


def test_delivery_requires_exact_incident_revision_and_discord_success():
    def row(incident: str, revision: str, event: str, status: int) -> dict:
        return {
            "resource": {"labels": {"revision_name": revision}},
            "textPayload": "INFO:     "
            + json.dumps({"incident_id": incident, "event": event, "discord_status": status}),
        }

    expected = "deployment-smoke-123"
    revision = "relay-00001"
    assert not delivered(
        [row(expected, revision, "discord_delivery_failed", 503)], expected, revision
    )
    assert not delivered(
        [row(expected, "old-revision", "discord_delivery_succeeded", 204)], expected, revision
    )
    assert not delivered(
        [row("other", revision, "discord_delivery_succeeded", 204)], expected, revision
    )
    assert delivered(
        [row(expected, revision, "discord_delivery_succeeded", 204)], expected, revision
    )
