#!/bin/bash -e

# Not everybody has a Shell extension to load .env files
if [ -f .env ]; then
  source .env
fi

export PGPASSWORD="$POSTGRES_PASSWORD"

sql() {
    psql -h localhost -U "$POSTGRES_USER" -d $1 -c "$2"
}

sql postgres "drop database if exists $POSTGRES_DB;"
sql postgres "create database $POSTGRES_DB;"

# We exclude some tables:
#
# - 'serverdb_*' because it is huge and usually not needed locally
# - 'apps_application' because it contains access tokens for production
ssh "$REMOTE_DB" \
    "pg_dump -O -x --exclude-table-data='serverdb_*' --exclude-table-data='apps_application' -d serveradmin | gzip -9 -c " \
    | gunzip -c \
    | psql -h localhost -U "$POSTGRES_USER" -d "$POSTGRES_DB"

# Hint the user why access might not work after dumping the database
echo -e '\e[33mYou must restart the docker compose web service to create the "serveradmin" user again or create it manually!\e[39m'