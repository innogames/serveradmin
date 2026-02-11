#!/bin/bash -e

source .env

# Install or update dependencies on every start in case something changed
pipenv install --dev

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
pipenv run python -m serveradmin migrate --no-input

# Requires Django >= 3.x
# pipenv run python -m serveradmin createsuper --no-input
pipenv run python -m serveradmin createdefaultuser

# Create default application
pipenv run python -m serveradmin createapp --non-interactive

echo -e "
********************************************************************************

\e[32m[TIPS]\e[39m
- Run 'docker compose exec web /bin/bash' to access web service
- Run 'pipenv run python -m serveradmin -h' in web service to access django commands
- Run 'pipenv run python -m adminapi example.com' in web service to make adminapi queries

\e[33mAccess serveradmin from your browser via:\e[39m
- URL: http://127.0.0.1:8000
- User: ${DJANGO_SUPERUSER_USERNAME}
- Password: ${DJANGO_SUPERUSER_PASSWORD}

********************************************************************************
"

# Start development server reachable for host machine
pipenv run python -m serveradmin runserver 0.0.0.0:8000