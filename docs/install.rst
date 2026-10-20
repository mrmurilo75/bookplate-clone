Installation
============

Locally
-------

With `uv <https://docs.astral.sh/uv/>`_ and Python 3.12 or later:

.. code-block:: bash

   uv sync
   uv run uvicorn bookplate.main:app --reload     # http://localhost:8000

With no configuration it keeps its data in ``./bookplate.db`` (SQLite) and
``./data/uploads``. Database migrations run automatically when the app starts.
The first visit asks for the owner's account; after that, sign-up is closed.

With Docker and Postgres
------------------------

.. code-block:: bash

   cp .env.example .env    # set DB_PASSWORD and PUBLIC_URL
   docker compose up -d --build

This runs two containers: the app on port 8000 and Postgres 17. Covers and
note images live in the ``uploads`` volume, the database in ``pgdata``.

Configuration
-------------

Everything is set with environment variables (:mod:`bookplate.config`).

.. list-table::
   :header-rows: 1
   :widths: 22 28 50

   * - Variable
     - Default
     - Meaning
   * - ``DATABASE_URL``
     - ``sqlite:///./bookplate.db``
     - SQLAlchemy URL. ``postgres://…`` and ``postgresql://…`` are accepted and use the psycopg 3 driver.
   * - ``PUBLIC_URL``
     - ``http://localhost:8000``
     - The address Bookplate is reached at. With ``https`` the session cookie is marked secure.
   * - ``REGISTRATION``
     - ``closed``
     - ``open`` lets anyone who can reach the server create their own separate library.
   * - ``UPLOADS_DIR``
     - ``./data/uploads`` (``/data/uploads`` in Docker)
     - Where covers and note images are stored.
   * - ``LIMIT_BOOKS``, ``LIMIT_WORDS``
     - no limit
     - The most books / vocabulary words one account may have.
   * - ``LIMIT_UPLOAD_MB``
     - ``8``
     - The largest single image.
   * - ``LIMIT_IMPORT_MB``
     - ``1024``
     - The largest export zip or CSV that can be imported.
   * - ``CONTACT_EMAIL``
     - —
     - Sent to Open Library with searches (they allow busier apps that give a contact more requests);
       showcases' *Report this page* links write to it.

Behind a reverse proxy
----------------------

The app speaks plain HTTP. For HTTPS, put it behind a reverse proxy such as
Caddy and set ``PUBLIC_URL`` to the public ``https://`` address::

   books.example.com {
       reverse_proxy localhost:8000
   }

Forgotten passwords
-------------------

Whoever runs the server resets a password with one command, which asks for the
new password twice and signs out every device:

.. code-block:: bash

   uv run bookplate-reset-password you@example.com
   # or, with Docker:
   docker compose exec bookplate bookplate-reset-password you@example.com

Backups
-------

Each reader can download everything (books, notes, images, covers, progress and
vocabulary) from **Settings → Import & export → Export library**, and import
the same zip into any Bookplate. For a whole server, back up the database and
the uploads folder:

.. code-block:: bash

   docker compose exec postgres pg_dump -U bookplate bookplate > bookplate.sql
   docker compose cp bookplate:/data/uploads ./uploads-backup

Outside services
----------------

The only services Bookplate talks to are Open Library and iTunes (catalogue
search and covers) and Wiktionary (word lookups), and only when those features
are used. All of them are proxied through the app, so the browser never
contacts them. When they can't be reached, the forms say so and everything can
still be entered by hand.
