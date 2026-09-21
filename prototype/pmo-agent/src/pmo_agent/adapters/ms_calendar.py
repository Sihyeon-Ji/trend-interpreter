"""The Outlook calendar adapter (Microsoft Graph) — it reads the time meetings have taken.

The board holds what has to be done; the repository holds what was done.
The calendar holds **how much time is left to do it in** — a number neither of the others has.

**Read-only.** There is no method here that creates or edits an event.
Writing into someone else's calendar by accident is only really prevented by there
being no code path at all.

⚠ Unverified against a real call. It needs an Azure app registration and consent, so only the
   structure is here. With `CALENDAR_BACKEND=memory` the same maths runs on the local calendar.

Setup (by hand):
  1. https://entra.microsoft.com → App registrations → any name, allow personal accounts
  2. Authentication → turn on "Allow public client flows" (this uses the device code flow)
  3. API permissions → Microsoft Graph → Delegated → Calendars.Read, User.Read → consent
  4. MS_CLIENT_ID=<Application (client) ID> in .env

The token comes from the device code flow and is cached in .ms_token.json (gitignored).
No client secret — this is a public client, so there is no reason to keep a secret in a file.
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
    """A Graph call or the authentication failed."""


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
            return json.loads(body)  # the device code flow returns an error body while it waits
        except json.JSONDecodeError:
            raise CalendarError(f"Graph auth {e.code}: {body}") from None


class MSCalendar:
    """The Outlook calendar. Same methods and shapes as MemoryCalendar (ports.Calendar)."""

    def __init__(self, client_id: str | None = None, workday_hours: float = WORKDAY_HOURS):
        self.client_id = client_id or env("MS_CLIENT_ID")
        self.source = "outlook"
        self.workday_hours = workday_hours
        self._token: str | None = None
        if not self.client_id:
            raise CalendarError(
                "MS_CLIENT_ID is not set — see the setup steps in the module docstring"
            )

    # ---------- authentication ----------
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
        """Use the cached token if there is one, otherwise run the device code flow.

        The user has to type a code in a browser, so it is interactive — on a server the cache
        has to be there already.
        """
        if self._token:
            return self._token
        cached = self._cached()
        if cached:
            self._token = cached
            return cached
        start = _post(f"{AUTHORITY}/devicecode", {"client_id": self.client_id, "scope": SCOPE})
        if "user_code" not in start:
            raise CalendarError(f"could not get a device code: {str(start)[:200]}")
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
                raise CalendarError(f"authentication failed: {blob.get('error_description', blob)}")
            if blob.get("error") == "slow_down":
                interval += 5
        raise CalendarError("the device code expired. Try again.")

    def _get(self, path: str, params: dict | None = None):
        url = f"{GRAPH}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token()}",
                "Accept": "application/json",
                # Without an explicit time zone these come back in UTC and the day boundary shifts
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

    # ---------- reads ----------
    def whoami(self) -> str:
        return self._get("/me", {"$select": "displayName,mail"}).get("displayName", "?")

    def events(self, days: int = 20, attendee: str = "", start=None) -> list:
        """Events in the `days` days from `start` (today by default). Graph only ever
        gives *my* calendar — seeing the whole team needs each person's consent or an
        organisation permission.

        `attendee` filters the return value; the query is always about the logged-in user.
        An earlier `start` looks backwards, which is what cause.py needs.
        """
        first = start or _dt.date.today()
        if isinstance(first, str):
            first = _dt.date.fromisoformat(first[:10])
        start = _dt.datetime.combine(first, _dt.time.min)
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
                continue  # drop events that do not actually consume time
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
        """{person: {ISO date: meeting hours}} — the shape availability.from_busy_hours takes."""
        out: dict[str, dict[str, float]] = {}
        for e in self.events(days):
            out.setdefault(e["attendee"], {})
            out[e["attendee"]][e["date"]] = out[e["attendee"]].get(e["date"], 0.0) + e["hours"]
        return out
