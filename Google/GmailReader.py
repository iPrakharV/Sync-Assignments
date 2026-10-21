from __future__ import annotations

import os
import re
import html
import base64
import logging
import datetime
from zoneinfo import ZoneInfo
from googleapiclient.discovery import build

from Assignment import Assignment
from Google.Auth import load_credentials

log = logging.getLogger(__name__)

# "Activity summary for PFW Fall 2026 ECON 20101-05I Intro To Microeconomics XLST"
HEADER_PATTERN = re.compile(
    r'^Activity summary for (?:\S+ )?(?:(?:Fall|Spring|Summer|Winter) \d{4} )?'
    r'(?P<dept>[A-Z]{2,5}) (?P<number>\d{3,5})(?:-\S+)? (?P<title>.+?)(?: (?:LEC|XLST|LAB|REC|PSO|SD|DIS|ONL|IND|CLN))?$')
# "Quiz (1)"
CATEGORY_PATTERN = re.compile(r'^(?P<category>[A-Za-z][A-Za-z ]*?) \(\d+\)$')
# "Homework#2<https://...> - Due date is in 3 days"
ITEM_PATTERN = re.compile(r'^(?P<name>.+?)\s*(?:<(?P<url>https?://[^>]+)>)?\s+-\s+Due date is\b')
# "Sunday, October 25, 2026 11:59 PM EDT"
DATE_PATTERN = re.compile(
    r'(?P<text>(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), '
    r'(?P<date>[A-Z][a-z]+ \d{1,2}, \d{4}) (?P<time>\d{1,2}:\d{2} [AP]M)(?: (?P<tz>[A-Z]{2,4}))?)')
# "Go to Quiz >><https://...>"
LIST_LINK_PATTERN = re.compile(r'^Go to .*?>>\s*<(?P<url>https?://[^>]+)>')

TZ_OFFSETS = {'EDT': -4, 'EST': -5, 'CDT': -5, 'CST': -6, 'MDT': -6, 'MST': -7,
              'PDT': -7, 'PST': -8, 'UTC': 0, 'GMT': 0}


class GmailReader:
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def __init__(self, credentials_path='client_secret.json', token_path='GmailToken.json', timezone='America/New_York'):
        path = os.path.dirname(os.path.abspath(__file__))
        self.credentials_path = os.path.join(path, credentials_path)
        self.token_path = os.path.join(path, token_path)
        self.timezone = ZoneInfo(timezone)
        self.service = None

    def authenticate(self, interactive=True):
        creds = load_credentials(self.credentials_path, self.token_path, self.SCOPES, interactive)
        self.service = build('gmail', 'v1', credentials=creds)

    def fetch_summaries(self, senders, lookback_days):
        """Returns [(received_datetime, body_text)] oldest first, so newer emails win on conflicts."""
        query = f'from:({" OR ".join(senders)}) subject:"Activity summary" newer_than:{lookback_days}d'
        messages, page_token = [], None
        while True:
            result = self.service.users().messages().list(
                userId='me', q=query, pageToken=page_token).execute(num_retries=5)
            messages += result.get('messages', [])
            page_token = result.get('nextPageToken')
            if not page_token:
                break
        log.info("Found %d summary emails from the last %d days.", len(messages), lookback_days)

        summaries = []
        for message in messages:
            full = self.service.users().messages().get(
                userId='me', id=message['id'], format='full').execute(num_retries=5)
            received = datetime.datetime.fromtimestamp(int(full['internalDate']) / 1000, tz=self.timezone)
            body = self.get_message_body(full['payload'])
            if body:
                summaries.append((received, body))
            else:
                log.warning("No readable body in message %s", message['id'])
        summaries.sort(key=lambda summary: summary[0])
        return summaries

    @staticmethod
    def get_message_body(payload):
        def find(part, mime_type):
            if part.get('mimeType') == mime_type and part.get('body', {}).get('data'):
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', 'replace')
            for child in part.get('parts', []) or []:
                found = find(child, mime_type)
                if found:
                    return found
            return None

        text = find(payload, 'text/plain')
        if text:
            return text
        page = find(payload, 'text/html')
        return html_to_text(page) if page else None

    def parse_summary(self, body, received=None):
        lines = [line.strip() for line in body.replace('\r', '').split('\n')]
        course_code, course_title = None, None
        category = 'Assignment'
        category_items = []
        assignments = []

        for i, line in enumerate(lines):
            line = re.sub(r'^(FW|Fwd|RE): ', '', line)
            if course_code is None and line.startswith('Activity summary for'):
                header = HEADER_PATTERN.match(line)
                if header:
                    course_code = f"{header['dept']} {header['number']}"
                    course_title = header['title']
                else:
                    course_code = course_title = line.replace('Activity summary for ', '')
                continue

            heading = CATEGORY_PATTERN.match(line)
            if heading:
                category = heading['category']
                category_items = []
                continue

            list_link = LIST_LINK_PATTERN.match(line)
            if list_link:
                for item in category_items:
                    item.list_url = list_link['url']
                continue

            item = ITEM_PATTERN.match(line)
            if not item or course_code is None:
                continue

            due = None
            for candidate in lines[i:i + 3]:
                found = DATE_PATTERN.search(candidate)
                if found:
                    due = found
                    break
            if not due:
                log.warning("No due date found for %r in %s", item['name'], course_code)
                continue

            assignment = Assignment(
                name=item['name'].strip(),
                course_code=course_code,
                course_title=course_title,
                category=category,
                due=self.parse_due(due),
                due_text=due['text'],
                url=item['url'],
                email_date=received.date() if received else None,
            )
            category_items.append(assignment)
            assignments.append(assignment)
        return assignments

    def parse_due(self, match):
        naive = datetime.datetime.strptime(f"{match['date']} {match['time']}", '%B %d, %Y %I:%M %p')
        offset = TZ_OFFSETS.get(match['tz'] or '')
        if offset is None:
            return naive.replace(tzinfo=self.timezone)
        return naive.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=offset)))

    def read_assignments(self, senders, lookback_days):
        """Returns {key: Assignment}; when an assignment shows up in several emails the newest one wins."""
        assignments = {}
        for received, body in self.fetch_summaries(senders, lookback_days):
            for assignment in self.parse_summary(body, received):
                assignments[assignment.key] = assignment
        log.info("Parsed %d unique assignments.", len(assignments))
        return assignments


def html_to_text(page):
    page = re.sub(r'\s+', ' ', page)
    # Keep links in the same "text<url>" shape as the plain-text part; placeholders survive tag stripping
    page = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', '\\2\x00\\1\x01', page, flags=re.I)
    page = re.sub(r'<br\s*/?>|</(div|p|h\d|tr)>', '\n', page, flags=re.I)
    page = re.sub(r'<[^>]+>', '', page)
    return html.unescape(page.replace('\x00', '<').replace('\x01', '>'))


# Run from the repo root: python -m Google.GmailReader
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    reader = GmailReader()
    reader.authenticate()
    for key, assignment in reader.read_assignments(['d2lsupport@purdue.brightspace.com'], 7).items():
        print(key, '->', assignment.due)
