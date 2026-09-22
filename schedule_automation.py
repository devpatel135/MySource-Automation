"""
Weekly MySource schedule confirmation.

Drives Edge through Windows UI Automation (the accessibility layer screen
readers use) instead of a browser remote-debugging protocol. That matters
on machines where IT policy disables DevTools remote debugging: tools like
Playwright/Selenium/Puppeteer all rely on that protocol and are blocked by
such a policy, but UI Automation is a separate OS-level mechanism it doesn't
cover.

Opens Edge to MySource, waits for and clicks "Go to Schedule", waits for the
schedule page, then clicks "Confirm Schedule".
"""

import logging
import os
import subprocess
import sys
import time
from datetime import datetime

try:
    from pywinauto import Desktop
except ImportError:
    print(
        "pywinauto is not installed. Run: python -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_path = os.path.join(LOG_DIR, f"run-{datetime.now():%Y%m%d-%H%M%S}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# The app's normal entry point. Letting mysource1.deloitte.com generate its
# own sign-in redirect keeps the OAuth state/nonce fresh on every run,
# unlike a raw copied login link (see README).
URL = os.environ.get("MYSOURCE_URL", "https://mysource1.deloitte.com/")

DEFAULT_EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

NAV_TIMEOUT_SECONDS = int(os.environ.get("NAV_TIMEOUT_SECONDS", "120"))
POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", "2"))


def resolve_edge_path():
    override = os.environ.get("EDGE_PATH")
    if override:
        return override
    for candidate in DEFAULT_EDGE_PATHS:
        if os.path.exists(candidate):
            return candidate
    return "msedge"  # fall back to PATH


def find_and_click(button_name, timeout=NAV_TIMEOUT_SECONDS, poll=POLL_INTERVAL_SECONDS):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            windows = Desktop(backend="uia").windows(class_name_re="Chrome_WidgetWin_.*")
            for win in windows:
                try:
                    btn = win.child_window(title=button_name, control_type="Button")
                    if btn.exists(timeout=0.5):
                        btn.click_input()
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(poll)
    return False


def main():
    edge_path = resolve_edge_path()
    log.info(f"Opening Edge ({edge_path}) at {URL} ...")
    subprocess.Popen([edge_path, "--new-window", URL])

    log.info('Waiting for "Go to Schedule" button...')
    if not find_and_click("Go to Schedule"):
        log.error(
            'Timed out waiting for "Go to Schedule". The page likely stopped at a '
            "sign-in/MFA prompt instead of reaching MySource. Run this script "
            "interactively (python schedule_automation.py) and sign in manually to "
            "confirm; the session should then persist for future runs."
        )
        sys.exit(1)
    log.info('Clicked "Go to Schedule".')

    log.info('Waiting for "Confirm Schedule" button...')
    if not find_and_click("Confirm Schedule"):
        log.error('Timed out waiting for "Confirm Schedule".')
        sys.exit(1)
    log.info('Clicked "Confirm Schedule". Done.')


if __name__ == "__main__":
    main()
