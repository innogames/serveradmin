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

if [[ $GPGSQL_USER == *"secondary"* ]]; then
  echo "This node is secondary"
  echo "secondary=yes" >> /etc/powerdns/pdns.d/replication.conf
  echo "allow-notify-from=172.18.0.0/24" >> /etc/powerdns/pdns.d/replication.conf
else
  echo "This node is primary"
  echo "primary=yes" >> /etc/powerdns/pdns.d/replication.conf
  echo "allow-axfr-ips=172.18.0.0/24" >> /etc/powerdns/pdns.d/replication.conf
fi

# https://github.com/PowerDNS/pdns/blob/master/Dockerfile-auth#L106
/usr/bin/tini -- /usr/local/sbin/pdns_server-startup
