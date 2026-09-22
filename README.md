# MySource Schedule Automation

Automates the weekly MySource "Confirm Schedule" click in Microsoft Edge:

1. Opens Edge (using your real Edge profile, so your existing Windows/SSO
   session applies).
2. Navigates to MySource.
3. Waits for the page to load, then clicks **Go to Schedule**.
4. Waits for the schedule page to load, then clicks **Confirm Schedule**.

Runs locally on your Windows machine via Windows Task Scheduler — it does
not run in any cloud/CI environment, since it needs a real Edge window and
your desktop session's SSO.

## Why it navigates to `mysource1.deloitte.com` instead of the raw login link

The URL you get when MySource redirects you to sign in
(`login.microsoftonline.com/.../oauth2/authorize?...&state=...&nonce=...`)
is a one-time OAuth request: the `state`/`nonce` are generated for that
specific login attempt and validated against server-side state from that
attempt. Reusing the exact same link on a later Monday will likely fail
(invalid/expired request) once that state is gone. Instead,
`schedule-automation.js` navigates to `https://mysource1.deloitte.com/`
and lets the app generate a fresh authorize redirect itself, which works
every time. If you still want to force a specific URL, you can override it
(see Configuration below), but the default is what you should use for a
recurring schedule.

## Prerequisites

- Windows with Microsoft Edge installed.
- [Node.js](https://nodejs.org/) 18 or later.
- You are able to sign into MySource in Edge today (either silently via
  Windows Integrated Auth, or with a password/MFA prompt).

## Setup

1. Install dependencies:

   ```powershell
   cd C:\path\to\MySource-Automation
   npm install
   ```

   (`channel: 'msedge'` in the script uses your already-installed system
   Edge — Playwright does not need to download a browser.)

2. Do one interactive test run first, so you can see whether sign-in
   happens silently or needs a manual step:

   ```powershell
   node schedule-automation.js
   ```

   - If it completes and prints `Clicked "Confirm Schedule". Done.`,
     you're ready to schedule it.
   - If Edge stops at a sign-in/MFA prompt, complete that sign-in by hand
     once. As long as your organization's SSO issues a session that
     persists in the browser profile (cookies, not a one-time code), later
     scheduled runs should reuse that session without prompting. If your
     org requires interactive MFA on every login, this automation can only
     get you to that prompt — it can't complete MFA for you.

3. Create the scheduled task (Task Scheduler):

   ```powershell
   $action = New-ScheduledTaskAction -Execute "powershell.exe" `
     -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\path\to\MySource-Automation\run-schedule-automation.ps1"'
   $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 10:00AM
   $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
   Register-ScheduledTask -TaskName "MySource Schedule Confirmation" `
     -Action $action -Trigger $trigger -Settings $settings
   ```

   Or via the Task Scheduler GUI:
   - **Trigger**: Weekly, every Monday, 10:00 AM.
   - **Action**: Start a program → `powershell.exe`, arguments:
     `-NoProfile -ExecutionPolicy Bypass -File "C:\path\to\MySource-Automation\run-schedule-automation.ps1"`.
   - **General** tab: run only when you are logged on (a real Edge window
     needs your active desktop session — this can't run "whether or not
     user is logged on").

## Important: closing Edge before each run

`run-schedule-automation.ps1` closes any currently-running Edge windows
before launching the automation. This is required — Edge refuses to open a
second instance against a profile that's already in use — but it means
**any unsaved work in other open Edge tabs/windows will be closed** when
the 10 AM task fires. If that's not acceptable, set the environment
variable `CLOSE_EXISTING_EDGE=false` on the scheduled task (Task Scheduler
→ task → Actions → add `/setenv` via a wrapper, or set it in the action's
`Argument` via `$env:CLOSE_EXISTING_EDGE='false'; ...`), and the run will
instead fail with a clear error if Edge is already open, rather than
closing it for you.

## Configuration

All optional, set as environment variables (e.g. on the scheduled task
action, or in your shell before an interactive test run):

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYSOURCE_URL` | `https://mysource1.deloitte.com/` | Page to navigate to first. |
| `EDGE_USER_DATA_DIR` | `%LOCALAPPDATA%\Microsoft\Edge\User Data` | Edge profile root directory. |
| `EDGE_PROFILE_DIRECTORY` | `Default` | Which profile inside that directory to use (check `edge://version` → "Profile path" if you use a non-default profile). |
| `NAV_TIMEOUT_MS` | `60000` | Max wait for page navigations. |
| `CLICK_TIMEOUT_MS` | `90000` | Max wait for each button to appear (covers slow sign-in). |
| `CLOSE_EXISTING_EDGE` | `true` | Set to `false` to fail instead of closing open Edge windows. |

## Logs

Each run writes a timestamped log to `logs/run-<timestamp>.log` (ignored by
git) so you can check what happened without needing to have watched the
screen at 10 AM.

## Troubleshooting

- **Times out waiting for "Go to Schedule"**: the page probably stopped at
  a sign-in prompt. Run `node schedule-automation.js` interactively to see
  what's on screen.
- **"Go to Schedule" or "Confirm Schedule" button never appears even after
  signing in**: MySource may have changed the page markup, or there's
  nothing to confirm that week (e.g. schedule already confirmed). Check the
  log and the last screenshot state manually.
- **Edge fails to launch / "profile in use"**: another Edge process is
  still holding the profile. `run-schedule-automation.ps1` should have
  closed it; if it's still failing, close Edge manually and re-run.
