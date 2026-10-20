# 📚 Bookplate (Python port)

A Python port of [Bookplate](https://github.com/LeoPhh/bookplate) — a
self-hosted personal reading tracker with a bold editorial look. Books carry
ratings, reading dates, reading progress and their own notes pages, and can
wear real cover photos; a vocabulary registry keeps the words learned along
the way. Everything can be exported as a zip of plain JSON, markdown and
image files, in the same format as the original, so libraries move freely
between the two.

Built with **FastAPI**, **Jinja2** (server-rendered pages plus three small
scripts), **SQLModel** on SQLite or Postgres, **Alembic**, **uv**, **ruff**
and **pytest-bdd**.

## Features

- **Library**: a covers grid (real photos, or generated cloth covers in one of
  twelve binding colours) and a sortable ledger with a count row; free-text
  search across titles, authors, genres and notes; status filter chips; a
  *Show notes* toggle that drapes a ribbon over books with notes.
- **Books**: title, author, genre, pages, status (read / reading / to read /
  didn't finish), half-star rating, date finished or stopped, ISBN; optional
  source and physical-copy fields switched on in Settings → Preferences.
- **Adding books**: search the Open Library catalogue (no API key) to fill in
  the title, author and pages and fetch the cover, falling back to iTunes
  artwork; or type it all by hand. Uploaded covers are centre-cropped to 2 : 3
  and stored as JPEGs of at most 600 × 900.
- **Notes page per book** (`/books/<id>`): markdown, rendered with raw HTML
  off; images pasted, dropped or picked are uploaded at once (long edge capped
  at 1600 px). Every save deletes images the text no longer uses, Cancel bins
  images pasted meanwhile, and deleting a book removes its notes, images,
  progress and cover.
- **Reading progress**: one update per day, in pages or percent, with pace,
  days left and how long a finished book took.
- **Vocabulary**: words looked up in Wiktionary (proxied), with your own
  definition when the dictionary has none; tagged with a book, searchable,
  sortable and filterable by book.
- **Statistics**: tiles (books read, read this year, pages, average rating),
  books finished per year, ratings, genres, sources and currently reading —
  each bar drills down into its books.
- **Showcase your year**: a public, unlisted page (`/s/<random id>`) of one
  year's reading — covers, titles, authors, ratings and page counts, never
  notes or vocabulary. One link per year, turned off from Settings.
- **Import & export**: the original's zip format, plus Goodreads and
  StoryGraph CSV exports (re-importing updates books in place).
- **Accounts**: the first visit creates the owner's account and then sign-up
  closes, unless `REGISTRATION=open` gives everyone their own library.
  Passwords are hashed with scrypt; sessions last 30 days from the last visit.

## Run it

```bash
uv sync
uv run uvicorn bookplate.main:app --reload     # http://localhost:8000
```

With no configuration it keeps its data in `./bookplate.db` and
`./data/uploads`. Migrations run automatically on start.

### With Docker and Postgres

```bash
cp .env.example .env    # set DB_PASSWORD and PUBLIC_URL
docker compose up -d --build
```

### Configuration

| Variable | Default | |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./bookplate.db` | SQLAlchemy URL; `postgres://…` works too |
| `PUBLIC_URL` | `http://localhost:8000` | the address Bookplate is reached at; `https` marks cookies secure |
| `REGISTRATION` | `closed` | `open` lets anyone create their own separate library |
| `UPLOADS_DIR` | `./data/uploads` (`/data/uploads` in Docker) | where images are stored |
| `LIMIT_BOOKS`, `LIMIT_WORDS` | no limit | the most books / words one account may have |
| `LIMIT_UPLOAD_MB` | `8` | the largest single image |
| `LIMIT_IMPORT_MB` | `1024` | the largest export zip or CSV |
| `CONTACT_EMAIL` | — | sent to Open Library with searches; showcases' *Report this page* writes to it |

A forgotten password is reset on the server with
`uv run bookplate-reset-password you@example.com` (or
`docker compose exec bookplate bookplate-reset-password you@example.com`).

## Development

```bash
uv run pytest                      # BDD scenarios on a throwaway SQLite database
TEST_DATABASE_URL=postgresql+psycopg://user@localhost/db uv run pytest   # …or on Postgres
uv run ruff check . && uv run ruff format .
uv run alembic revision --autogenerate -m "what changed"   # after changing bookplate/models.py
```

The scenarios in `tests/features/*.feature` run the real app, migrations
included, through FastAPI's test client. Outside services are never called
from tests.

## Where things are (and where they came from)

| Python | Original | |
| --- | --- | --- |
| `bookplate/models.py`, `migrations/` | `lib/db/schema.ts`, `drizzle/` | tables; every row belongs to a user |
| `bookplate/library.py` | `lib/library.ts` | user-scoped data access, JSON shapes |
| `bookplate/domain.py` | `lib/types.ts`, `palette.ts`, `ratings.ts`, `progress.ts`, `featureList.ts` | labels, palette, ratings and progress maths |
| `bookplate/auth.py` | `lib/auth.ts` (Better Auth) | accounts, sessions, scrypt |
| `bookplate/storage.py` | `lib/storage/`, the browser-side crop/compress | images on disk |
| `bookplate/outbound.py` | `lib/openLibrary.ts`, `lib/coverLookup.ts`, `app/api/define`, `app/api/booksearch` | Open Library, iTunes, Wiktionary |
| `bookplate/archive.py`, `validate.py` | `lib/archive.ts`, `lib/validate.ts` | zip export / import |
| `bookplate/csv_import.py` | `lib/csvImport.ts`, `lib/csv.ts` | Goodreads / StoryGraph |
| `bookplate/stats.py` | `components/StatsView.tsx` | statistics and drill-downs |
| `bookplate/showcase.py` | `lib/showcase.ts`, `lib/showcaseYear.ts` | public year pages |
| `bookplate/routes/api.py` | `app/api/*` | JSON API |
| `bookplate/routes/pages.py`, `templates/` | `app/*/page.tsx`, `components/` | pages |
| `bookplate/static/style.css` | `app/globals.css` | the look |
| `bookplate/cli.py` | `scripts/reset-password.mjs` | server commands |

### Not ported

Kept out to stay small, as they serve hosting many strangers rather than
tracking reading: email (password reset by mail, address confirmation),
S3 storage, the ALTCHA sign-up puzzle and per-address sign-up limits,
`/api/metrics`, the contact form, newsletter consent, legal pages, profile
photos, info hints and the showcase preview image. The rich-text notes editor
is a markdown textarea with a rendered view; covers are cropped on the server
(centre crop) rather than with an interactive crop dialog.

## License

Apache License 2.0, like the original (see `LICENSE` and `NOTICE`). The name
"Bookplate" and its logo belong to the original project; this is an
unofficial port based on Bookplate.
