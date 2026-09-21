"""Jira Cloud REST v3 어댑터 — API 토큰(Basic auth) 직결. Claude 커넥터/OAuth 사용하지 않음.
안전 가드: WRITE_ALLOWLIST 에 없는 사이트로는 쓰기 호출이 아예 나가지 않는다 (회사 실 Jira 사고
방지).
쓰기 함수는 dry_run 기본값 True — approve=True 를 명시해야 실제로 반영된다."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from pmo_agent.env import env

DONE_NAMES = ("완료", "Done", "종료")  # 사이트 언어에 따라 달라 둘 다 넣는다


def _host(v: str) -> str:
    """사이트 문자열을 호스트만 남겨 정규화. https:// 나 끝 슬래시가 붙어도 같은 사이트로 본다.
    (.env 에 https:// 를 붙여 적었다가 쓰기가 통째로 막히는 사고를 막는다.)"""
    return (v or "").strip().replace("https://", "").replace("http://", "").rstrip("/").lower()


def _alike(a, b):
    """상태 이름 비교는 schedule 의 별칭표에 맡긴다 (순환 import 를 피해 지연 로딩)."""
    from pmo_agent.schedule import status_alike

    return status_alike(a, b)


class WriteBlocked(RuntimeError):
    pass


class Jira:
    def __init__(self, site=None, email=None, token=None, project=None):
        self.site = _host(site or env("JIRA_SITE"))
        self.email = email or env("JIRA_EMAIL")
        self.token = token or env("JIRA_API_TOKEN")
        self.project = project or env("JIRA_PROJECT_KEY", "ECHO")
        self.allow = [_host(s) for s in env("WRITE_ALLOWLIST", "localhost").split(",") if s.strip()]
        if not (self.site and self.email and self.token):
            raise RuntimeError("JIRA_SITE / JIRA_EMAIL / JIRA_API_TOKEN 미설정 — SETUP.md 1-2 참고")

    # ---------- low level ----------
    def _call(self, method, path, body=None, params=None, write=False):
        if write and self.site not in self.allow:
            raise WriteBlocked(
                f"쓰기 차단: {self.site} 는 WRITE_ALLOWLIST({self.allow}) 에 없음. 샌드박스에서만 "
                f"쓰기 허용."
            )
        url = f"https://{self.site}/rest/api/3{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        auth = base64.b64encode(f"{self.email}:{self.token}".encode()).decode()
        req = urllib.request.Request(
            url,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Basic {auth}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "echo-pmo",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
                return json.loads(raw) if raw else {"status": r.status}
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"Jira {method} {path} -> HTTP {e.code}: {e.read()[:400].decode('utf-8', 'ignore')}"
            ) from None

    @staticmethod
    def adf(text: str) -> dict:
        """Jira v3 는 본문이 ADF(Atlassian Document Format)."""
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": t}]}
                for t in text.split("\n")
                if t
            ],
        }

    # ---------- read ----------
    def whoami(self):
        return self._call("GET", "/myself")

    def project_info(self):
        return self._call("GET", f"/project/{self.project}")

    # fields 는 키워드 전용이다 — 위치 인자 순서를 로컬 보드와 맞춰야
    # 두 어댑터가 실제로 교체 가능하다 (ports.Board).
    def search(
        self,
        jql=None,
        limit=100,
        *,
        fields=(
            "summary",
            "status",
            "assignee",
            "duedate",
            "priority",
            "issuelinks",
            "parent",
            "labels",
            "customfield_10016",
        ),
    ):
        jql = jql or f"project = {self.project} ORDER BY created DESC"
        out: list[dict] = []
        start = 0
        while True:
            j = self._call(
                "POST",
                "/search/jql",
                {
                    "jql": jql,
                    "maxResults": min(100, limit - len(out)),
                    "nextPageToken": None if start == 0 else start,
                    "fields": list(fields),
                },
            )
            out += j.get("issues", [])
            start = j.get("nextPageToken")
            if not start or len(out) >= limit:
                break
        return out

    def issue(self, key):
        return self._call("GET", f"/issue/{key}")

    def done_since(self, days=7, limit=100):
        """최근 days 영업일 안에 '완료'로 바뀐 이슈. Jira 의 상태 변경 이력(JQL CHANGED)을 쓴다 —
        우리 에이전트를 거치지 않고 사람이 직접 바꾼 것도 잡힌다."""
        names = ", ".join(f'"{n}"' for n in DONE_NAMES)
        return self.search(
            f"project = {self.project} AND status CHANGED TO ({names}) AFTER -{int(days)}d",
            limit=limit,
        )

    def transitions(self, key):
        return self._call("GET", f"/issue/{key}/transitions").get("transitions", [])

    # ---------- write (approval-gated) ----------
    def create_issue(
        self,
        summary,
        description="",
        issuetype="Task",
        assignee_id=None,
        duedate=None,
        parent=None,
        extra=None,
        approve=False,
    ):
        fields = {
            "project": {"key": self.project},
            "summary": summary,
            "issuetype": {"name": issuetype},
        }
        if description:
            fields["description"] = self.adf(description)
        if assignee_id:
            fields["assignee"] = {"id": assignee_id}
        if duedate:
            fields["duedate"] = duedate
        if parent:
            fields["parent"] = {"key": parent}
        if extra:
            fields.update(extra)
        if not approve:
            return {"dry_run": True, "would_create": fields}
        return self._call("POST", "/issue", {"fields": fields}, write=True)

    def comment(self, key, text, approve=False):
        if not approve:
            return {"dry_run": True, "would_comment_on": key, "text": text}
        return self._call("POST", f"/issue/{key}/comment", {"body": self.adf(text)}, write=True)

    def set_fields(self, key, fields: dict, approve=False):
        if not approve:
            return {"dry_run": True, "issue": key, "would_set": fields}
        return self._call("PUT", f"/issue/{key}", {"fields": fields}, write=True)

    def transition(self, key, to_name, approve=False):
        trs = self.transitions(key)
        tr = next(
            (t for t in trs if _alike(t["name"], to_name) or _alike(t["to"]["name"], to_name)), None
        )
        if not tr:
            return {
                "error": f"'{to_name}' 전이 없음",
                "available": [t["name"] for t in self.transitions(key)],
            }
        if not approve:
            return {"dry_run": True, "issue": key, "would_transition_to": tr["name"]}
        return self._call(
            "POST", f"/issue/{key}/transitions", {"transition": {"id": tr["id"]}}, write=True
        )

    def link(self, inward_key, outward_key, link_type="Blocks", approve=False):
        body = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        if not approve:
            return {"dry_run": True, "would_link": body}
        return self._call("POST", "/issueLink", body, write=True)


if __name__ == "__main__":
    j = Jira()
    me = j.whoami()
    print(
        "연결 OK:",
        me.get("displayName"),
        me.get("emailAddress"),
        "| site",
        j.site,
        "| project",
        j.project,
    )
    print("쓰기 허용 사이트:", j.allow)
    issues = j.search(limit=5)
    print(f"이슈 {len(issues)}건 샘플:", [(i["key"], i["fields"]["summary"][:30]) for i in issues])
