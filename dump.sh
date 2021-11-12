#!/bin/bash -e

psql -h localhost -U "$POSTGRES_USER" -d postgres -c "drop database if exists $POSTGRES_DB;"
psql -h localhost -U "$POSTGRES_USER" -d postgres -c "create database $POSTGRES_DB;"
ssh "$REMOTE_DB" \
    "pg_dump -O -x --exclude-table-data='serverdb_*' -d serveradmin | gzip -9 -c " \
    | gunzip -c \
    | psql -h localhost -U "$POSTGRES_USER" -d "$POSTGRES_DB"