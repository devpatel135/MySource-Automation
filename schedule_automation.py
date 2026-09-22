"""
Weekly MySource schedule confirmation.

Drives Edge through Windows UI Automation (the accessibility layer screen
readers use) instead of a browser remote-debugging protocol. That matters
on machines where IT policy disables DevTools remote debugging: tools like
Playwright/Selenium/Puppeteer all rely on that protocol and are blocked by
such a policy, but UI Automation is a separate OS-level mechanism it doesn't
cover.

Chromium only builds its accessibility tree for a tab while that tab is
the focused/active one in its window -- background tabs stay invisible to
UI Automation entirely, even though the tab label itself (browser chrome,
not page content) is always visible. So this script: opens MySource, finds
whichever open tab's label starts with "MySource" and clicks it to make it
the active tab, then waits for and clicks "Go to Schedule" followed by
"Confirm Schedule" within that same window.
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

try:
    import win32con
    import win32gui
except ImportError:
    print(
        "pywin32 is not installed. Run: python -m pip install -r requirements.txt",
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

TAB_TITLE_HINT = os.environ.get("MYSOURCE_TAB_HINT", "MySource")
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


def force_foreground(win):
    """Bring a background window to genuine OS focus. Windows deliberately
    blocks unrelated processes from stealing foreground focus outright, but
    minimizing then restoring a window is a well-known way around that
    restriction. Chromium ties full accessibility-tree population to real
    window focus, not just which tab Chrome considers internally selected,
    so this matters even after the tab itself has been switched."""
    hwnd = win.handle
    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.5)


def activate_element(element):
    """Trigger a UIA element via its native pattern (Invoke/Select) rather
    than a real screen-coordinate click. A screen click can land on the
    wrong window if something else happens to be covering that pixel at
    that instant; invoking the pattern directly sidesteps that entirely.

    Invoke (UIA's "DoDefault" action) is tried first: it's what actually
    triggers Chromium's real activation behavior for both buttons and tabs.
    Select can report success on a tab without truly switching to it, so
    it's only a fallback, not the primary method."""
    for method in ("invoke", "select"):
        try:
            getattr(element, method)()
            return
        except Exception:
            continue
    element.click_input()


def find_and_activate_tab(title_hint, timeout, poll):
    """Find any open Edge tab whose label starts with title_hint, activate
    it, and return its window."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            windows = Desktop(backend="uia").windows(class_name_re="Chrome_WidgetWin_.*")
            for win in windows:
                try:
                    tabs = win.descendants(control_type="TabItem")
                except Exception:
                    continue
                for tab in tabs:
                    try:
                        name = tab.window_text()
                    except Exception:
                        continue
                    if name.startswith(title_hint):
                        force_foreground(win)
                        activate_element(tab)
                        time.sleep(0.5)
                        if win.window_text().startswith(title_hint):
                            return win
        except Exception:
            pass
        time.sleep(poll)
    return None


def find_and_click(win, button_name, timeout, poll):
    """Find a button by name within a specific window and activate it.

    Uses descendants() rather than child_window(): the latter expects a
    single unique match and raises on ambiguity, which silently broke this
    when a page has more than one button with the same visible text (e.g.
    MySource's "Go to Schedule" appears twice)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            matches = win.descendants(title=button_name, control_type="Button")
            if matches:
                activate_element(matches[0])
                return True
        except Exception:
            pass
        time.sleep(poll)
    return False


def main():
    edge_path = resolve_edge_path()
    log.info(f"Opening Edge ({edge_path}) at {URL} ...")
    subprocess.Popen([edge_path, URL])

    log.info(f'Waiting for a tab starting with "{TAB_TITLE_HINT}" and activating it...')
    win = find_and_activate_tab(TAB_TITLE_HINT, NAV_TIMEOUT_SECONDS, POLL_INTERVAL_SECONDS)
    if win is None:
        log.error(
            f'Timed out finding a tab starting with "{TAB_TITLE_HINT}". Run '
            "debug_list_buttons.py to see what tabs/buttons are actually visible."
        )
        sys.exit(1)
    log.info(f"Activated tab: {win.window_text()!r}")

    log.info('Waiting for "Go to Schedule" button...')
    if not find_and_click(win, "Go to Schedule", NAV_TIMEOUT_SECONDS, POLL_INTERVAL_SECONDS):
        log.error(
            'Timed out waiting for "Go to Schedule". The page likely stopped at a '
            "sign-in/MFA prompt instead of reaching MySource. Run this script "
            "interactively (python schedule_automation.py) and sign in manually to "
            "confirm; the session should then persist for future runs."
        )
        sys.exit(1)
    log.info('Clicked "Go to Schedule".')

    log.info('Waiting for "Confirm Schedule" button...')
    if not find_and_click(win, "Confirm Schedule", NAV_TIMEOUT_SECONDS, POLL_INTERVAL_SECONDS):
        log.error('Timed out waiting for "Confirm Schedule".')
        sys.exit(1)
    log.info('Clicked "Confirm Schedule". Done.')


if __name__ == "__main__":
    main()
