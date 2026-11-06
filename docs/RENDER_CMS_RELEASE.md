# Safwa CMS persistent deployment

The CMS implementation was approved and merged through PR #6 at commit `8de7bafec4bebe705396d19653049ce290a81b86`. `render.yaml` prepares a separate Python web service for that code. The existing static service and its live URL remain available throughout provisioning and verification.

## Proposed resources

| Setting | Value |
| --- | --- |
| Compute | One `0.5c-512mb` instance, 0.5 CPU and 512 MB RAM |
| Region | Frankfurt |
| Runtime | Python 3.12.14, hash-locked runtime dependencies, Waitress |
| Disk | 1 GB mounted at `/var/data` |
| Database | `/var/data/safwa/cms.sqlite3` |
| Authenticator encryption key | `/var/data/safwa/cms.key`, created privately on first initialization |
| Health check | `/healthz` |
| Automatic deployment | Off; future releases require an explicit deploy |
| Blueprint auto-sync | Off; infrastructure plans require approval |
| Initial staff credentials | None; an authorized owner enrolls through Render's private terminal |

The currently listed base cost is **US $7.25 per month**: $7 for the service and $0.25 for 1 GB of disk. Taxes, usage overages and changes to the workspace subscription are outside this base estimate. No new workspace subscription is requested.

The Blueprint plan is prepared with `existingResources: create_new`, so it creates a separate service and does not adopt, modify or delete existing services. Render can add a suffix to the service name. The start command uses Render's documented `RENDER_EXTERNAL_URL` as the exact public origin instead of guessing the assigned hostname.

## Startup and data protection

Initialization runs in the service's start command, when the disk is mounted. It imports approved page text only on a fresh database. Subsequent starts verify the current schema; they do not migrate or overwrite an existing database. The database, WAL files and encryption key all remain beneath the disk mount. Startup refuses an incompatible schema. The application process replaces the shell with `exec` so Render can signal it directly.

No administrator, passphrase, authenticator setup key or recovery code is placed in Git, environment variables or deployment logs. Once the service is live, the owner creates the first administrator in the Render service's Shell using:

```sh
python3 scripts/cms.py create-user yourname --role admin
```

The private terminal prompts for the passphrase and displays the authenticator enrollment URI once. The owner imports it into an authenticator and signs in at the service's `/editor` address. Credentials must not be pasted into chat. The owner then provisions the individual editorial roles through Staff.

## Verification before public cutover

Confirm the specific deploy is live, `/healthz` returns success, all nine public pages load, staff sign-in uses HTTPS Secure/HttpOnly/SameSite cookies, and database/key paths are on the persistent disk. In private staging, rehearse a publish and a SQLite backup/restore, then restart and confirm persistence. The implementation's 25 automated checks already exercise workflow, scope, media privacy, migration/recovery and the production WSGI launcher using synthetic data.

Keep the current static website as the fallback until the CMS service is healthy. An onrender.com hostname belongs to its service; this configuration does not attempt to transfer or delete the existing static service to reclaim its hostname. Public routing is changed only after the replacement is verified. An operational rollback returns visitors to the retained static release while the persistent service and its data are retained for diagnosis.

Database backups use the SQLite backup command described in `SQLITE_CMS.md`; disk snapshots are not a substitute for a consistent database backup. Preserve a separately protected copy of the matching `cms.key`. Persistent-disk services run as one instance and can have a short interruption during subsequent deploys.

## References checked on 6 November 2026

- [Render pricing](https://render.com/pricing)
- [Persistent disks](https://render.com/docs/disks)
- [Blueprint specification](https://render.com/docs/blueprint-spec)
- [Default environment variables](https://render.com/docs/environment-variables)
- [Python version selection](https://render.com/docs/python-version)
- [Health checks](https://render.com/docs/health-checks)
