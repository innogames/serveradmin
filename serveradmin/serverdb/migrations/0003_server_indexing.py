# -*- coding: utf-8 -*-

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('serverdb', '0002_lookup_constraints')]
    operations = [
        # Add a pg_trgm based trigram index on the server hostname.
        migrations.RunSQL('CREATE EXTENSION IF NOT EXISTS pg_trgm'),
        migrations.RunSQL(
            'CREATE INDEX server_hostname_trgm '
            'ON server USING gin (hostname gin_trgm_ops)'
        ),
        # Ensure objects within the same servertype have a unique intern_ip.
        migrations.RunSQL('CREATE EXTENSION IF NOT EXISTS btree_gist'),
        migrations.RunSQL(
            # We can't directly use the ip_addr_type from the servertype table
            # in constraints for the server table. Hence we need this function.
            "CREATE FUNCTION get_ip_addr_type(text) RETURNS text"
            "    LANGUAGE sql STRICT IMMUTABLE"
            "    AS 'SELECT ip_addr_type FROM servertype WHERE servertype_id = $1'; "
            "ALTER TABLE server"
            # Objects of servertypes with the ip_addr_type null, must not have
            # an ip address set.
            "    ADD CONSTRAINT server_inter_ip_check"
            "    CHECK ((get_ip_addr_type(servertype_id) = 'null') = (intern_ip IS NULL)),"
            # Objects of servertypes with the ip_addr_type host, must not have
            # the same ip address on multiple objects.
            "    ADD CONSTRAINT server_host_inter_ip_exclude"
            "    EXCLUDE ("
            "        intern_ip WITH ="
            "    )"
            "    WHERE (get_ip_addr_type(servertype_id) = 'host'),"
            # Objects of servertypes with the ip_addr_type loadbalancer, are
            # allowed to use the same ip address on multiple objects. This
            # exlucdes ip addresses used on an object of a servertypes with the
            # ip_addr_type host though.
            # We use this to forward different ports to different hosts as well
            # as for multi datacenter virtual IPs.
            "    ADD CONSTRAINT server_host_loadbalancer_inter_ip_exclude"
            "    EXCLUDE USING gist ("
            "        intern_ip WITH =,"
            "        servertype_id WITH !="
            "    )"
            "    WHERE (get_ip_addr_type(servertype_id) IN ('host', 'loadbalancer')),"
            # Objects of servertypes with the ip_addr_type network, may not
            # have overlapping ip networks within the same servertype.
            # For instance a route_network may be inside a provider_network but
            # a provider_network may not overlap with another provider_network.
            "    ADD CONSTRAINT server_network_inter_ip_exclude"
            "    EXCLUDE USING gist ("
            "        intern_ip inet_ops WITH &&,"
            "        servertype_id WITH ="
            "    )"
            "    WHERE (get_ip_addr_type(servertype_id) = 'network');"
        ),
    ]
