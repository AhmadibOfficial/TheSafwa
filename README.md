# The Safwa

The Safwa institutional website presents its philosophy, Institute, Studios, portfolio, journal and ways to contribute.

Run the dependency-free build with:

```sh
python3 scripts/build.py
```

Render publishes `dist/` at https://thesafwa.onrender.com. Approved page bodies live in `content/pages/` and share `content/layout.html`. Page metadata and output routes are declared in `content/pages.json`. The build supplies public canonical metadata, a sitemap, and the existing HTML entry points alongside clean page routes.

The public release follows the reviewed institutional direction. Safwa OS remains a concept within Studios, Acquisition is upcoming, and Safwa Quran is described as a project in development. Editorial sections await reviewed publications.

The enquiry tool prepares an email on the visitor’s device. The visitor reviews and sends it through their email application. The deployed public website currently serves static pages.

## SQLite CMS

The CMS adds page editing, articles, projects, learning activities, opportunities, image uploads, editorial approvals, staff permissions, MFA, revision history, audit, backup/restore and a production WSGI server. It uses the same approved templates and brand assets.

From this repository's root, with Python 3.12 or newer:

```sh
./safwa setup
./safwa create-user yourname --role admin
./safwa local
```

Open `http://127.0.0.1:4173/editor` and leave the terminal running. The account command prompts for a passphrase and prints the authenticator setup once. There are no default accounts.

Read [the CMS operating guide](docs/SQLITE_CMS.md) for the publishing workflow, staff management, recovery, migration and persistent hosting requirements. CMS publishing requires the Python service; the current static deployment has not been switched.

The supplied brand images and font licences are retained. See `ART_DIRECTION.md` for the original asset provenance.
