# MySource Schedule Automation

Automates the weekly MySource "Confirm Schedule" click in Microsoft Edge:

1. Opens Edge to MySource.
2. Waits for the page to load, then clicks **Go to Schedule**.
3. Waits for the schedule page to load, then clicks **Confirm Schedule**.

Runs locally on your Windows machine via Windows Task Scheduler — it does
not run in any cloud/CI environment, since it needs a real Edge window and
your desktop session's SSO.

## Why UI Automation instead of a browser automation library

The obvious tool for this is something like Playwright/Selenium/Puppeteer,
but those all drive the browser through its DevTools remote-debugging
protocol. Many corporate-managed Windows machines have that protocol
disabled by policy (Edge/Chrome error: *"DevTools remote debugging is
disallowed by the system admin"*) — a deliberate security control, not a
bug, so it isn't something to work around.

Windows UI Automation is a separate, unrelated mechanism — the same
accessibility layer screen readers use to read what's on screen and act on
it — and isn't affected by that policy. `schedule_automation.py` uses the
`pywinauto` library to find Edge's on-screen buttons by their visible text
and click them, the same way an accessibility tool would.

One quirk this has to work around: Chromium only builds the accessibility
tree for whichever tab is currently the *focused/active* tab in its
window — a background tab is invisible to UI Automation even though it's
fully loaded. The tab's label itself is always visible (it's browser
chrome, not page content), so the script finds whichever open tab's label
starts with "MySource" and clicks that tab to activate it before it looks
for "Go to Schedule"/"Confirm Schedule".

Trade-off: this is less precise than driving the DOM directly. It matches
buttons by their visible text, so it's a little more fragile if MySource
changes that text or its tab title.

## Why it navigates to `mysource1.deloitte.com` instead of a raw login link

If you get a URL from MySource redirecting you to sign in
(`login.microsoftonline.com/.../oauth2/authorize?...&state=...&nonce=...`),
that's a one-time OAuth request: the `state`/`nonce` are generated for that
specific login attempt. Reusing that exact link later will likely fail
(invalid/expired request) once that state is gone. Instead, the script
navigates to `https://mysource1.deloitte.com/` and lets the app generate a
fresh sign-in redirect itself, which works every time.

## Prerequisites

- Windows with Microsoft Edge installed.
- Python 3.9+ (check with `python --version`; install via your
  organization's software catalog — e.g. Company Portal or Software
  Center — if missing).
- You are able to sign into MySource in Edge today (either silently via
  Windows Integrated Auth, or with a password/MFA prompt).

## Setup

1. Install the one dependency:

   ```powershell
   cd C:\path\to\MySource-Automation
   python -m pip install -r requirements.txt
   ```

2. Do one interactive test run first, so you can see whether sign-in
   happens silently or needs a manual step:

   ```powershell
   python schedule_automation.py
   ```

   - If it completes and prints `Clicked "Confirm Schedule". Done.`,
     you're ready to schedule it.
   - If Edge stops at a sign-in/MFA prompt, complete that sign-in by hand
     once. As long as your organization's SSO issues a session that
     persists in the browser (cookies, not a one-time code), later
     scheduled runs should reuse that session without prompting. If your
     org requires interactive MFA on every login, this automation can only
     get you to that prompt — it can't complete MFA for you.
   - If it times out without ever seeing a login prompt, MySource's button
     text or layout may not match what this script expects — check the
     Edge window manually and compare against what's in
     `schedule_automation.py`.

3. Create the scheduled task (Task Scheduler):

   ```powershell
   $action = New-ScheduledTaskAction -Execute "C:\path\to\MySource-Automation\run-schedule-automation.bat"
   $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 10:00AM
   $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
   Register-ScheduledTask -TaskName "MySource Schedule Confirmation" `
     -Action $action -Trigger $trigger -Settings $settings
   ```

   Or via the Task Scheduler GUI:
   - **Trigger**: Weekly, every Monday, 10:00 AM.
   - **Action**: Start a program →
     `C:\path\to\MySource-Automation\run-schedule-automation.bat`.
   - **General** tab: run only when you are logged on (a real, visible Edge
     window needs your active desktop session — this can't run "whether or
     not user is logged on").

## Configuration

All optional, set as environment variables (e.g. on the scheduled task
action, or in your shell before an interactive test run):

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYSOURCE_URL` | `https://mysource1.deloitte.com/` | Page to navigate to first. |
| `EDGE_PATH` | auto-detected under `Program Files` / `Program Files (x86)` | Path to `msedge.exe`. |
| `MYSOURCE_TAB_HINT` | `MySource` | Prefix used to find and activate the right open tab by its label. |
| `NAV_TIMEOUT_SECONDS` | `120` | Max wait for each button to appear (covers slow sign-in/MFA). |
| `POLL_INTERVAL_SECONDS` | `2` | How often to re-check for the button while waiting. |

## Logs

Each run writes a timestamped log to `logs/run-<timestamp>.log` (ignored by
git) so you can check what happened without needing to have watched the
screen at 10 AM.

## Troubleshooting

- **Times out waiting for "Go to Schedule"**: the page probably stopped at
  a sign-in prompt, or the button's visible text/wording has changed. Run
  `python schedule_automation.py` interactively to see what's on screen.
- **"Go to Schedule" or "Confirm Schedule" button never appears even after
  signing in**: MySource may have changed its markup, or there's nothing to
  confirm that week (e.g. schedule already confirmed). Check manually.
- **Wrong button gets clicked, or nothing happens on click**: multiple open
  tabs have labels starting with "MySource" (e.g. stale tabs from earlier
  test runs) and the wrong one got activated. Close extra MySource tabs
  before the scheduled run, or narrow `MYSOURCE_TAB_HINT`.
- **Times out finding a tab starting with "MySource"**: run
  `python debug_list_buttons.py` while the page is open to see the actual
  tab labels and button names UI Automation can see, and compare against
  what the script expects.
- **`python` isn't recognized**: install Python via your organization's
  software catalog, then open a new terminal.
