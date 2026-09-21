"""Outlook 캘린더 어댑터 (Microsoft Graph) — 회의로 먹힌 시간을 읽는다.

보드는 '무엇을 해야 하나', 저장소는 '무엇을 했나'를 담는다.
캘린더는 **'무엇을 할 시간이 남았나'** 를 담는다 — 다른 두 곳에는 없는 값이다.

**읽기 전용이다.** 일정을 만들거나 고치는 메서드를 두지 않는다.
남의 캘린더에 무언가를 쓰는 사고는 코드 경로가 없어야 막힌다.

⚠ 실호출 미검증. Azure 앱 등록과 동의가 필요해 구조만 준비돼 있다.
   `CALENDAR_BACKEND=memory` 로 두면 로컬 캘린더로 같은 계산이 돈다.

준비 (사람이 직접):
  1. https://entra.microsoft.com → 앱 등록 → 이름 아무거나, 개인 계정 허용
  2. 인증 → '퍼블릭 클라이언트 흐름 허용' 켜기 (기기 코드 흐름을 쓴다)
  3. API 사용 권한 → Microsoft Graph → 위임됨 → Calendars.Read, User.Read → 동의
  4. .env 에 MS_CLIENT_ID=<응용 프로그램(클라이언트) ID>

토큰은 기기 코드 흐름으로 받아 .ms_token.json 에 캐시한다 (.gitignore 대상).
클라이언트 비밀은 쓰지 않는다 — 퍼블릭 클라이언트라 비밀을 파일에 둘 이유가 없다.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from pmo_agent.availability import WORKDAY_HOURS
from pmo_agent.env import env, project_root

AUTHORITY = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "Calendars.Read User.Read offline_access"
TOKEN_CACHE = str(project_root() / ".ms_token.json")
TIMEOUT = 40


class CalendarError(RuntimeError):
    """Graph 호출 또는 인증 실패."""


def _post(url: str, form: dict) -> dict:
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        body = e.read()[:400].decode("utf-8", "ignore")
        try:
            return json.loads(body)  # 기기 코드 흐름은 대기 중에도 오류 본문을 준다
        except json.JSONDecodeError:
            raise CalendarError(f"Graph 인증 {e.code}: {body}") from None


class MSCalendar:
    """Outlook 캘린더. MemoryCalendar 와 메서드 이름·반환 모양이 같다 (ports.Calendar)."""

    def __init__(self, client_id: str | None = None, workday_hours: float = WORKDAY_HOURS):
        self.client_id = client_id or env("MS_CLIENT_ID")
        self.source = "outlook"
        self.workday_hours = workday_hours
        self._token: str | None = None
        if not self.client_id:
            raise CalendarError("MS_CLIENT_ID 미설정 — 모듈 docstring 의 준비 단계를 보라")

    # ---------- 인증 ----------
    def _cached(self) -> str | None:
        if not os.path.exists(TOKEN_CACHE):
            return None
        try:
            with open(TOKEN_CACHE, encoding="utf-8") as handle:
                blob = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None
        if blob.get("expires_at", 0) > time.time() + 60:
            return blob.get("access_token")
        return None

    def _save(self, blob: dict) -> None:
        blob["expires_at"] = time.time() + float(blob.get("expires_in", 3600))
        with open(TOKEN_CACHE, "w", encoding="utf-8") as handle:
            json.dump(blob, handle)

    def token(self) -> str:
        """캐시된 토큰이 있으면 쓰고, 없으면 기기 코드 흐름으로 받는다.

        사용자가 브라우저에서 코드를 넣어야 하므로 대화형이다 — 서버에서는 캐시가 있어야 한다.
        """
        if self._token:
            return self._token
        cached = self._cached()
        if cached:
            self._token = cached
            return cached
        start = _post(f"{AUTHORITY}/devicecode", {"client_id": self.client_id, "scope": SCOPE})
        if "user_code" not in start:
            raise CalendarError(f"기기 코드 발급 실패: {str(start)[:200]}")
        print(f"\n  {start.get('message', '')}\n")
        deadline = time.time() + float(start.get("expires_in", 900))
        interval = float(start.get("interval", 5))
        while time.time() < deadline:
            time.sleep(interval)
            blob = _post(
                f"{AUTHORITY}/token",
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": self.client_id,
                    "device_code": start["device_code"],
                },
            )
            if "access_token" in blob:
                self._save(blob)
                self._token = blob["access_token"]
                return self._token
            if blob.get("error") not in ("authorization_pending", "slow_down"):
                raise CalendarError(f"인증 실패: {blob.get('error_description', blob)}")
            if blob.get("error") == "slow_down":
                interval += 5
        raise CalendarError("기기 코드가 만료됐다. 다시 시도하라.")

    def _get(self, path: str, params: dict | None = None):
        url = f"{GRAPH}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token()}",
                "Accept": "application/json",
                # 시간대를 명시하지 않으면 UTC 로 오고, 하루 경계가 밀린다
                "Prefer": 'outlook.timezone="Asia/Seoul"',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            raise CalendarError(
                f"Graph {path} → {e.code}: {e.read()[:300].decode('utf-8', 'ignore')}"
            ) from None

    # ---------- 읽기 ----------
    def whoami(self) -> str:
        return self._get("/me", {"$select": "displayName,mail"}).get("displayName", "?")

    def events(self, days: int = 20, attendee: str = "") -> list:
        """앞으로 days 일의 일정. Graph 는 '내 캘린더'만 준다 —
        팀 전체를 보려면 각자 동의하거나 조직 권한이 필요하다.

        attendee 는 반환값을 거르는 용도이고, 조회 대상은 항상 로그인한 사용자다.
        """
        start = _dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + _dt.timedelta(days=int(days))
        raw = self._get(
            "/me/calendarView",
            {
                "startDateTime": start.isoformat(),
                "endDateTime": end.isoformat(),
                "$select": "subject,start,end,isAllDay,showAs",
                "$orderby": "start/dateTime",
                "$top": "200",
            },
        ).get("value", [])
        me = self.whoami()
        out = []
        for item in raw:
            if item.get("showAs") in ("free", "workingElsewhere"):
                continue  # 시간을 실제로 먹지 않는 일정은 뺀다
            hours, day, hhmm = self._duration(item)
            if hours <= 0:
                continue
            out.append(
                {
                    "attendee": me,
                    "date": day,
                    "start": hhmm,
                    "hours": hours,
                    "title": item.get("subject", ""),
                }
            )
        return [e for e in out if not attendee or e["attendee"] == attendee]

    def _duration(self, item: dict) -> tuple:
        if item.get("isAllDay"):
            day = (item.get("start", {}).get("dateTime") or "")[:10]
            return self.workday_hours, day, "00:00"
        try:
            s = _dt.datetime.fromisoformat(item["start"]["dateTime"][:19])
            e = _dt.datetime.fromisoformat(item["end"]["dateTime"][:19])
        except (KeyError, ValueError):
            return 0.0, "", ""
        return round((e - s).total_seconds() / 3600.0, 2), s.date().isoformat(), s.strftime("%H:%M")

    def busy_hours(self, days: int = 20) -> dict:
        """{사람: {ISO날짜: 회의시간}} — availability.from_busy_hours 가 받는 모양."""
        out: dict[str, dict[str, float]] = {}
        for e in self.events(days):
            out.setdefault(e["attendee"], {})
            out[e["attendee"]][e["date"]] = out[e["attendee"]].get(e["date"], 0.0) + e["hours"]
        return out
