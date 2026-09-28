import os
import subprocess
from pathlib import Path

import pytest


def test_failed_relay_candidate_health_preserves_serving_revision(tmp_path):
    tools = tmp_path / "tools"
    tools.mkdir()
    trace = tmp_path / "gcloud-calls.txt"
    gcloud = tools / "gcloud"
    gcloud.write_text(
        "#!/usr/bin/env python3\n"
        "import json,os,sys\n"
        "args=sys.argv[1:]\n"
        "with open(os.environ['FAKE_GCLOUD_TRACE'],'a') as out: out.write(' '.join(args)+'\\n')\n"
        "if args[:3]==['secrets','versions','list']: print('1')\n"
        "elif args[:3]==['run','services','describe'] and '--format=json' in args:\n"
        " print(json.dumps({'status':{'url':'https://example.test','latestReadyRevisionName':'candidate-revision',"
        "'traffic':[{'revisionName':'previous-revision','percent':100,'tag':'candidate','url':'https://candidate.test'}]}}))\n"
        "elif args[:3]==['run','services','describe']: print('previous-revision')\n"
    )
    gcloud.chmod(0o755)
    curl = tools / "curl"
    curl.write_text("#!/bin/sh\nexit 22\n")
    curl.chmod(0o755)
    env = os.environ.copy()
    env.update(
        PATH=f"{tools}:{env['PATH']}",
        FAKE_GCLOUD_TRACE=str(trace),
        PROJECT_ID="test-project",
        PROJECT_NUMBER="12345",
        REGION="asia-northeast1",
        SERVICE="builder-cup-alert-relay",
        ALERT_TOPIC="test-topic",
        HEALTH_ID_TOKEN="synthetic-test-token",
    )
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["bash", "scripts/deploy-alert-relay.sh", "image@sha256:abc"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "run services update-traffic" not in trace.read_text()
