#!/bin/bash -e

export PGPASSWORD="$POSTGRES_PASSWORD"

sql() {
    psql -h localhost -U "$POSTGRES_USER" -d $1 -c "$2"
}

sql postgres "drop database if exists $POSTGRES_DB;"
sql postgres "create database $POSTGRES_DB;"
ssh "$REMOTE_DB" \
    "pg_dump -O -x --exclude-table-data='serverdb_*' -d serveradmin | gzip -9 -c " \
    | gunzip -c \
    | psql -h localhost -U "$POSTGRES_USER" -d "$POSTGRES_DB"


# To have less of a risk of accessing production and preventing token leaks
# we better disable applications and change tokens
sql "$POSTGRES_DB" 'update apps_application set disabled = true;'
sql "$POSTGRES_DB" "update apps_application set auth_token = substr(md5(random()::text || id::text), 1, 25);"
