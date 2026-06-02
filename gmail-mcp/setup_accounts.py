#!/usr/bin/env python3
"""
Authenticate additional Gmail accounts and save tokens to tokens/.

Run this script once per new account:
    python setup_accounts.py

It will process every credential JSON file found in the current directory
(files with an "installed" key — the format downloaded from Google Cloud Console).
A browser window opens for each one; sign in with the matching Google account.
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

TOKENS_DIR = Path(__file__).parent / "tokens"
CREDS_DIR  = Path(__file__).parent / "creds"
TOKENS_DIR.mkdir(exist_ok=True)
CREDS_DIR.mkdir(exist_ok=True)

HERE = Path(__file__).parent

# Find credential files in the directory (have "installed" or "web" key)
cred_files = sorted(
    f for f in HERE.glob("*.json")
    if f.name not in ("creds.json",)
    and not f.stem.startswith("token")
    and json.loads(f.read_text()).get("installed") or json.loads(f.read_text()).get("web")
)

if not cred_files:
    print("No credential files found. Place your downloaded credential JSON files")
    print("in the gmail-mcp directory, then re-run this script.")
    sys.exit(0)

print(f"Found {len(cred_files)} credential file(s) to process.\n")

for cred_file in cred_files:
    print(f"--- {cred_file.name} ---")
    print("A browser window will open. Sign in with the corresponding Google account.")

    try:
        flow  = InstalledAppFlow.from_client_secrets_file(str(cred_file), SCOPES)
        creds = flow.run_local_server(port=0)

        svc   = build("gmail", "v1", credentials=creds)
        email = svc.users().getProfile(userId="me").execute().get("emailAddress", "unknown")

        token_path = TOKENS_DIR / f"{email}.json"
        token_path.write_text(creds.to_json())
        print(f"Token saved for: {email}")

        # Move credential file to creds/ to keep root tidy
        dest = CREDS_DIR / f"{email}.json"
        cred_file.rename(dest)
        print(f"Credential file moved to creds/{email}.json\n")

    except Exception as e:
        print(f"Error processing {cred_file.name}: {e}\n")

print("Done! Restart the dashboard (python dashboard.py) to see all accounts.")
