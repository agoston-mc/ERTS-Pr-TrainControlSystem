#!/usr/bin/env python3
"""
Toggle the 'Local' workspace member in/out of the root pyproject.toml.

Usage:
    python scripts/toggle_local.py          # toggle (flip current state)
    python scripts/toggle_local.py enable   # include Local in workspace
    python scripts/toggle_local.py disable  # exclude Local from workspace
    python scripts/toggle_local.py status   # show current state
"""

import sys
import re
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"

ACTIVE_LINE   = '    "Local",'
INACTIVE_LINE = '#    "Local",'


def read():
    return PYPROJECT.read_text()


def write(text):
    PYPROJECT.write_text(text)


def is_active(text):
    # Must match an uncommented line — check line by line
    return any(
        line == ACTIVE_LINE for line in text.splitlines()
    )


def is_inactive(text):
    return any(
        line.rstrip() == INACTIVE_LINE for line in text.splitlines()
    )


def enable(text):
    """Uncomment 'Local' in the members list."""
    if is_active(text):
        print("Local is already included.")
        return text
    if is_inactive(text):
        return text.replace(INACTIVE_LINE, ACTIVE_LINE, 1)
    # Not present at all — insert it into the members list
    return re.sub(
        r'(members\s*=\s*\[)',
        r'\1\n' + ACTIVE_LINE,
        text,
        count=1,
    )


def disable(text):
    """Comment out 'Local' in the members list."""
    if is_inactive(text):
        print("Local is already excluded.")
        return text
    if is_active(text):
        return text.replace(ACTIVE_LINE, INACTIVE_LINE, 1)
    print("'Local' entry not found in members list — nothing to disable.")
    return text


def status(text):
    if is_active(text):
        print("Local is currently INCLUDED in the workspace (Pi mode).")
    elif is_inactive(text):
        print("Local is currently EXCLUDED from the workspace (macOS mode).")
    else:
        print("Local entry not found in the members list.")


def main():
    text = read()
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "toggle"

    if cmd == "status":
        status(text)
        return

    if cmd == "toggle":
        cmd = "disable" if is_active(text) else "enable"

    if cmd == "enable":
        new_text = enable(text)
        action = "Enabled"
    elif cmd == "disable":
        new_text = disable(text)
        action = "Disabled"
    else:
        print(__doc__)
        sys.exit(1)

    if new_text != text:
        write(new_text)
        print(f"{action} Local workspace member in {PYPROJECT}")
        print("Run `uv lock` to update the lockfile.")


if __name__ == "__main__":
    main()

