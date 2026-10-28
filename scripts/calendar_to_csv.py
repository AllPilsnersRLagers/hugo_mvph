# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "icalendar>=6",
#     "recurring-ical-events>=3",
# ]
# ///
"""Fill the food truck and special event tables from the public Google Calendar.

Only calendar entries whose title starts with a tag are published:

    Food: <truck name>     description = food style
    Music: <artist>        shown as "Live Music"
    Event: <event name>    description = description

Untagged entries are private and skipped.

Run with:  uv run scripts/calendar_to_csv.py
"""

import csv
import html
import re
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

CALENDAR_URL = (
    "https://calendar.google.com/calendar/ical/"
    "27cea41c4176f2d71d09dff05a70d4ca0fd40ee9de41a411d614415c044fdeaf"
    "%40group.calendar.google.com/public/basic.ics"
)
TIMEZONE = ZoneInfo("America/New_York")
DAYS_AHEAD = 90

MENU_DIR = Path(__file__).resolve().parent.parent / "assets" / "beer_menus"
TRUCK_CSV = MENU_DIR / "truck_menu.csv"
EVENT_CSV = MENU_DIR / "event_menu.csv"

TAG_PATTERN = re.compile(r"^\s*(food|music|event)\s*:\s*(.+?)\s*$", re.IGNORECASE)
MONTHS = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "June",
          "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]


def fetch_calendar(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return icalendar.Calendar.from_ical(response.read())


def local_start(event):
    """Start of the event as a datetime in TIMEZONE (all-day events start at midnight)."""
    start = event["DTSTART"].dt
    if isinstance(start, datetime):
        if start.tzinfo is None:
            return start.replace(tzinfo=TIMEZONE)
        return start.astimezone(TIMEZONE)
    return datetime(start.year, start.month, start.day, tzinfo=TIMEZONE)


def ordinal(day):
    if 11 <= day % 100 <= 13:
        return f"{day}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def format_date(day):
    """e.g. 'Wed. Oct. 28th', matching the hand-written tables."""
    return f"{day.strftime('%a')}. {MONTHS[day.month - 1]} {ordinal(day.day)}"


def description_lines(event):
    """Google sends descriptions as plain text or light HTML; return the non-empty text lines."""
    text = str(event.get("DESCRIPTION", ""))
    text = re.sub(r"<br\s*/?>|</p>|</div>", "\n", text, flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return [line.strip() for line in text.splitlines() if line.strip()]


def build_rows(calendar, today):
    window_start = datetime(today.year, today.month, today.day, tzinfo=TIMEZONE)
    window_end = window_start + timedelta(days=DAYS_AHEAD)
    occurrences = recurring_ical_events.of(calendar).between(window_start, window_end)

    trucks, events = [], []
    for event in sorted(occurrences, key=local_start):
        match = TAG_PATTERN.match(str(event.get("SUMMARY", "")))
        if not match:
            continue
        tag, name = match.group(1).lower(), match.group(2)
        start = local_start(event)
        if start.date() < today:
            continue
        when = format_date(start.date())
        lines = description_lines(event)

        if tag == "food":
            trucks.append([when, name, " ".join(lines)])
        elif tag == "music":
            events.append([when, "Live Music", name])
        else:
            events.append([when, name, " ".join(lines)])
    return trucks, events


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header, *rows])


def main():
    today = datetime.now(TIMEZONE).date()
    trucks, events = build_rows(fetch_calendar(CALENDAR_URL), today)
    write_csv(TRUCK_CSV, ["Date", "Name", "Food Style"], trucks)
    write_csv(EVENT_CSV, ["Date", "Name", "Description"], events)
    print(f"Wrote {len(trucks)} food trucks and {len(events)} events from {today}.")


if __name__ == "__main__":
    main()
