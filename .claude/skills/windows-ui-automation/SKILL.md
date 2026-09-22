---
name: windows-ui-automation
description: Automate a Windows desktop app or website in Edge/Chrome when browser remote-debugging (Playwright/Selenium/Puppeteer) is blocked by IT policy. Use when a corporate-managed machine returns "DevTools remote debugging is disallowed by the system admin," or when browser automation needs to work without CDP. Drives the app through Windows UI Automation (pywinauto) instead.
---

# Windows UI Automation (fallback for locked-down machines)

## When to use this

Playwright, Selenium, and Puppeteer all drive Chromium-based browsers
through the DevTools remote-debugging protocol (CDP). Many corporate IT
policies disable that protocol outright. The symptom is unambiguous:

```
DevTools remote debugging is disallowed by the system admin.
```

Once you see that error, stop trying CDP-based tools — no framework
switch fixes it, since they all depend on the same blocked mechanism.
Windows UI Automation (the accessibility layer screen readers use) is a
separate OS mechanism this policy doesn't touch, and `pywinauto` gives
Python access to it.

## The gotchas, in the order you'll hit them

1. **Chromium only builds a tab's accessibility tree while that tab is the
   active/focused tab in its window.** A background tab is invisible to UI
   Automation even though it's fully loaded — the tab *label* (browser
   chrome) is always visible, but the page *content* isn't. Enumerate
   `TabItem` controls to find the tab you want by its label, before
   assuming the button you need is reachable.

2. **Switching which tab is selected isn't enough — the window needs real
   OS focus too.** A background window can't grant itself foreground focus
   (Windows blocks that for unrelated processes). The reliable workaround
   is minimize-then-restore, which sidesteps the foreground-lock
   restriction:

   ```python
   import win32con, win32gui

   def force_foreground(hwnd):
       win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
       win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
       try:
           win32gui.SetForegroundWindow(hwnd)
       except Exception:
           pass
   ```

   Do this *before* selecting/activating the target tab, not after.

3. **Prefer `invoke()` over `select()` when activating an element.**
   `select()` (SelectionItemPattern) can report success on a tab without
   actually triggering Chromium's real tab-switch behavior. `invoke()`
   (UIA's "DoDefault" action) is what actually maps to the real activation
   handling for both tabs and buttons. Try `invoke()` first, fall back to
   `select()`, and only fall back to a real screen-coordinate click
   (`click_input()`) as a last resort — a screen click can hit the wrong
   window if something else happens to cover that pixel at that instant.

   ```python
   def activate_element(element):
       for method in ("invoke", "select"):
           try:
               getattr(element, method)()
               return
           except Exception:
               continue
       element.click_input()
   ```

4. **Don't use `child_window()` to find a button by name — use
   `descendants()`.** `child_window()` expects a single unique match and
   raises on ambiguity. If the page has more than one element with the
   same visible text (common — e.g. the same button in a nav bar and in
   page content), that exception gets silently swallowed by a broad
   `except Exception` in a polling loop, and the loop retries forever
   without ever finding anything, right up to timeout, with no useful
   error. `descendants()` returns a list, so duplicates are harmless: just
   take the first match.

   ```python
   matches = win.descendants(title="Go to Schedule", control_type="Button")
   if matches:
       activate_element(matches[0])
   ```

5. **Diagnose in one uninterrupted script run, not step-by-step across
   separate commands.** If you check results by running a second command
   and reading its output, switching back to read/paste that output can
   itself change which window/tab has focus — invalidating the very state
   you were trying to verify. Write one script that finds the target,
   activates it, and immediately inspects/acts on the result, with no
   human action in between.

## Minimal working pattern

```python
from pywinauto import Desktop
import win32con, win32gui
import time

def force_foreground(hwnd):
    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass

def activate_element(element):
    for method in ("invoke", "select"):
        try:
            getattr(element, method)()
            return
        except Exception:
            continue
    element.click_input()

def find_tab_window(title_hint):
    for win in Desktop(backend="uia").windows(class_name_re="Chrome_WidgetWin_.*"):
        for tab in win.descendants(control_type="TabItem"):
            if tab.window_text().startswith(title_hint):
                force_foreground(win.handle)
                activate_element(tab)
                time.sleep(0.5)
                return win
    return None

def find_and_click(win, button_name):
    matches = win.descendants(title=button_name, control_type="Button")
    if matches:
        activate_element(matches[0])
        return True
    return False
```

## Reference implementation

A complete, working example — including polling/timeout handling and a
Task Scheduler wrapper — lives in this repo:
[`schedule_automation.py`](../../../schedule_automation.py). Two standalone
diagnostics that helped debug this pattern are also worth reusing on a new
target app: [`debug_list_buttons.py`](../../../debug_list_buttons.py) (list
every visible button/tab) and
[`debug_activate_and_list.py`](../../../debug_activate_and_list.py)
(activate a tab and list what becomes visible, in one uninterrupted run).

## Trade-offs to set expectations on

- Matches elements by visible text, so it's more fragile than driving the
  DOM directly — a wording change in the target app breaks matching.
- If multiple tabs/windows have ambiguous matching labels (e.g. several
  tabs from repeated test runs), the wrong one can get activated. Keep
  test runs clean (close stray duplicate tabs) while developing against a
  new target.
- Needs a real, visible desktop session — this can't run in a headless CI
  environment or "whether or not user is logged on" scheduled task.
