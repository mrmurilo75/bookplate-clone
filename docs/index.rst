Bookplate (Python port)
=======================

A Python port of `Bookplate <https://github.com/LeoPhh/bookplate>`_, a
self-hosted personal reading tracker with a bold editorial look. Books carry
ratings, reading dates, reading progress and their own notes pages, and can
wear real cover photos; a vocabulary registry keeps the words learned along
the way. Everything can be exported as a zip of plain JSON, markdown and image
files in the original's format, so libraries move freely between the two.

It is built with FastAPI, Jinja2 (server-rendered pages and three small
scripts), SQLModel on SQLite or Postgres, Alembic, uv, ruff and pytest-bdd.

.. toctree::
   :maxdepth: 2

   install
   deployment
   guide
   http-api
   development
   reference

* :ref:`genindex`
* :ref:`modindex`
