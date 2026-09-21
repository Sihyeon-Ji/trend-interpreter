"""로컬 보드 어댑터 — Jira 없이 전체 루프를 돌리기 위한 백엔드.

Jira 어댑터와 '같은 모양'을 돌려준다 (fields.status.name, issuelinks, customfield_10016 …).
그래서 schedule.from_jira_issues / tools.py / approve.py 는 한 줄도 바뀌지 않는다 —
PM 도구에 종속되지 않는다는 주장이 코드로 증명되는 지점이다 (SETUP.md 1-4 의 Kaneo 도 같은 자리에
꽂힌다).

저장은 JSON 파일 하나. 계정도 네트워크도 필요 없고, 쓰기는 Jira 와 동일하게 approve 게이트를 탄다.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re

from pmo_agent.env import data_dir

STORE = str(data_dir() / "seed_state.json")
STATUSES = ("To Do", "In Progress", "In Review", "Done")


class MemoryBoard:
    """파일 한 개를 보드로 쓰는 어댑터. Jira 클래스와 메서드 이름·반환 모양이 같다."""

    def __init__(self, path: str | None = None, project: str = "ECHO", issues=None):
        self.path: str | None = path or STORE
        self.project = project
        self.site = "local"
        self.allow = ["local"]
        self._issues = None
        if issues is not None:  # 파일 없이 메모리만 쓰는 모드 (테스트용)
            self._issues = {i["key"]: i for i in issues}
            self.path = None

    # ---------- 저장소 ----------
    def _load(self) -> dict:
        if self._issues is not None:
            return self._issues
        if self.path and os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self._issues = {i["key"]: i for i in data.get("issues", [])}
        else:
            self._issues = {}
        return self._issues

    def _save(self) -> None:
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "project": self.project,
                    "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "issues": list(self._load().values()),
                },
                f,
                ensure_ascii=False,
                indent=1,
            )

    # ---------- 읽기 ----------
    def whoami(self):
        return {"displayName": "로컬 보드", "emailAddress": "local@echo-pmo", "accountId": "local"}

    def project_info(self):
        return {"key": self.project, "name": "Echo PMO (로컬)", "projectTypeKey": "software"}

    def search(self, jql=None, limit=100, **_):
        """JQL 전체를 해석하지는 않는다.

        status / assignee 필터와 duedate 정렬만 본다 — list_tasks 가 쓰는 범위다.
        """
        issues = list(self._load().values())
        for field in ("status", "assignee"):
            m = re.search(rf'{field}\s*=\s*"([^"]+)"', jql or "")
            if not m:
                continue
            want = m.group(1)
            issues = [i for i in issues if _field_name(i, field) == want]
        issues.sort(key=lambda i: (i["fields"].get("duedate") or "9999-12-31", i["key"]))
        return issues[:limit]

    def issue(self, key):
        i = self._load().get(key)
        if not i:
            raise RuntimeError(f"{key} 없음 (로컬 보드)")
        return i

    def transitions(self, key):
        cur = _field_name(self.issue(key), "status")
        return [
            {"id": str(n), "name": s, "to": {"name": s}}
            for n, s in enumerate(STATUSES, 1)
            if s != cur
        ]

    # ---------- 쓰기 (Jira 와 동일하게 approve 게이트) ----------
    def create_issue(
        self,
        summary,
        description="",
        issuetype="Task",
        assignee_id=None,
        duedate=None,
        parent=None,
        approve=False,
    ):
        fields = {
            "summary": summary,
            "issuetype": {"name": issuetype},
            "status": {"name": "To Do"},
            "assignee": {"displayName": assignee_id} if assignee_id else None,
            "duedate": duedate,
            "issuelinks": [],
            "customfield_10016": None,
        }
        if not approve:
            return {"dry_run": True, "would_create": fields}
        issues = self._load()
        key = f"{self.project}-{max([int(k.split('-')[1]) for k in issues] or [0]) + 1}"
        issues[key] = {"key": key, "fields": fields}
        self._save()
        return {"key": key, "fields": fields}

    def comment(self, key, text, approve=False):
        if not approve:
            return {"dry_run": True, "would_comment_on": key, "text": text}
        i = self.issue(key)
        i["fields"].setdefault("comments", []).append(
            {"at": dt.datetime.now().isoformat(timespec="seconds"), "text": text}
        )
        self._save()
        return {"id": str(len(i["fields"]["comments"])), "issue": key, "text": text}

    def set_fields(self, key, fields: dict, approve=False):
        if not approve:
            return {"dry_run": True, "issue": key, "would_set": fields}
        i = self.issue(key)
        i["fields"].update(fields)
        self._save()
        return {"issue": key, "set": fields}

    def transition(self, key, to_name, approve=False):
        from pmo_agent.schedule import status_alike

        tr = next((t for t in self.transitions(key) if status_alike(t["name"], to_name)), None)
        if not tr:
            return {
                "error": f"'{to_name}' 전이 없음",
                "available": [t["name"] for t in self.transitions(key)],
            }
        if not approve:
            return {"dry_run": True, "issue": key, "would_transition_to": tr["name"]}
        f = self.issue(key)["fields"]
        f["status"] = {"name": tr["name"]}
        f["status_changed_at"] = dt.datetime.now().isoformat(
            timespec="seconds"
        )  # Jira 의 변경 이력에 대응
        self._save()
        return {"issue": key, "status": tr["name"]}

    def done_since(self, days=7, limit=100):
        """최근 days 일 안에 완료로 바뀐 이슈. Jira 의 done_since() 와 같은 역할."""
        from pmo_agent.schedule import DONE

        since = (dt.date.today() - dt.timedelta(days=int(days))).isoformat()
        out = [
            i
            for i in self._load().values()
            if (_field_name(i, "status") or "").strip().lower() in DONE
            and (i["fields"].get("status_changed_at") or "")[:10] >= since
        ]
        return out[:limit]

    def link(self, inward_key, outward_key, link_type="Blocks", approve=False):
        body = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        if not approve:
            return {"dry_run": True, "would_link": body}
        self.issue(inward_key)["fields"].setdefault("issuelinks", []).append(
            {"type": {"name": link_type}, "outwardIssue": {"key": outward_key}}
        )
        self.issue(outward_key)["fields"].setdefault("issuelinks", []).append(
            {"type": {"name": link_type}, "inwardIssue": {"key": inward_key}}
        )
        self._save()
        return {"linked": body}


def _field_name(issue: dict, field: str) -> str:
    v = (issue.get("fields") or {}).get(field) or {}
    return v.get("name") or v.get("displayName") or ""


def make_issue(key, summary, status="To Do", assignee="", duedate=None, points=None, blocks=()):
    """보드에 넣을 이슈 한 건 (Jira search() 응답과 같은 모양)."""
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "status": {"name": status},
            "assignee": {"displayName": assignee} if assignee else None,
            "duedate": duedate,
            "customfield_10016": points,
            "issuelinks": [
                {"type": {"name": "Blocks"}, "outwardIssue": {"key": k}} for k in blocks
            ],
        },
    }
