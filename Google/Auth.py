import os
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

log = logging.getLogger(__name__)


class AuthRequiredError(Exception):
    """Raised when Google needs a browser sign-in but we're running unattended."""


def load_credentials(credentials_path, token_path, scopes, interactive=True):
    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, scopes)
        except Exception as e:
            log.warning("Error loading credentials from %s: %s", token_path, e)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            log.warning("Google token expired or revoked.")
            creds = None

    if not creds or not creds.valid:
        if not interactive:
            raise AuthRequiredError(
                f"Google sign-in needed ({os.path.basename(token_path)}). Run `python Main.py` once by hand.")
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
        creds = flow.run_local_server(port=0)

    with open(token_path, 'w') as token:
        token.write(creds.to_json())
    return creds
