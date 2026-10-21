from __future__ import annotations

import logging
import platform
import subprocess
import datetime
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class SyncReport:
    target: str
    created: list = field(default_factory=list)
    updated: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)
    skipped: list = field(default_factory=list)   # past due, completed or deleted by you
    errors: list = field(default_factory=list)
    due_soon: list = field(default_factory=list)  # [(name, due datetime)]

    @property
    def changed(self):
        return bool(self.created or self.updated)

    def headline(self):
        parts = [f"{len(self.created)} new", f"{len(self.updated)} updated"]
        if self.errors:
            parts.append(f"{len(self.errors)} failed")
        return f"{self.target}: " + ', '.join(parts)

    def details(self):
        lines = [self.headline()]
        for label, items in (('New', self.created), ('Updated', self.updated),
                             ('Skipped', self.skipped), ('Failed', self.errors)):
            for item in items:
                lines.append(f"  {label}: {item}")
        if self.due_soon:
            lines.append("  Due in the next 48h:")
            for name, due in self.due_soon:
                lines.append(f"    - {name} ({format_due(due)})")
        return '\n'.join(lines)


def format_due(due):
    local = due.astimezone()
    today = datetime.datetime.now().astimezone().date()
    if local.date() == today:
        day = 'today'
    elif local.date() == today + datetime.timedelta(days=1):
        day = 'tomorrow'
    else:
        day = local.strftime('%a')
    return f"{day} {local.strftime('%I:%M %p').lstrip('0')}"


def notification_text(reports):
    message = ' · '.join(report.headline() for report in reports)
    due_soon = sorted({item for report in reports for item in report.due_soon}, key=lambda item: item[1])
    if due_soon:
        message += '\nDue soon: ' + ', '.join(f"{name} ({format_due(due)})" for name, due in due_soon[:4])
    return message


def notify(title, message):
    """macOS banner notification; quietly does nothing elsewhere."""
    if platform.system() != 'Darwin':
        return
    script = ['-e', 'on run argv', '-e', 'display notification (item 1 of argv) with title (item 2 of argv)',
              '-e', 'end run']
    try:
        subprocess.run(['osascript', *script, message, title], check=True, capture_output=True, timeout=10)
    except Exception as e:
        log.warning("Couldn't show notification: %s", e)
