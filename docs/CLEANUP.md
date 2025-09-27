Project Cleanup Guide

Overview
- This repo currently contains generated artifacts and legacy static bundles. To keep the repository lean and avoid confusion, prefer ignoring and regenerating those artifacts rather than committing them.

Safe-to-regenerate artifacts (do not commit):
- staticfiles/ — created by Django collectstatic
- node_modules/ — installed by npm/yarn
- rms-admin/dist/ — built by Vite (npm run build)
- logs/ — runtime log output
- db.sqlite3 — local dev DB

Legacy/duplicate admin bundles:
- rms/static/admin/ — legacy admin bundle
- frontend/admin_spa/ — legacy static SPA source
- frontend/rms_admin_spa/ — legacy static SPA source

How to audit and clean
- Dry run (report only):
  `python scripts/audit_cleanup.py`
- Delete recommended items (interactive):
  `python scripts/audit_cleanup.py --delete`
- Delete without prompts (dangerous):
  `python scripts/audit_cleanup.py --delete --yes`

Notes
- The Django Admin SPA is served from `rms-admin/dist` when present; otherwise it falls back to `templates/admin_spa/index.html` which pulls assets via staticfiles. Keep one strategy per environment to avoid duplication.
- CI/CD should build the admin SPA (`npm run build` in rms-admin) and run `collectstatic` as part of deployment, rather than committing build outputs.

