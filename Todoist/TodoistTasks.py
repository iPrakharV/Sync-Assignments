from __future__ import annotations

import os
import json
import logging
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from todoist_api_python.api import TodoistAPI

from Summary import SyncReport

log = logging.getLogger(__name__)

COURSE_COLORS = ['blue', 'green', 'violet', 'teal', 'magenta', 'lime_green', 'grape', 'salmon', 'mint_green', 'lavender']
KIND_COLORS = {'exam': 'red', 'quiz': 'orange', 'assignment': 'sky_blue'}
USER_URL = 'https://api.todoist.com/api/v1/user'
KEEP_CLOSED_FOR = datetime.timedelta(days=14)
DUE_SOON = datetime.timedelta(hours=48)


def flatten(paginator):
    return [item for page in paginator for item in page]


def retrying_session():
    """Retries dropped connections and Todoist 429/5xx responses, waiting 0s, 4s, 8s, 16s between tries.
    POSTs are retried too: the SDK sends the same X-Request-ID on each try, which Todoist uses to
    ignore duplicates, so a retried add_task can't create the task twice."""
    retry = Retry(total=4, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=None, respect_retry_after_header=True, raise_on_status=False)
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=retry))
    return session


class TodoistTasks:
    def __init__(self, settings, dry_run=False, state_file='todoist_state.json'):
        self.settings = settings
        self.dry_run = dry_run
        self.path = os.path.dirname(os.path.abspath(__file__))
        self.state_path = os.path.join(self.path, state_file)
        self.token = self.get_api_token()
        self.session = retrying_session()
        self.api = TodoistAPI(self.token, session=self.session)
        self.project_id = None
        self.section_id = None
        self.assignee_id = None  # your user ID, when tasks should be assigned to you
        self.open_tasks = {}  # task_id -> Task, open tasks in the target project/section
        self.created_ids = set()

    def get_api_token(self):
        with open(os.path.join(self.path, 'Token.json'), 'r') as file:
            return json.load(file)['API_Token']

    # ---- state: {assignment key: {task_id, name, course, due, closed}} ----

    def read_state(self):
        if not os.path.exists(self.state_path):
            return {}
        with open(self.state_path, 'r') as f:
            return json.load(f).get('tasks', {})

    def write_state(self, state):
        if self.dry_run:
            return
        with open(self.state_path, 'w') as f:
            json.dump({'version': 2, 'tasks': state}, f, indent=2)

    # ---- Todoist lookups ----

    def resolve_destination(self):
        project_name, section_name = self.settings['project'], self.settings.get('section')
        project = next((p for p in flatten(self.api.get_projects()) if p.name == project_name), None)
        if not project:
            raise RuntimeError(f"Todoist project '{project_name}' not found.")
        self.project_id = project.id
        # Todoist only allows assignees in shared projects
        if self.settings.get('assign_to_me') and project.is_shared:
            self.assignee_id = self.get_user_id()
        if section_name:
            section = next((s for s in flatten(self.api.get_sections(project_id=project.id))
                            if s.name == section_name), None)
            if not section:
                raise RuntimeError(f"Section '{section_name}' not found in project '{project_name}'.")
            self.section_id = section.id

        tasks = flatten(self.api.get_tasks(project_id=self.project_id, section_id=self.section_id))
        self.open_tasks = {task.id: task for task in tasks}

    def get_user_id(self):
        response = self.session.get(USER_URL, headers={'Authorization': f'Bearer {self.token}'}, timeout=60)
        response.raise_for_status()
        return str(response.json()['id'])

    def labels_for(self, assignment):
        course_label = self.settings['course_labels'].get(
            assignment.course_code, assignment.course_code.replace(' ', ''))
        labels = [course_label]
        if self.settings.get('type_labels'):
            labels.append(assignment.kind)
        return labels

    def ensure_labels(self, assignments):
        wanted = {label for assignment in assignments for label in self.labels_for(assignment)}
        existing = {label.name for label in flatten(self.api.get_labels())}
        colors = self.settings.get('label_colors', {})
        course_labels = sorted(set(self.settings['course_labels'].values()))
        for name in sorted(wanted - existing):
            if name in colors:
                color = colors[name]
            elif name in KIND_COLORS:
                color = KIND_COLORS[name]
            elif name in course_labels:
                color = COURSE_COLORS[course_labels.index(name) % len(COURSE_COLORS)]
            else:
                color = 'charcoal'
            log.info("%s label '%s' (%s)", "Would create" if self.dry_run else "Creating", name, color)
            if not self.dry_run:
                self.api.add_label(name=name, color=color)

    def find_existing(self, assignment):
        """Adopt a matching open task (e.g. if the state file was lost) instead of creating a duplicate."""
        course_label = self.labels_for(assignment)[0]
        for task in self.open_tasks.values():
            if task.content == assignment.name and course_label in (task.labels or []):
                return task
        return None

    def get_task(self, task_id):
        """Returns the task, or None if it was deleted."""
        if task_id in self.open_tasks:
            return self.open_tasks[task_id]
        try:
            return self.api.get_task(task_id)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    # ---- sync ----

    def create(self, assignment):
        if self.dry_run:
            self.created_ids.add('dry-run')
            return 'dry-run'
        task = self.api.add_task(
            content=assignment.name,
            description=assignment.description(),
            labels=self.labels_for(assignment),
            priority=self.settings.get('priority', 2),
            project_id=self.project_id,
            section_id=self.section_id,
            due_datetime=assignment.due,
            assignee_id=self.assignee_id,
        )
        self.created_ids.add(task.id)
        return task.id

    def update(self, task, assignment):
        if self.dry_run:
            return
        labels = list(dict.fromkeys((task.labels or []) + self.labels_for(assignment)))
        self.api.update_task(task.id, due_datetime=assignment.due,
                             description=assignment.description(), labels=labels)

    def sync_one(self, assignment, state, report, now):
        entry = state.get(assignment.key)
        label = f"{assignment.name} [{assignment.course_code}]"

        if entry and entry.get('closed'):
            report.skipped.append(f"{label} (you completed or deleted it)")
            return

        if entry is None:
            if assignment.due <= now:
                report.skipped.append(f"{label} (already past due)")
                return
            existing = self.find_existing(assignment)
            if existing:
                state[assignment.key] = self.entry(existing.id, assignment, due=None)
                entry = state[assignment.key]
                log.info("Adopted existing Todoist task for %s", label)
            else:
                task_id = self.create(assignment)
                state[assignment.key] = self.entry(task_id, assignment)
                report.created.append(f"{label} — due {assignment.due_text}")
                return

        previous_due = datetime.datetime.fromisoformat(entry['due']) if entry.get('due') else None
        if previous_due == assignment.due:
            report.unchanged.append(label)
            return

        task = self.get_task(entry['task_id'])
        if task is None or task.is_completed:
            entry['closed'] = True
            report.skipped.append(f"{label} (you completed or deleted it)")
            return
        self.update(task, assignment)
        entry['due'] = assignment.due.isoformat()
        if previous_due:
            report.updated.append(f"{label} — due date moved to {assignment.due_text}")
        else:
            report.updated.append(f"{label} — refreshed details")

    @staticmethod
    def entry(task_id, assignment, due='from-assignment'):
        return {
            'task_id': task_id,
            'name': assignment.name,
            'course': assignment.course_code,
            'due': assignment.due.isoformat() if due == 'from-assignment' else due,
            'closed': False,
            'synced_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
        }

    def assign_to_me(self, state, report):
        """Assigns each synced task to you once. Tasks created this run already are; older ones and
        adopted ones get assigned here if nobody is assigned. Later reassignments are left alone."""
        if not self.assignee_id:
            return
        for entry in state.values():
            if entry.get('assigned') or entry.get('closed'):
                continue
            task = self.open_tasks.get(entry['task_id'])
            if entry['task_id'] in self.created_ids or (task and task.assignee_id):
                entry['assigned'] = True
            elif task:
                if not self.dry_run:
                    self.api.update_task(task.id, assignee_id=self.assignee_id)
                entry['assigned'] = True
                report.updated.append(f"{entry['name']} [{entry['course']}] — assigned to you")

    def sync_tasks(self, assignments):
        report = SyncReport(target='Todoist')
        now = datetime.datetime.now().astimezone()
        self.resolve_destination()
        self.ensure_labels(assignments.values())

        state = self.read_state()
        for assignment in sorted(assignments.values(), key=lambda a: a.due):
            try:
                self.sync_one(assignment, state, report, now)
            except Exception as e:
                log.exception("Failed to sync %s", assignment.key)
                report.errors.append(f"{assignment.name} [{assignment.course_code}]: {e}")
        try:
            self.assign_to_me(state, report)
        except Exception as e:
            log.exception("Failed to assign tasks")
            report.errors.append(f"Assigning tasks to you: {e}")

        # Forget tasks well past their due date so the state file doesn't grow forever
        for key, entry in list(state.items()):
            if entry.get('due') and datetime.datetime.fromisoformat(entry['due']) < now - KEEP_CLOSED_FOR:
                del state[key]
        self.write_state(state)

        for entry in state.values():
            if entry.get('closed') or not entry.get('due'):
                continue
            due = datetime.datetime.fromisoformat(entry['due'])
            still_open = entry['task_id'] in self.open_tasks or entry['task_id'] in self.created_ids
            if still_open and now < due <= now + DUE_SOON:
                report.due_soon.append((entry['name'], due))
        report.due_soon.sort(key=lambda item: item[1])
        return report
