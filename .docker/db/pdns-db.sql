-- PowerDNS database for the docker compose profile "powerdns".
--
-- Run by the pdns-db-init service on every start:
--   psql -v ON_ERROR_STOP=1 -v pdns_db=... -v pdns_user=... -v pdns_password=...
--        -h db -U $POSTGRES_USER -d postgres -f /pdns-db.sql
-- Everything is idempotent, so it also works on an existing postgres-data
-- volume (Postgres initdb scripts would only run on an empty one).

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'pdns_user', :'pdns_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'pdns_user') \gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'pdns_db', :'pdns_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'pdns_db') \gexec

\connect :pdns_db

-- Create the tables as the PowerDNS role so it owns them and needs no grants.
SET ROLE :"pdns_user";

-- Schema of the generic PostgreSQL backend, PowerDNS Authoritative 5.0.x:
-- https://github.com/PowerDNS/pdns/blob/rel/auth-5.0.x/modules/gpgsqlbackend/schema.pgsql.sql
-- Verbatim except for the added IF NOT EXISTS clauses.

CREATE TABLE IF NOT EXISTS domains (
  id                    SERIAL PRIMARY KEY,
  name                  VARCHAR(255) NOT NULL,
  master                VARCHAR(128) DEFAULT NULL,
  last_check            INT DEFAULT NULL,
  type                  TEXT NOT NULL,
  notified_serial       BIGINT DEFAULT NULL,
  account               VARCHAR(40) DEFAULT NULL,
  options               TEXT DEFAULT NULL,
  catalog               TEXT DEFAULT NULL,
  CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT)))
);

CREATE UNIQUE INDEX IF NOT EXISTS name_index ON domains(name);
CREATE INDEX IF NOT EXISTS catalog_idx ON domains(catalog);


CREATE TABLE IF NOT EXISTS records (
  id                    BIGSERIAL PRIMARY KEY,
  domain_id             INT DEFAULT NULL,
  name                  VARCHAR(255) DEFAULT NULL,
  type                  VARCHAR(10) DEFAULT NULL,
  content               VARCHAR(65535) DEFAULT NULL,
  ttl                   INT DEFAULT NULL,
  prio                  INT DEFAULT NULL,
  disabled              BOOL DEFAULT 'f',
  ordername             VARCHAR(255),
  auth                  BOOL DEFAULT 't',
  CONSTRAINT domain_exists
  FOREIGN KEY(domain_id) REFERENCES domains(id)
  ON DELETE CASCADE,
  CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT)))
);

CREATE INDEX IF NOT EXISTS rec_name_index ON records(name);
CREATE INDEX IF NOT EXISTS nametype_index ON records(name,type);
CREATE INDEX IF NOT EXISTS domain_id ON records(domain_id);
CREATE INDEX IF NOT EXISTS recordorder ON records (domain_id, ordername text_pattern_ops);


CREATE TABLE IF NOT EXISTS supermasters (
  ip                    INET NOT NULL,
  nameserver            VARCHAR(255) NOT NULL,
  account               VARCHAR(40) NOT NULL,
  PRIMARY KEY(ip, nameserver)
);


CREATE TABLE IF NOT EXISTS comments (
  id                    SERIAL PRIMARY KEY,
  domain_id             INT NOT NULL,
  name                  VARCHAR(255) NOT NULL,
  type                  VARCHAR(10) NOT NULL,
  modified_at           INT NOT NULL,
  account               VARCHAR(40) DEFAULT NULL,
  comment               VARCHAR(65535) NOT NULL,
  CONSTRAINT domain_exists
  FOREIGN KEY(domain_id) REFERENCES domains(id)
  ON DELETE CASCADE,
  CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT)))
);

CREATE INDEX IF NOT EXISTS comments_domain_id_idx ON comments (domain_id);
CREATE INDEX IF NOT EXISTS comments_name_type_idx ON comments (name, type);
CREATE INDEX IF NOT EXISTS comments_order_idx ON comments (domain_id, modified_at);


CREATE TABLE IF NOT EXISTS domainmetadata (
  id                    SERIAL PRIMARY KEY,
  domain_id             INT REFERENCES domains(id) ON DELETE CASCADE,
  kind                  VARCHAR(32),
  content               TEXT
);

CREATE INDEX IF NOT EXISTS domainidmetaindex ON domainmetadata(domain_id);


CREATE TABLE IF NOT EXISTS cryptokeys (
  id                    SERIAL PRIMARY KEY,
  domain_id             INT REFERENCES domains(id) ON DELETE CASCADE,
  flags                 INT NOT NULL,
  active                BOOL,
  published             BOOL DEFAULT TRUE,
  content               TEXT
);

CREATE INDEX IF NOT EXISTS domainidindex ON cryptokeys(domain_id);


CREATE TABLE IF NOT EXISTS tsigkeys (
  id                    SERIAL PRIMARY KEY,
  name                  VARCHAR(255),
  algorithm             VARCHAR(50),
  secret                VARCHAR(255),
  CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT)))
);

CREATE UNIQUE INDEX IF NOT EXISTS namealgoindex ON tsigkeys(name, algorithm);
