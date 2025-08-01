#!/bin/bash -e

source .env

# Install or update dependencies on every start in case something changed
python3 -m pipenv install --dev

# Wait for database to be available before running migrations
until pg_isready -h "$POSTGRES_HOST" -U "$POSTGRES_USER" &> /dev/null; do
  echo "Waiting for database to be ready on ${POSTGRES_HOST} ..."
  sleep 5
done

# Apply pending migrations on every start
python3 -m pipenv run python -m serveradmin migrate --no-input

# Requires Django >= 3.x
# pipenv run python -m serveradmin createsuper --no-input
python3 -m pipenv run python -m serveradmin createdefaultuser

# Create default application
python3 -m pipenv run python -m serveradmin createapp --non-interactive

echo -e "
********************************************************************************

\e[32m[TIPS]\e[39m
- Run 'docker compose exec web /bin/bash' to access web service
- Run 'python3 -m pipenv run python -m serveradmin -h' in web service to access django commands
- Run 'python3 -m pipenv run python -m adminapi example.com' in web service to make adminapi queries

\e[33mAccess serveradmin from your browser via:\e[39m
- URL: http://127.0.0.1:8000
- User: ${DJANGO_SUPERUSER_USERNAME}
- Password: ${DJANGO_SUPERUSER_PASSWORD}

********************************************************************************
"

# Start development server reachable for host machine
python3 -m pipenv run python -m serveradmin runserver 0.0.0.0:8000