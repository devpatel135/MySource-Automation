"""
Diagnostic: lists every Button-like control pywinauto can see in any open
Edge window right now. Run this while the page with "Go to Schedule" is
visible in Edge, to see exactly how its accessible name/type differ from
what schedule_automation.py expects to match.
"""

from pywinauto import Desktop

windows = Desktop(backend="uia").windows(class_name_re="Chrome_WidgetWin_.*")
print(f"Found {len(windows)} Edge window(s).\n")

for win in windows:
    try:
        title = win.window_text()
    except Exception:
        title = "<unknown>"
    print(f"=== Window: {title!r} ===")
    try:
        descendants = win.descendants()
    except Exception as e:
        print(f"  (couldn't enumerate descendants: {e})")
        continue

    for ctrl in descendants:
        try:
            ctrl_type = ctrl.element_info.control_type
        except Exception:
            ctrl_type = "?"
        if ctrl_type not in ("Button", "MenuItem"):
            continue
        try:
            name = ctrl.window_text()
        except Exception:
            name = "<error reading text>"
        print(f"  control_type={ctrl_type!r} name={name!r}")
    print()
