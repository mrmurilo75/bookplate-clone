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

On a server
-----------

To run Bookplate for everyday use, with Docker Compose and Postgres or as a
systemd service, behind HTTPS and with backups, follow the
:doc:`deployment`.

.. _configuration:

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

Outside services
----------------

The only services Bookplate talks to are Open Library and iTunes (catalogue
search and covers) and Wiktionary (word lookups), and only when those features
are used. All of them are proxied through the app, so the browser never
contacts them. When they can't be reached, the forms say so and everything can
still be entered by hand.
