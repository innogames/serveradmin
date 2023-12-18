FROM powerdns/pdns-auth-48:latest

ARG GPGSQL_HOST
ARG GPGSQL_PORT
ARG GPGSQL_DBNAME
ARG GPGSQL_USER
ARG GPGSQL_PASSWORD

COPY pdns.conf /etc/powerdns/pdns.conf
COPY entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
