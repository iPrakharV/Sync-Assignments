from __future__ import annotations

import os
import re
import json
import email
import imaplib
import logging
import email.utils
from email.message import Message
from zoneinfo import ZoneInfo

from Google.Auth import AuthRequiredError
from Google.GmailReader import GmailReader, html_to_text

log = logging.getLogger(__name__)

IMAP_HOST = 'imap.gmail.com'
SETUP_HINT = "Run `.venv/bin/python scripts/setup_app_password.py` to set it up."


class ImapGmailReader(GmailReader):
    """Reads Gmail over IMAP with an app password instead of the Gmail API, so there's no Google Cloud
    project and no OAuth token to expire. Parsing is shared with GmailReader."""

    def __init__(self, credentials_file='AppPassword.json', timezone='America/New_York'):
        self.credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), credentials_file)
        self.timezone = ZoneInfo(timezone)
        self.connection = None
        self.mailbox = None

    def authenticate(self, interactive=True):
        if not os.path.exists(self.credentials_path):
            raise AuthRequiredError(f"No Gmail app password set up. {SETUP_HINT}")
        with open(self.credentials_path, 'r') as f:
            credentials = json.load(f)
        self.connection = imaplib.IMAP4_SSL(IMAP_HOST, timeout=60)
        try:
            self.connection.login(credentials['email'], credentials['app_password'].replace(' ', ''))
        except imaplib.IMAP4.error as e:
            raise AuthRequiredError(f"Gmail rejected the app password ({e}). It may have been revoked. {SETUP_HINT}")
        self.mailbox = self.find_all_mail()
        status, _ = self.connection.select(self.mailbox, readonly=True)
        if status != 'OK':
            raise RuntimeError(f"Couldn't open mailbox {self.mailbox}")

    def find_all_mail(self):
        """The "All Mail" folder name depends on your Gmail language, so look it up by its \\All flag."""
        _, folders = self.connection.list()
        for folder in folders or []:
            line = folder.decode('utf-8', 'replace')
            if '\\All' in line:
                return '"' + re.search(r'"([^"]+)"\s*$', line).group(1) + '"'
        return 'INBOX'

    def fetch_summaries(self, senders, lookback_days):
        """Same contract as GmailReader.fetch_summaries: [(received_datetime, body_text)] oldest first."""
        query = f'from:({" OR ".join(senders)}) subject:(Activity summary) newer_than:{lookback_days}d'
        status, data = self.connection.uid('SEARCH', 'X-GM-RAW', imap_quote(query))
        if status != 'OK':
            raise RuntimeError(f"Gmail search failed: {data}")
        uids = data[0].split() if data and data[0] else []
        log.info("Found %d summary emails from the last %d days.", len(uids), lookback_days)

        summaries = []
        for uid in uids:
            status, parts = self.connection.uid('FETCH', uid, '(BODY.PEEK[])')
            raw = next((part[1] for part in parts if isinstance(part, tuple)), None)
            if status != 'OK' or raw is None:
                log.warning("Couldn't fetch message %s", uid)
                continue
            message = email.message_from_bytes(raw)
            received = email.utils.parsedate_to_datetime(message['Date']).astimezone(self.timezone)
            body = message_body(message)
            if body:
                summaries.append((received, body))
            else:
                log.warning("No readable body in message %s", uid)
        summaries.sort(key=lambda summary: summary[0])
        return summaries

    def read_assignments(self, senders, lookback_days):
        try:
            return super().read_assignments(senders, lookback_days)
        finally:
            try:
                self.connection.logout()
            except Exception:
                pass


def imap_quote(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'


def message_body(message: Message):
    def find(mime_type):
        for part in message.walk():
            if part.get_content_type() == mime_type and not part.is_multipart():
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or 'utf-8', 'replace')
        return None

    text = find('text/plain')
    if text:
        return text
    page = find('text/html')
    return html_to_text(page) if page else None
