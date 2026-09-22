"""
Diagnostic: finds the MySource tab, activates it exactly like
schedule_automation.py does, and immediately lists what's visible --
all in one uninterrupted script run, with no human action in between
that could change window/tab focus and invalidate the test.
"""

import time

from pywinauto import Desktop
import win32con
import win32gui

TITLE_HINT = "MySource"


def force_foreground(win):
    hwnd = win.handle
    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.5)


def activate_element(element):
    for method in ("invoke", "select"):
        try:
            getattr(element, method)()
            return method
        except Exception:
            continue
    element.click_input()
    return "click_input"


windows = Desktop(backend="uia").windows(class_name_re="Chrome_WidgetWin_.*")
target_win = None
target_tab = None
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
        if name.startswith(TITLE_HINT):
            target_win = win
            target_tab = tab
            break
    if target_win:
        break

if not target_win:
    print(f'No tab starting with "{TITLE_HINT}" found.')
    raise SystemExit(1)

print(f"Found tab in window: {target_win.window_text()!r}")
force_foreground(target_win)
method_used = activate_element(target_tab)
print(f"Activated via: {method_used}")
time.sleep(1.0)
print(f"Window title after activation: {target_win.window_text()!r}")

print("\n--- Buttons/TabItems visible now ---")
try:
    descendants = target_win.descendants()
except Exception as e:
    print(f"(couldn't enumerate descendants: {e})")
    raise SystemExit(1)

for ctrl in descendants:
    try:
        ctrl_type = ctrl.element_info.control_type
    except Exception:
        ctrl_type = "?"
    if ctrl_type not in ("Button", "TabItem"):
        continue
    try:
        name = ctrl.window_text()
    except Exception:
        name = "<error reading text>"
    print(f"  {ctrl_type}: {name!r}")
