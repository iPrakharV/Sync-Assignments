import os
import json
import logging
import datetime
from googleapiclient.discovery import build

from Google.Auth import load_credentials
from Summary import SyncReport

log = logging.getLogger(__name__)


class GCalendarTasks:
    """Syncs assignments to Google Tasks (despite the name, it doesn't touch Google Calendar)."""
    SCOPES = ['https://www.googleapis.com/auth/tasks']

    def __init__(self, dry_run=False, credentials_path='client_secret.json', token_path='TasksToken.json'):
        self.path = os.path.dirname(os.path.abspath(__file__))
        self.dry_run = dry_run
        self.credentials_path = os.path.join(self.path, credentials_path)
        self.token_path = os.path.join(self.path, token_path)
        self.log_path = os.path.join(self.path, 'gTasks_log.json')
        self.service = None

    def authenticate(self, interactive=True):
        creds = load_credentials(self.credentials_path, self.token_path, self.SCOPES, interactive)
        self.service = build('tasks', 'v1', credentials=creds)

    def read_task_log(self):
        if not os.path.exists(self.log_path):
            return {}
        with open(self.log_path, 'r') as f:
            return json.load(f)

    def write_task_log(self, tasks_log):
        if not self.dry_run:
            with open(self.log_path, 'w') as f:
                json.dump(tasks_log, f, indent=2)

    def sync_tasks(self, assignments):
        report = SyncReport(target='Google Tasks')
        now = datetime.datetime.now().astimezone()
        tasks_log = {key: entry for key, entry in self.read_task_log().items()
                     if datetime.datetime.fromisoformat(entry['due']) >= now}

        for assignment in assignments.values():
            label = f"{assignment.name} [{assignment.course_code}]"
            if assignment.key in tasks_log:
                report.unchanged.append(label)
                continue
            if assignment.due <= now:
                report.skipped.append(f"{label} (already past due)")
                continue
            try:
                if not self.dry_run:
                    # Google Tasks only stores the date part of `due`
                    due = assignment.due.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
                    body = {'title': f"{assignment.name} - {assignment.course_code}",
                            'notes': assignment.description(), 'due': due}
                    self.service.tasks().insert(tasklist='@default', body=body).execute(num_retries=5)
                tasks_log[assignment.key] = {'due': assignment.due.isoformat()}
                report.created.append(f"{label} — due {assignment.due_text}")
            except Exception as e:
                log.exception("Failed to add %s to Google Tasks", assignment.key)
                report.errors.append(f"{label}: {e}")

        self.write_task_log(tasks_log)
        return report
