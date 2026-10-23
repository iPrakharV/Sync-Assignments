import os
import sys
import time
import socket
import logging
import argparse
import warnings
from logging.handlers import RotatingFileHandler

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

import requests
from google.auth.exceptions import TransportError
from googleapiclient.errors import HttpError

from Config import ROOT, load_config
from Google.Auth import AuthRequiredError
from Google.GmailReader import GmailReader
from Google.GCalendarTasks import GCalendarTasks
from Todoist.TodoistTasks import TodoistTasks
from Summary import notify, notification_text

log = logging.getLogger('sync')

REQUIRED_HOSTS = ('oauth2.googleapis.com', 'gmail.googleapis.com', 'api.todoist.com')
NETWORK_WAIT = 180      # seconds a scheduled run waits for Wi-Fi after the Mac wakes
RUN_RETRY_DELAYS = (60, 300)  # waits before re-running a scheduled sync that hit a temporary error


def setup_logging(verbose):
    log_dir = os.path.join(ROOT, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(os.path.join(log_dir, 'sync.log'), maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter('%(message)s'))
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, handlers=[file_handler, console])
    for noisy in ('googleapiclient', 'urllib3', 'google_auth_oauthlib'):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def network_ready():
    try:
        for host in REQUIRED_HOSTS:
            socket.getaddrinfo(host, 443)
        return True
    except OSError:
        return False


def wait_for_network(timeout):
    deadline = time.monotonic() + timeout
    if network_ready():
        return True
    log.info("No network yet, waiting up to %ds...", timeout)
    while time.monotonic() < deadline:
        time.sleep(5)
        if network_ready():
            log.info("Network is up.")
            return True
    return False


def is_temporary(error):
    """Network drops and server-side hiccups, as opposed to bugs or sign-in problems."""
    if isinstance(error, (requests.ConnectionError, requests.Timeout, TransportError)):
        return True
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return error.response.status_code == 429 or error.response.status_code >= 500
    if isinstance(error, HttpError):
        return error.resp.status == 429 or error.resp.status >= 500
    return False


def should_notify(setting, reports, failed):
    if setting == 'never':
        return False
    if setting == 'errors':
        return failed or any(report.errors for report in reports)
    if setting == 'changes':
        return failed or any(report.changed or report.errors for report in reports)
    return True


def run(args, config):
    reader = GmailReader(timezone=config['timezone'])
    reader.authenticate(interactive=not args.scheduled)
    assignments = reader.read_assignments(config['senders'], args.lookback or config['lookback_days'])

    reports = []
    if config['todoist']['enabled']:
        reports.append(TodoistTasks(config['todoist'], dry_run=args.dry_run).sync_tasks(assignments))
    if config['google_tasks']['enabled']:
        google_tasks = GCalendarTasks(dry_run=args.dry_run)
        google_tasks.authenticate(interactive=not args.scheduled)
        reports.append(google_tasks.sync_tasks(assignments))
    return reports


def main():
    parser = argparse.ArgumentParser(description="Sync Brightspace assignments from Gmail to Todoist.")
    parser.add_argument('--dry-run', action='store_true', help="show what would change without touching anything")
    parser.add_argument('--scheduled', action='store_true',
                        help="unattended run: never open a browser for sign-in, notify instead")
    parser.add_argument('--lookback', type=int, help="days of email to scan (overrides config)")
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    setup_logging(args.verbose)
    config = load_config()
    title = 'Sync Assignments' + (' (dry run)' if args.dry_run else '')
    log.info("=== %s started ===", title)

    if not wait_for_network(NETWORK_WAIT if args.scheduled else 0):
        log.error("No internet connection, skipping this run.")
        if args.scheduled and config['notifications'] != 'never':
            notify(title, "⚠️ Skipped: no internet connection. Will try again at the next scheduled time.")
        return 1

    retry_delays = list(RUN_RETRY_DELAYS) if args.scheduled else []
    try:
        while True:
            try:
                reports = run(args, config)
                break
            except Exception as e:
                if not retry_delays or not is_temporary(e):
                    raise
                delay = retry_delays.pop(0)
                log.warning("Temporary error (%s: %s), retrying in %ds.", type(e).__name__, e, delay)
                time.sleep(delay)
                wait_for_network(NETWORK_WAIT)
    except AuthRequiredError as e:
        log.error(str(e))
        if config['notifications'] != 'never':
            notify(title, f"⚠️ {e}")
        return 1
    except Exception as e:
        log.exception("Sync failed")
        if config['notifications'] != 'never':
            notify(title, f"⚠️ Sync failed: {e}")
        return 1

    for report in reports:
        log.info(report.details())
    if not args.dry_run and should_notify(config['notifications'], reports, failed=False):
        notify(title, notification_text(reports))
    return 1 if any(report.errors for report in reports) else 0


if __name__ == '__main__':
    sys.exit(main())
