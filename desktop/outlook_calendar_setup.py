#!/usr/bin/env python3
"""One-time Outlook / Microsoft 365 Calendar authorization (device code flow).

Run this once after adding 'outlook_client_id' to ~/.jarvis/config.json - it
prints a short code and a URL (microsoft.com/devicelogin), you enter the
code and sign in there, and a reusable token is cached at
~/.jarvis/outlook_token_cache.bin. Jarvis's read_outlook_calendar tool
refreshes it automatically afterwards; you won't need to run this again
unless you revoke access.

See the README ("Outlook Calendar setup") for how to register the app in
Azure and get a client ID.
"""
import json
from pathlib import Path

import msal

JARVIS_HOME = Path.home() / ".jarvis"
CONFIG_PATH = JARVIS_HOME / "config.json"
CACHE_PATH = JARVIS_HOME / "outlook_token_cache.bin"
SCOPES = ["Calendars.Read"]


def main():
    cfg = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    client_id = cfg.get("outlook_client_id")
    if not client_id:
        print(f"! Set 'outlook_client_id' in {CONFIG_PATH} first.")
        print("  See the README's Outlook Calendar setup section for how to get one.")
        return

    cache = msal.SerializableTokenCache()
    if CACHE_PATH.exists():
        cache.deserialize(CACHE_PATH.read_text())

    app = msal.PublicClientApplication(
        client_id, authority="https://login.microsoftonline.com/common", token_cache=cache)

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        print("! Could not start the sign-in flow:", flow.get("error_description", flow))
        return

    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)  # waits until you finish signing in

    if "access_token" in result:
        CACHE_PATH.write_text(cache.serialize())
        print("Outlook Calendar connected. You can close this window and use Jarvis normally.")
    else:
        print("! Failed:", result.get("error_description", result))


if __name__ == "__main__":
    main()
