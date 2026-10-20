Development
===========

Setup and checks
----------------

.. code-block:: bash

   uv sync                              # the app plus the dev tools
   uv run uvicorn bookplate.main:app --reload
   uv run pytest                        # every scenario, on a throwaway SQLite database
   uv run ruff check . && uv run ruff format .

To run the suite on Postgres, as CI does, point ``TEST_DATABASE_URL`` at an
empty database:

.. code-block:: bash

   TEST_DATABASE_URL=postgresql+psycopg://user@localhost/bookplate_test uv run pytest

Tests
-----

The tests are behaviour scenarios in ``tests/features/*.feature``, with their
steps in ``tests/test_*.py`` and the shared steps and fixtures in
``tests/conftest.py``. Each scenario runs the real app, migrations included,
through FastAPI's test client against a fresh database and uploads folder.
Outside services are never called: scenarios that need them supply answers in
each service's format (``tests/features/outside_services.feature``).

Database changes
----------------

The tables are SQLModel classes in :mod:`bookplate.models`; migrations live in
``migrations/``. After changing a model, write a migration and check that
nothing is left over:

.. code-block:: bash

   uv run alembic revision --autogenerate -m "what changed"
   uv run alembic upgrade head && uv run alembic check

Documentation
-------------

These pages are built with Sphinx from ``docs/``. The code reference comes
from the docstrings, and the HTTP route tables from the app itself, so both
follow the code:

.. code-block:: bash

   uv run --group docs sphinx-build -W docs docs/_build/html

Where things are
----------------

Each module names the part of the original Bookplate it ports, so behaviour can
be traced back to its source.

.. list-table::
   :header-rows: 1
   :widths: 32 40 28

   * - Python
     - Original
     - What it holds
   * - :mod:`bookplate.models`, ``migrations/``
     - ``lib/db/schema.ts``, ``drizzle/``
     - tables; every row belongs to a user
   * - :mod:`bookplate.library`
     - ``lib/library.ts``
     - user-scoped data access, JSON shapes
   * - :mod:`bookplate.domain`
     - ``lib/types.ts``, ``palette.ts``, ``ratings.ts``, ``progress.ts``, ``featureList.ts``
     - labels, palette, ratings and progress maths
   * - :mod:`bookplate.auth`
     - ``lib/auth.ts`` (Better Auth)
     - accounts, sessions, scrypt
   * - :mod:`bookplate.storage`
     - ``lib/storage/``, the browser-side crop and compression
     - images on disk
   * - :mod:`bookplate.outbound`
     - ``lib/openLibrary.ts``, ``lib/coverLookup.ts``, ``app/api/define``, ``app/api/booksearch``
     - Open Library, iTunes, Wiktionary
   * - :mod:`bookplate.archive`, :mod:`bookplate.validate`
     - ``lib/archive.ts``, ``lib/validate.ts``
     - zip export and import
   * - :mod:`bookplate.csv_import`
     - ``lib/csvImport.ts``, ``lib/csv.ts``
     - Goodreads and StoryGraph
   * - :mod:`bookplate.stats`
     - ``components/StatsView.tsx``
     - statistics and drill-downs
   * - :mod:`bookplate.showcase`
     - ``lib/showcase.ts``, ``lib/showcaseYear.ts``
     - public year pages
   * - :mod:`bookplate.search`
     - the search filter in ``app/page.tsx``
     - forgiving free-text search (difflib)
   * - :mod:`bookplate.routes.api`
     - ``app/api/*``
     - JSON API
   * - :mod:`bookplate.routes.pages`, ``bookplate/templates/``
     - ``app/*/page.tsx``, ``components/``
     - pages
   * - ``bookplate/static/style.css``
     - ``app/globals.css``
     - the look
   * - :mod:`bookplate.cli`
     - ``scripts/reset-password.mjs``
     - server commands

Not ported
----------

Left out to stay small, as they serve hosting many strangers rather than
tracking reading: email (password reset by mail, address confirmation), S3
storage, the ALTCHA sign-up puzzle and per-address sign-up limits,
``/api/metrics``, the contact form, newsletter consent, legal pages, profile
photos, info hints and the showcase preview image. The rich-text notes editor
is a markdown textarea with a rendered view, and covers are centre-cropped on
the server rather than in an interactive crop dialog.
