#!/bin/bash

cat <<EOF > /etc/powerdns/pdns.d/pdns.local.gpgsql.conf
launch=gpgsql
gpgsql-host=$GPGSQL_HOST
gpgsql-port=$GPGSQL_PORT
gpgsql-dbname=$GPGSQL_DBNAME
gpgsql-user=$GPGSQL_USER
gpgsql-password=$GPGSQL_PASSWORD
gpgsql-dnssec=no
EOF

until timeout 5 bash -c "</dev/tcp/web/8000" &> /dev/null; do
  echo "Waiting for database to be ready ..."
  sleep 5
done

# https://github.com/PowerDNS/pdns/blob/master/Dockerfile-auth#L106
/usr/bin/tini -- /usr/local/sbin/pdns_server-startup
