#!/usr/bin/env python3
"""One-time Google Calendar authorization.

Run this once after placing your OAuth client file at
~/.jarvis/google_credentials.json - it opens your browser, you log in and
grant access, and a reusable token is cached at ~/.jarvis/google_token.json.
Jarvis's read_google_calendar tool uses that cached token afterwards and
refreshes it automatically; you never need to run this again unless you
revoke access.

See the README ("Google Calendar setup") for how to get the credentials file.
"""
import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

JARVIS_HOME = Path.home() / ".jarvis"
CREDS_PATH = JARVIS_HOME / "google_credentials.json"
TOKEN_PATH = JARVIS_HOME / "google_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]  # read + create events


def main():
    if not CREDS_PATH.exists():
        print(f"! Missing {CREDS_PATH}")
        print("  Download it from Google Cloud Console (OAuth client, Desktop app type)")
        print("  and save it at that exact path. See the README for the full steps.")
        return

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_info(json.loads(TOKEN_PATH.read_text()), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    print("Google Calendar connected. You can close this window and use Jarvis normally.")


if __name__ == "__main__":
    main()
