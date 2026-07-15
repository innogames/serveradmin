.. image:: https://github.com/innogames/serveradmin/actions/workflows/tests.yml/badge.svg
    :target: https://github.com/innogames/serveradmin/actions/workflows/tests.yml/badge.svg
    :alt: Continuous Integration Status

.. image:: https://readthedocs.org/projects/serveradmin/badge/?version=latest
    :target: https://serveradmin.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

Serveradmin
===========

Serveradmin is central server database management system of InnoGames.  It
has a HTTP web interface and a HTTP JSON API.  Check out `the documentation
<https://serveradmin.readthedocs.io/en/latest/>`_  or watch `this FOSDEM 19
talk <https://archive.org/details/youtube-nWuisFTIgME>`_ for a deepdive how
InnoGames works with serveradmin.


Quickstart
----------

The fastest way to get a local Serveradmin running is the provided Docker
Compose setup.  It starts the web application together with a PostgreSQL
database, installs all dependencies, applies the database schema and creates a
default user - no local Python or PostgreSQL installation required.

.. note::
   This setup is meant for local development and evaluation, not production.

You need:

* `Git <https://git-scm.com/downloads>`_
* `Docker Engine <https://docs.docker.com/engine/install/>`_ with the
  `Compose plugin <https://docs.docker.com/compose/install/>`_

Get it running::

    git clone https://github.com/innogames/serveradmin
    cd serveradmin
    cp .env.dist .env
    docker compose up

The defaults in ``.env.dist`` work out of the box; adjust them later if needed.
On the first start the containers install the dependencies, run the database
migrations and create a default super user, then start the development server.

Once it is ready, open http://127.0.0.1:8000 and log in with the default
credentials ``serveradmin`` / ``serveradmin``.

To run management commands or the Python Remote API, open a shell in the
running ``web`` container::

    docker compose exec web bash

    # Django management commands
    uv run python -m serveradmin -h

    # Python Remote API
    uv run python -m adminapi "hostname=example.com"

See the `documentation <https://serveradmin.readthedocs.io/en/latest/>`_ for
configuration, development and extension topics.


License
-------

The project is released under the MIT License.  The MIT License is registered
with and approved by the `Open Source Initiative <https://opensource.org/licenses/MIT>`_.
