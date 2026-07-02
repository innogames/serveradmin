#!/bin/bash -e

source .env

# Install or update dependencies on every start in case something changed.
# --inexact keeps packages that were added to the environment out-of-band (e.g.
# an editable overlay installed via $SERVERADMIN_EXTRA_INSTALL below) instead of
# pruning them. --frozen installs strictly from the committed uv.lock and never
# rewrites it, so a bind-mounted /code/uv.lock can't be mutated from the
# container (e.g. re-resolved against a private index). Re-lock on the host.
uv sync --frozen --inexact

# Optional local overlay: install an additional editable package (e.g. a private
# bundle of serveradmin_* apps) into the same environment. Set via a git-ignored
# docker-compose.override.yml so the open source setup is unaffected.
if [ -n "$SERVERADMIN_EXTRA_INSTALL" ]; then
  echo "Installing extra package from $SERVERADMIN_EXTRA_INSTALL"
  # Unlike `uv sync`, `uv pip` ignores UV_PROJECT_ENVIRONMENT and would target a
  # .venv in the working tree, so pin the interpreter to the same environment.
  # --no-sources ignores the package's [tool.uv.sources] (which point at a host
  # sibling checkout for local dev); serveradmin/adminapi are already installed
  # here by `uv sync`, and the remaining deps resolve from the configured index.
  # $SERVERADMIN_EXTRA_INDEX (optional) scopes a private index to THIS step only,
  # so the core `uv sync` above never sees it and the lockfile stays public.
  extra_index_arg=""
  if [ -n "$SERVERADMIN_EXTRA_INDEX" ]; then
    extra_index_arg="--default-index $SERVERADMIN_EXTRA_INDEX"
  fi
  uv pip install --python "${UV_PROJECT_ENVIRONMENT:-/usr/local}/bin/python" --no-sources $extra_index_arg -e "$SERVERADMIN_EXTRA_INSTALL"
fi

# Some users prefer to develop on their host rather than containers and have adjusted .env
if [ $POSTGRES_HOST == "localhost" ]; then
  echo -e "\033[33mWARNING: Your \$POSTGRES_HOST variable points to localhost not db!\033[0m"
fi

# Wait for database to be available before running migrations
until pg_isready -h "$POSTGRES_HOST" -U "$POSTGRES_USER" &> /dev/null; do
  echo "Waiting for database to be ready on ${POSTGRES_HOST} ..."
  sleep 5
done

# Apply pending migrations on every start
uv run python -m serveradmin migrate --no-input

# Requires Django >= 3.x
# uv run python -m serveradmin createsuper --no-input
uv run python -m serveradmin createdefaultuser

# Create default application
uv run python -m serveradmin createapp --non-interactive

echo -e "
********************************************************************************

\e[32m[TIPS]\e[39m
- Run 'docker compose exec web /bin/bash' to access web service
- Run 'uv run python -m serveradmin -h' in web service to access django commands
- Run 'uv run python -m adminapi example.com' in web service to make adminapi queries

\e[33mAccess serveradmin from your browser via:\e[39m
- URL: http://127.0.0.1:8000
- User: ${DJANGO_SUPERUSER_USERNAME}
- Password: ${DJANGO_SUPERUSER_PASSWORD}

********************************************************************************
"

# Start development server reachable for host machine
uv run python -m serveradmin runserver 0.0.0.0:8000