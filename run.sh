#!/bin/bash -e

# Install or update dependencies on every start in case something changed
pipenv install --dev

# Apply pending migrations on every start
pipenv run python -m serveradmin migrate

# Requires Django >= 3.x
# pipenv run python -m serveradmin createsuper --no-input
pipenv run python -m serveradmin createdefaultuser

# Create default application
pipenv run python -m serveradmin createapp --non-interactive

echo -e "
\033[0;37m
********************************************************************************

\033[0;32m[USEFUL TIPS]\033[0;37m
Run 'docker-compose exec web /bin/bash' to access web service
Run 'pipenv run python -m serveradmin -h' in web service to access django commands
Run 'pipenv run python -m adminapi example.com' in web service to make adminapi queries

********************************************************************************
"

# Start development server reachable for host machine
pipenv run python -m serveradmin runserver 0.0.0.0:8000