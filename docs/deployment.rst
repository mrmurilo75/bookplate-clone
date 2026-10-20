Deployment guide
================

This guide puts Bookplate on a server for everyday use: running it, giving it
HTTPS, keeping it updated, and backing it up. Every command here was run
against a real deployment while writing it.

What a deployment needs:

* **One app process.** Bookplate is built for a household or a small group;
  one process is plenty. It runs its database migrations when it starts.
* **A database.** Postgres is recommended and comes with the Docker setup.
  SQLite works too for a single reader.
* **A folder for images**: covers and the images pasted into notes.
* **HTTPS in front**, from a reverse proxy, if the server is reachable from the
  internet.

A small server is enough: at rest the app uses about 85 MB of memory and
Postgres about 40 MB.

There are two ways to run it: :ref:`with Docker Compose <deploy-docker>`
(recommended) or :ref:`as a service on the host <deploy-systemd>`.

.. _deploy-docker:

With Docker Compose
-------------------

You need `Docker <https://docs.docker.com/engine/install/>`_ with the Compose
plugin, and git.

1. Get the code. The image is built from it, so keep this folder: updates
   happen here.

   .. code-block:: bash

      git clone https://github.com/mrmurilo75/bookplate-clone.git bookplate
      cd bookplate

2. Configure it. Copy the example settings and edit ``.env``:

   .. code-block:: bash

      cp .env.example .env
      chmod 600 .env
      openssl rand -hex 24      # paste this as DB_PASSWORD

   .. list-table::
      :widths: 25 75

      * - ``DB_PASSWORD``
        - Required. The bundled database's password.
      * - ``PUBLIC_URL``
        - The address people will open, e.g. ``https://books.example.com``.
          With ``https://`` the sign-in cookie is only sent over HTTPS.
      * - ``BOOKPLATE_PORT``
        - Where the app listens on the server. Behind a reverse proxy on the
          same server, use ``127.0.0.1:8000`` so it isn't reachable around the
          proxy. Without a proxy (on a home network, say) ``8000`` listens on
          every address.
      * - ``REGISTRATION``
        - ``closed`` (default): only the first account can be created.
          ``open``: anyone who can reach the server can make their own library;
          consider the ``LIMIT_*`` settings then.

   All the settings are listed under :ref:`configuration`.

3. Start it, waiting until the app answers its health check:

   .. code-block:: bash

      docker compose up -d --build --wait
      docker compose ps         # both services: "Up … (healthy)"

4. Open ``PUBLIC_URL``. The first visit asks for the owner's account; after
   that, sign-up is closed (unless ``REGISTRATION=open``).

The stack is two containers: the app and Postgres 17. The database lives in the
``pgdata`` volume and the images in ``uploads``. Postgres isn't published on
any port, and both containers restart with the server. Docker keeps the last
50 MB of each container's logs.

.. _deploy-https:

HTTPS with a reverse proxy
--------------------------

Bookplate speaks plain HTTP. To serve it over HTTPS, put a reverse proxy in
front, set ``BOOKPLATE_PORT=127.0.0.1:8000`` and
``PUBLIC_URL=https://books.example.com``, and apply the change with
``docker compose up -d --wait``. Point the domain's DNS at the server first.

Caddy
   The simplest choice: it fetches and renews certificates by itself, and has no
   upload size limit. Install `Caddy <https://caddyserver.com/docs/install>`_,
   then put this in ``/etc/caddy/Caddyfile`` and run ``systemctl reload caddy``::

      books.example.com {
          reverse_proxy 127.0.0.1:8000
      }

nginx
   nginx refuses uploads over 1 MB by default, which breaks imports, so raise
   the limit. Put this in ``/etc/nginx/sites-available/bookplate``, link it into
   ``sites-enabled``, then get a certificate with
   ``certbot --nginx -d books.example.com``, which adds the HTTPS part:

   .. code-block:: nginx

      server {
          listen 80;
          server_name books.example.com;

          # Imports can be large: allow up to LIMIT_IMPORT_MB (1024 by default).
          client_max_body_size 1100m;

          location / {
              proxy_pass http://127.0.0.1:8000;
              proxy_set_header Host $host;
              proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
              proxy_set_header X-Forwarded-Proto $scheme;
              proxy_set_header X-Request-Id $request_id;
              proxy_read_timeout 300s;
          }
      }

   Passing ``X-Request-Id`` lets the app log nginx's request ID, so a request
   can be followed through both logs.

Any other proxy works too, as long as it forwards to ``127.0.0.1:8000`` and
accepts uploads up to ``LIMIT_IMPORT_MB``.

If the server isn't reachable from the internet, a VPN such as
`Tailscale <https://tailscale.com>`_ is an alternative to a public proxy.

.. _deploy-systemd:

Without Docker (systemd)
------------------------

Bookplate also runs straight on the host, with SQLite or a Postgres server you
already have. These steps are for a Linux server with systemd, run as root.

1. Install `uv <https://docs.astral.sh/uv/getting-started/installation/>`_ and
   git, create a user for the service, and install the app in ``/opt``.
   ``UV_PYTHON_INSTALL_DIR`` makes uv put Python (if it has to download one)
   outside root's home, where the service can't see it:

   .. code-block:: bash

      useradd --system --home-dir /var/lib/bookplate --shell /usr/sbin/nologin bookplate
      git clone https://github.com/mrmurilo75/bookplate-clone.git /opt/bookplate
      cd /opt/bookplate
      UV_PYTHON_INSTALL_DIR=/opt/uv-python uv sync --frozen --no-dev

2. Write the settings to ``/etc/bookplate.env`` (readable by root only:
   ``chmod 600``). With SQLite:

   .. code-block:: bash

      DATABASE_URL=sqlite:////var/lib/bookplate/bookplate.db
      UPLOADS_DIR=/var/lib/bookplate/uploads
      PUBLIC_URL=https://books.example.com

   With Postgres, use its address instead, e.g.
   ``DATABASE_URL=postgresql://bookplate:PASSWORD@localhost/bookplate``.

3. Create ``/etc/systemd/system/bookplate.service``:

   .. code-block:: ini

      [Unit]
      Description=Bookplate reading tracker
      Wants=network-online.target
      After=network-online.target

      [Service]
      Type=exec
      User=bookplate
      WorkingDirectory=/opt/bookplate
      EnvironmentFile=/etc/bookplate.env
      ExecStart=/opt/bookplate/.venv/bin/uvicorn bookplate.main:app --host 127.0.0.1 --port 8000 --proxy-headers --no-access-log
      Restart=on-failure
      # Data lives in /var/lib/bookplate (created for the bookplate user); everything else is read-only.
      StateDirectory=bookplate
      ProtectSystem=strict
      ProtectHome=true
      PrivateTmp=true
      NoNewPrivileges=true

      [Install]
      WantedBy=multi-user.target

   With Postgres on the same server, add ``postgresql.service`` to ``After=``.

4. Start it and check it answers:

   .. code-block:: bash

      systemctl daemon-reload
      systemctl enable --now bookplate
      curl http://127.0.0.1:8000/api/health

5. Put a reverse proxy in front, as :ref:`above <deploy-https>`.

Updating
--------

Database changes are applied automatically when the new version starts. Take a
:ref:`backup <deploy-backups>` first.

With Docker:

.. code-block:: bash

   git pull
   docker compose up -d --build --wait

As a service:

.. code-block:: bash

   cd /opt/bookplate
   git pull
   UV_PYTHON_INSTALL_DIR=/opt/uv-python uv sync --frozen --no-dev
   systemctl restart bookplate

To stay on a particular version, check out that commit or tag instead of
pulling. Going back to an older version whose database is older too means
restoring the backup taken before the update.

.. _deploy-backups:

Backups
-------

Each reader can download their whole library (books, notes, images, covers,
progress and vocabulary) from **Settings → Import & export → Export library**,
and import it into any Bookplate. For the whole server, back up the database
and the images.

With Docker
   .. code-block:: bash

      docker compose exec -T postgres pg_dump -U bookplate bookplate > bookplate.sql
      docker compose cp bookplate:/data/uploads ./uploads-backup

   For a nightly database backup, create a ``backups`` folder next to
   ``docker-compose.yml``; then a line like this in root's crontab (``%`` must
   be written ``\%`` there) keeps a compressed dump per day:

   .. code-block:: bash

      15 3 * * * cd /path/to/bookplate && docker compose exec -T postgres pg_dump -U bookplate bookplate | gzip > backups/bookplate-$(date +\%F).sql.gz

As a service
   Stop it briefly and archive its data folder; with Postgres, use ``pg_dump``
   as well:

   .. code-block:: bash

      systemctl stop bookplate
      tar czf bookplate-$(date +%F).tgz -C /var/lib bookplate
      systemctl start bookplate

Keep copies somewhere other than the server.

Restoring with Docker
~~~~~~~~~~~~~~~~~~~~~

On a fresh deployment (or after ``docker compose down -v``), restore the
database before the app first starts, so it finds its tables already there:

.. code-block:: bash

   docker compose up -d --wait postgres
   docker compose exec -T postgres psql -q -U bookplate -d bookplate < bookplate.sql
   docker compose up -d --build --wait
   docker compose cp ./uploads-backup/. bookplate:/data/uploads

For a compressed dump, use ``gunzip -c bookplate-….sql.gz |`` in place of
``< bookplate.sql``. Everyone's password stays as it was.

Running it
----------

Logs
   One JSON line per request (health checks aside), with its request ID (also
   sent back as the ``X-Request-Id`` header):

   .. code-block:: bash

      docker compose logs bookplate --since 1h
      journalctl -u bookplate --since "1 hour ago"    # as a service

Health check
   ``GET /api/health`` answers ``{"ok": true, "version": "…"}`` without
   signing in; point an uptime monitor at it. Docker uses it for the
   container's health.

Forgotten passwords
   The command asks for the new password twice and signs out every device:

   .. code-block:: bash

      docker compose exec bookplate bookplate-reset-password you@example.com
      # as a service:
      sh -c 'set -a; . /etc/bookplate.env; exec /opt/bookplate/.venv/bin/bookplate-reset-password you@example.com'

Security checklist
------------------

* Serve it over HTTPS, with ``PUBLIC_URL`` starting with ``https://``, so the
  sign-in cookie is never sent unencrypted.
* Behind a proxy, keep the app on ``127.0.0.1`` (``BOOKPLATE_PORT`` or the
  service's ``--host``) or firewall its port.
* Use a long random ``DB_PASSWORD``, and keep ``.env`` or
  ``/etc/bookplate.env`` readable by root only.
* Leave ``REGISTRATION=closed`` unless you mean strangers to sign up; if open,
  set the ``LIMIT_*`` settings so one account can't fill the disk.
* Back up regularly, keep copies off the server, and try a restore once.
* Update when new versions come out.

Troubleshooting
---------------

``docker compose`` says "set DB_PASSWORD in .env"
   ``.env`` is missing, isn't next to ``docker-compose.yml``, or has no
   ``DB_PASSWORD``.

Signing in just shows the sign-in page again
   ``PUBLIC_URL`` starts with ``https://`` but the site was opened over plain
   HTTP, so the browser drops the secure cookie. Open it at ``PUBLIC_URL``, or
   correct ``PUBLIC_URL``. (Browsers make an exception for ``localhost``, so
   this only shows up from other machines.)

Imports fail with "413 Request Entity Too Large"
   The reverse proxy limits upload size; raise it (nginx:
   ``client_max_body_size``).

The app container isn't healthy
   ``docker compose logs bookplate`` shows why; a wrong ``DATABASE_URL`` or an
   unreachable database are the usual causes.

Catalogue search or word lookups say they failed
   The server can't reach Open Library, iTunes or Wiktionary (a firewall, or
   no outbound internet). Everything else works, and books and words can be
   entered by hand.
