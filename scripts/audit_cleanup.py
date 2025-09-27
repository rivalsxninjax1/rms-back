#!/usr/bin/env python3
"""
Audit the repository for generated/duplicate artifacts and produce a cleanup plan.

Usage:
  python scripts/audit_cleanup.py            # Dry run report
  python scripts/audit_cleanup.py --delete   # Delete recommended items (interactive)
  python scripts/audit_cleanup.py --delete --yes  # Delete without prompts (DANGEROUS)

The script is conservative: it only targets well-known build artifacts and legacy
bundles that are safe to regenerate. It never touches source code.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rg_count(pattern: str, path: str = ROOT) -> int:
    try:
        r = subprocess.run([
            "rg", "-n", pattern, path
        ], capture_output=True, text=True, check=False)
        if r.returncode not in (0, 1):
            return 0
        return len(r.stdout.splitlines())
    except FileNotFoundError:
        return 0


@dataclass
class Target:
    path: str
    reason: str
    keep_if_referenced: bool = True

    def full(self) -> str:
        return os.path.join(ROOT, self.path)


TARGETS: List[Target] = [
    Target("staticfiles", "Django collectstatic output (generated)", True),
    Target("node_modules", "Root Node dependencies (generated)", True),
    Target("rms-admin/node_modules", "Admin Node dependencies (generated)", True),
    Target("rms-admin/dist", "Admin build output (generated)", True),
    Target("rms/static/admin", "Legacy admin static bundle (duplicated)", True),
    Target("frontend/admin_spa", "Legacy SPA static source (duplicated)", True),
    Target("frontend/rms_admin_spa", "Legacy SPA static source (duplicated)", True),
    Target("logs", "Runtime logs (generated)", False),
    Target("db.sqlite3", "Dev database (local artifact)", False),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true", help="Delete recommended items")
    ap.add_argument("--yes", action="store_true", help="Skip confirmation prompts")
    args = ap.parse_args()

    print("Cleanup audit:\n")
    to_delete: List[Target] = []
    for t in TARGETS:
        f = t.full()
        exists = os.path.exists(f)
        refc = rg_count(t.path) if t.keep_if_referenced else 0
        status = "exists" if exists else "missing"
        print(f"- {t.path}: {status}; references: {refc}; reason: {t.reason}")
        if not exists:
            continue
        # conservative: keep generated outputs unless user asks to delete
        if t.keep_if_referenced and refc > 2:
            # likely used by templates/settings; keep
            continue
        to_delete.append(t)

    if not args.delete:
        print("\nDry run only. To delete, run with --delete (and optionally --yes).")
        if to_delete:
            print("\nRecommended deletions:")
            for t in to_delete:
                print(f"  - {t.path}")
        return

    # Delete stage
    for t in to_delete:
        f = t.full()
        if not os.path.exists(f):
            continue
        if not args.yes:
            ans = input(f"Delete {t.path}? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                continue
        if os.path.isdir(f) and not os.path.islink(f):
            shutil.rmtree(f)
            print(f"Deleted directory {t.path}")
        else:
            os.remove(f)
            print(f"Deleted file {t.path}")


if __name__ == "__main__":
    main()

