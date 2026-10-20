HTTP API
========

The pages are plain HTML forms, but everything they do is also available as a
JSON API under ``/api``, shaped like the original Bookplate's.

Authentication and errors
-------------------------

The API uses the same session cookie as the pages: sign in with
``POST /login`` (form fields ``email`` and ``password``) and send the cookie it
sets. Every ``/api`` route except ``/api/health`` answers ``401`` without one.

Errors come back with an HTTP status and a JSON body ``{"error": "…"}``:
``400`` for invalid input, ``403`` at an account limit, ``404`` for something
that doesn't exist, ``413`` for an upload that is too large, ``415`` for an
image that can't be read and ``502`` when an outside service can't be reached.

Every response carries an ``X-Request-Id`` header (kept from a reverse proxy
that sets one), which also appears in the server's JSON log line for the
request.

Records
-------

Books, words and progress travel as JSON objects with camelCase keys, the same
as in an export. Keys without a value are left out.

Book
   ``id`` (letters, digits, ``_`` and ``-``; chosen by the client), ``title``,
   ``author``, ``isbn``, ``olWorkId`` (an Open Library work, e.g.
   ``OL893415W``), ``genre``, ``pages``, ``format`` (the source: ``bookstore``,
   ``kindle``, ``audiobook``, ``borrowed``, ``secondhand``, ``gifted``,
   ``library`` or the reader's own text), ``status`` (``read``, ``reading``,
   ``to-read`` or ``dnf``), ``copy`` (a physical copy at home), ``rating`` (0–5
   in halves, 0 for unrated), ``dateRead`` (``yyyy-mm-dd``: finished, or
   stopped for ``dnf``), ``notes`` (one-line notes from older libraries),
   ``coverImage`` (``/api/covers/<file>?v=…``; absent for a generated cover),
   ``colorIndex`` (the binding colour) and ``addedAt`` (an ISO timestamp).

Word
   ``id``, ``word``, ``phonetic``, ``partOfSpeech``, ``definition``,
   ``example``, ``synonyms`` (a list of strings), ``bookId`` and ``addedAt``.

Progress entry
   ``bookId``, ``date`` (``yyyy-mm-dd``), ``percent`` (0–100) and, for a book
   with a page count, ``page``. There is at most one entry per book and day.

Examples:

.. code-block:: bash

   # Sign in and keep the session cookie
   curl -c jar -d "email=ada@example.com&password=…" http://localhost:8000/login

   # Add or replace a book, then log a day's progress
   curl -b jar -X PUT -H "Content-Type: application/json" \
        -d '{"id": "dune", "title": "Dune", "author": "Frank Herbert", "status": "reading", "pages": 658}' \
        http://localhost:8000/api/books/dune
   curl -b jar -X PUT -H "Content-Type: application/json" \
        -d '{"date": "2026-10-20", "page": 120, "percent": 18.2}' \
        http://localhost:8000/api/progress/dune

   # Preview what a Goodreads import would do, without saving
   curl -b jar -F file=@goodreads_library_export.csv -F mode=preview http://localhost:8000/api/import/csv

Imports answer with what they did: ``POST /api/import`` with ``{books, words,
notes, images, skipped}``, and ``POST /api/import/csv`` with ``{summary:
{source, total, added, updated, read, reading, toRead, dnf, withIsbn, notes,
skipped}, coverIds}`` (``coverIds`` only when applied: the imported books
still without a cover).

API routes
----------

Generated from the app on every build.

.. include:: _generated/routes-api.rst

Pages
-----

The HTML pages and the form posts behind them. Showcase pages (``/s/…``) are
public; everything else needs a signed-in reader and redirects to ``/login``
without one.

.. include:: _generated/routes-pages.rst
