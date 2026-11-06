# Safwa system implementation

The explicit SQLite CMS instruction selects the implementation described in [SQLITE_CMS.md](SQLITE_CMS.md). That guide replaces the earlier standalone review runbook.

The CMS keeps the approved public page templates and image bytes, adds structured page editing, publishing, staff access, image storage and verified recovery, and supports the version 1 review database through an explicit offline migration. It does not depend on or alter the separate Vercel deployment.

The current public Render release remains static. Activating the CMS requires a persistent Python web service and an approved production cutover. No production data was accessed or changed during implementation.
