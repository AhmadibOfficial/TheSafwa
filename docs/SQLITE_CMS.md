# The Safwa SQLite CMS

This CMS serves the approved institutional website and the staff workspace from one Python application. SQLite contains published page text, private revisions, staff accounts, audit events and uploaded images. The original brand assets, templates, fonts and approved visitor journeys remain in source control.

## Start locally

Use Python 3.12 or newer with the `venv` module. From this repository's root:

```sh
./safwa setup
./safwa create-user yourname --role admin
./safwa local
```

Keep the terminal running. Open `http://127.0.0.1:4173/editor`. The account command prompts for a passphrase and prints an authenticator enrollment URI once. Import it into your authenticator before closing the terminal. Passphrases never belong in command arguments or source files.

The default data directory is `private/`, outside the public asset allowlist. The database is `private/review.sqlite3`; the separate encryption key is `private/cms.key`. New data files are private to the owner. There are no default staff credentials.

The earlier command `python3 scripts/serve_review.py serve` remains available after installing dependencies. Prefer `./safwa local`, which selects the correct interpreter and starts from the correct directory.

## Publishing

| Role | Authority |
| --- | --- |
| Editor | Create content, edit assigned pages, upload images, save private revisions, restore an old revision as a new draft and submit for review |
| Reviewer | Inspect the exact working revision; approve it or return it with a reason |
| Publisher | Publish an approved revision, return it to draft, or withdraw an existing publication with a reason |
| Administrator | Provision and disable staff, change roles and institutional areas, inspect every record and read the system audit |

Editors, reviewers and publishers each belong to one institutional area: parent, Institute or Studios. An administrator has global access but cannot bypass editorial decisions. An author cannot approve their own revision after a role change. Every write uses a transaction and records its audit event together with the change. A stale form receives a conflict response and cannot overwrite newer work.

An editor saves a draft and sends it for review. A reviewer approves the working revision. A publisher releases that approved revision. The current public revision remains available throughout subsequent editing and review. A publisher may withdraw a publication while another revision is pending; both histories remain stored. Fixed website pages cannot be archived accidentally.

The workspace supports content-type and state filters, title/URL search and pagination. Each record includes a private preview in the actual website layout, revision history and decision history. Saving invalid content preserves the entered values. Restoring a revision creates a draft and requires the same review workflow.

## Pages and content

The nine approved pages are imported as the public baseline: Home, About, Institute, Studios, Safwa Quran, Portfolio, From Safwa, Build With Us and Contact. The original page bodies render unchanged on initialization.

Website-page editing covers headings, paragraphs, image captions, Institute mission and vision, page titles and search descriptions. Template navigation, link destinations, branding, structural markup and the visitor enquiry tool remain in source control. This keeps text editing separate from executable HTML. All entered text is escaped when rendered.

Articles, projects, learning activities and opportunities can use a publication image and plain-text paragraphs. Journal and opportunity collections begin empty. Initial institutional activity/project records are private drafts; there are no invented public achievements or openings. Approved publications appear in the relevant public collection and in the sitemap. Legacy HTML entry points redirect to their clean routes. `/work` redirects to `/portfolio`.

Safwa Quran remains an in-development project. The public enquiry tool prepares an email for a visitor to send; it does not transmit or retain enquiries. Admissions, scholarship applications, student records, payments and community member accounts are separate systems and are not claimed as CMS features.

## Images

Editors upload JPEG or PNG files through Images. Each file needs a text description for accessibility. Uploads are limited to 4 MB, 12 million pixels and a single still frame. Valid files are decoded, resized to at most 2,000 pixels on either side, re-encoded and stripped of source metadata. SVG, scripts, animation and malformed image data are rejected.

Images belong to the editor's institutional area. Selecting an image from another area is rejected on the server. Staff previews require authentication and the same area permission. The public image route works only while an exact published revision references that image. Withdrawing the final publication also removes anonymous access to the image. Image records are immutable so changes cannot silently alter previously reviewed material. Identical image data, description and area are deduplicated. The library has a 500 MB total upload limit.

Image bytes are stored in SQLite, making image/content backups transactionally consistent. The pre-approved brand images remain unchanged in `dist/assets/` and are included in source releases.

## Staff security

Passphrases use PBKDF2-HMAC-SHA256 with individual random salts and 600,000 iterations. TOTP authenticator codes follow RFC 6238; accepted counters cannot be replayed. Authenticator seeds use authenticated Fernet encryption with a separate key. Eight optional recovery codes are stored only as hashes; each works once with the account passphrase.

Administrators create individual accounts in Staff. A setup key is shown once and must be transferred privately to the account holder. The temporary passphrase must be changed before that account can access content. The account holder can generate recovery codes after changing it. Changing a passphrase ends all that account's sessions. Role, area or access changes also end the affected sessions immediately. Administrators cannot change their own permissions through Staff; another administrator must do so. The final active administrator cannot be disabled by the local command.

For an account holder who has lost both authenticator and recovery codes, an authorized local operator can reset access interactively:

```sh
./safwa reset-access staffname
```

This replaces the passphrase and authenticator seed, removes recovery codes, ends sessions, requires a passphrase change, and records an audit event. It does not reactivate an account that was disabled. Disabling an account from a private terminal is also supported:

```sh
./safwa revoke-user staffname
```

Session tokens are random; only their hashes are stored. Sessions expire after four hours. Cookies are HttpOnly and SameSite=Strict, and production HTTPS cookies are Secure. Staff forms require session-specific CSRF tokens and an allowed origin. Login attempts are throttled per account and globally over ten minutes. Content and SQL parameters are validated; the server serves only approved assets and explicit routes. Staff responses cannot be cached or indexed, and neither request forms nor credentials are written to access logs.

## Backup, restore and recovery

```sh
./safwa backup private/backup-2026-11-06.sqlite3
./safwa --database private/restored.sqlite3 restore private/backup-2026-11-06.sqlite3
./safwa --database private/restored.sqlite3 check
./safwa --database private/restored.sqlite3 local --port 4180
```

Backups use SQLite's online backup API, followed by integrity and foreign-key checks. Existing sessions and login attempts are removed from both backup and restore copies. Restoration writes a new destination and refuses to overwrite any file. The restore is audited.

**Back up `cms.key` separately in protected storage.** A database backup deliberately does not contain the encryption key. A restore in another directory needs the matching `cms.key` beside it, with mode 600. Without that key, authenticator seeds cannot be recovered. Keep database backups private too: they contain staff hashes, unpublished text and media. The tool verifies the database but does not encrypt the entire backup file. Use encrypted backup storage under the institution's control.

Rehearse restoration into a separate private directory. Verify public content, one private revision, images, permissions, the audit trail and a staff sign-in before relying on a backup. Set and operate the backup schedule outside the application; this repository does not claim an active managed backup service.

## Upgrade from the earlier review database

Stop the old server first. Preserve its existing source release, then run:

```sh
./safwa --database private/review.sqlite3 migrate --backup private/before-v2.sqlite3
./safwa --database private/review.sqlite3 check
```

Migration supports the Safwa schema version 1 only. It first preserves a verified original-schema backup, then uses a single transaction to retain users, content and revision/audit history, add image/recovery/page support, encrypt authenticator seeds and import the approved page baseline. It removes sessions. Startup never runs schema migrations automatically. Do not migrate while any process is using the database. The version 1 backup contains the earlier plaintext authenticator seeds and must be protected accordingly.

For rollback, stop the version 2 service and retain its database and key. Restore the pre-upgrade version 1 backup into a new file and run the matching old source release. Reconcile any content created after cutover separately; restoring an older snapshot does not preserve later edits automatically. The current public static release remains available until a reviewed CMS deployment is activated.

## Production runtime

The production entry point uses Waitress, not the loopback development server:

```sh
./safwa --database /var/data/safwa/cms.sqlite3 serve --host 0.0.0.0 --port 10000 --origin https://thesafwa.onrender.com
```

Initialize that private database and provision staff through an authorized private terminal before starting the service. `SAFWA_DATABASE`, `SAFWA_ORIGIN` and `PORT` can supply deployment-specific paths/origin/port. The origin must be HTTPS unless it is localhost. The application validates the exact Host and Origin and does not trust arbitrary forwarded headers. Canonical metadata uses that configured public origin. The TLS proxy must preserve the public Host header.

On Render this requires a **web service with a persistent local disk**, not the existing static site. Store the SQLite database, WAL files and `cms.key` together on that disk, outside `dist`. Use one service instance and local storage; do not share SQLite over a network filesystem or run independent instances against separate copies. Configure `/healthz` as the health check. The build command is `python3 -m pip install --require-hashes --only-binary=:all: -r requirements.lock && python3 scripts/build.py`. Use the command above as the start command with the actual mount path.

The repository's static `dist/` remains a separate, dependency-free public build. CMS publishing updates the running Python site's database, not the already-deployed static CDN. A production cutover needs persistent hosting, backup ownership, first staff enrollment, staging/recovery checks and the institution's release approval. No production database was accessed or deployment changed during this implementation.

## Verification and dependencies

```sh
.venv/bin/python -m unittest discover -s tests -v
python3 scripts/ai_security_preflight.py --tracked
python3 scripts/build.py
```

Runtime dependencies are pinned by version and PyPI release SHA-256 hashes in `requirements.lock`, with binary wheels required and no optional extras. Waitress (Pylons, ZPL-2.1) handles WSGI, Pillow (python-pillow, MIT-CMU) validates images, and cryptography (PyCA, Apache-2.0 OR BSD-3-Clause) handles Fernet. Its reviewed transitive dependencies are cffi (python-cffi, MIT-0) and pycparser (eliben, BSD-3-Clause). Release provenance and runtime dependency metadata were checked against PyPI on 6 November 2026. No new frontend packages are required.

Tests exercise the real HTTP boundary, exact initial page bodies, page approval/restore, publication isolation, cross-area permissions, malformed uploads, image privacy and metadata stripping, concurrent-write conflicts, staff provisioning and session revocation, recovery-code use, encrypted seeds, configured HTTPS cookies/origins and v1 migration with a recoverable backup. Browser QA checks the public site, staff sign-in and a staff-view projection with synthetic records; authenticated actions are covered by HTTP tests.
