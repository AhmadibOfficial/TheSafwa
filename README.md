# The Safwa

A five-page presentation website based on the approved Safwa brief and supplied brand imagery.

## Pages

- Home: the parent vision and paths into the different initiatives.
- Institute: exact mission/vision and learning, admissions and community enquiries.
- Studios: the supplied creative identity and Safwa Quran project direction.
- Safwa Quran: a clear introduction to a project in development.
- Connect: a local message-preparation flow for the relevant Safwa Instagram account.

## Build and hosting

Run `python scripts/build.py`. Publish the `dist` directory. No dependency installation, database, runtime secrets or server process is needed. The production target is https://thesafwa.onrender.com. The approved public build includes canonical metadata, social sharing tags and a sitemap. The original Sites preview retains its private audience.

The enquiry form copies a message for the visitor to paste and send through Instagram. It does not send or store information. Admissions, scholarship applications and member accounts are outside this first version.

The Connect page and shared footer include the approved WhatsApp and Telegram invitations. The five enhanced brand images are preserved byte-for-byte from the supplied JPEGs; SVG viewports frame the existing images without recompressing them.

See [ART_DIRECTION.md](ART_DIRECTION.md) for asset provenance, content constraints and the design rationale.
