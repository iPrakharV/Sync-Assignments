"""Saves your Gmail address + app password for Sync Assignments, after checking Gmail accepts them.

Create the app password first at https://myaccount.google.com/apppasswords
(requires 2-Step Verification). Run from the repo root:
    .venv/bin/python scripts/setup_app_password.py
"""
import os
import sys
import json
import getpass
import imaplib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(ROOT, 'Google', 'AppPassword.json')


def main():
    address = input("Gmail address: ").strip()
    password = getpass.getpass("App password (16 letters, typing is hidden): ").replace(' ', '')

    print("Checking with Gmail...")
    try:
        connection = imaplib.IMAP4_SSL('imap.gmail.com', timeout=60)
        connection.login(address, password)
        connection.logout()
    except imaplib.IMAP4.error as e:
        print(f"Gmail rejected that: {e}\nCheck the address, and that you pasted the app password "
              "(not your normal password).")
        return 1
    except OSError as e:
        print(f"Couldn't reach Gmail: {e}")
        return 1

    # Create the file readable only by you before writing the password into it
    fd = os.open(CREDENTIALS_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump({'email': address, 'app_password': password}, f)
    os.chmod(CREDENTIALS_PATH, 0o600)
    print(f"Saved to {CREDENTIALS_PATH}. Sync Assignments will use it from now on.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
