import os
import sys
import logging
import argparse
import warnings
from logging.handlers import RotatingFileHandler

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

from Config import ROOT, load_config
from Google.Auth import AuthRequiredError
from Google.GmailReader import GmailReader
from Google.GCalendarTasks import GCalendarTasks
from Todoist.TodoistTasks import TodoistTasks
from Summary import notify, notification_text

log = logging.getLogger('sync')


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

    try:
        reports = run(args, config)
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
