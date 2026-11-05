# The Safwa

The Safwa institutional website presents its philosophy, Institute, Studios, portfolio, journal and ways to contribute.

Run the dependency-free build with:

```sh
python3 scripts/build.py
```

Render publishes `dist/` at https://thesafwa.onrender.com. Approved page bodies live in `content/pages/` and share `content/layout.html`. Page metadata and output routes are declared in `content/pages.json`. The build supplies public canonical metadata, a sitemap, and the existing HTML entry points alongside clean page routes.

The public release follows the reviewed institutional direction. Safwa OS remains a concept within Studios, Acquisition is upcoming, and Safwa Quran is described as a project in development. Editorial sections await reviewed publications.

The enquiry tool prepares an email on the visitor’s device. The visitor reviews and sends it through their email application. The production website serves static pages. Editorial accounts, database migrations and integration with the existing Vercel CMS are a separate review.

The supplied brand images and font licences are retained. See `ART_DIRECTION.md` for the original asset provenance.
