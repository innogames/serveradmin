begin;

create schema if not exists dns_public;

create or replace view dns_public.domains as
select
    0 as id,
    hostname::text as name,
    null::text as master,
    null::int as last_check,
    'NATIVE'::text as type,
    null::int as notified_serial,
    null::text as account
from public.server
where servertype_id = 'provider_domain';

create or replace view dns_public.cryptokeys as
select
    0 as id,
    0 as domain_id,
    257 as flags,
    true as active,
    e'Private-key-format: v1.2\nAlgorithm: 13 (ECDSAP256SHA256)\nPrivateKey: K/gOdrQSkCSUOvhT6Xq1ulv5Www1RXIjlgbhIkL2kdQ=\n'::text as content;

create or replace view dns_public.domainmetadata as
select
    0 as id,
    0 as domain_id,
    kind,
    content
from (values
    ('NSEC3PARAM'::text, '1 0 8 e5b7'::text),
    ('NSEC3NARROW'::text, '1'::text)
) as r(kind,content);

create or replace view dns_public.records as
select
    0 as id,
    0 as domain_id,
    r.name,
    r.type,
    r.content,
    86400 as ttl,
    0 as prio,
    0 as change_date,
    false as disabled,
    null::text as ordername,
    true as auth
from (
    select
        server.hostname::text as name,
        v.type::text,
        v.content::text
    from public.server
    cross join (values
        ('SOA', 'dnspub-af.innogames.de. hostmaster.innogames.de.'),
        ('NS', 'dnspub-af.innogames.de'),
        ('NS', 'dnspub-aw.innogames.de'),
        ('NS', 'dnspub-vn.innogames.de')
    ) as v(type, content)
    where server.servertype_id = 'provider_domain'
union all
    select
        server.hostname::text as name,
        null::text as type,
        null::text as content
    from public.server
    where server.servertype_id = 'project_domain'
union all
    select
        server.hostname::text as name,
        case family(server.intern_ip) when 4 then 'A'::text else 'AAAA'::text end as type,
        host(server.intern_ip) as content
    from public.server
    where server.servertype_id in ('vm_external', 'hardware_external')
union all
    select
        server.hostname::text as name,
        case family(attribute.value) when 4 then 'A'::text else 'AAAA'::text end as type,
        host(attribute.value) as content
    from public.server
    join public.server_inet_attribute as attribute using (server_id)
    where server.servertype_id in ('vm_external', 'hardware_external')
union all
    select
        domain.hostname::text as name,
        case family(server.intern_ip) when 4 then 'A'::text else 'AAAA'::text end as type,
        host(server.intern_ip) as content
    from public.server
    join public.server_relation_attribute as domain_attribute using (server_id)
    join public.server as domain on domain_attribute.value = domain.server_id
    where server.intern_ip is not null and
        domain_attribute.attribute_id = 'domain'
union all
    select
        domain.hostname::text as name,
        case family(attribute.value) when 4 then 'A'::text else 'AAAA'::text end as type,
        host(attribute.value) as content
    from public.server
    join public.server_inet_attribute as attribute using (server_id)
    join public.server_relation_attribute as domain_attribute using (server_id)
    join public.server as domain on domain_attribute.value = domain.server_id
    where server.intern_ip is not null and
        domain_attribute.attribute_id = 'domain'
union all
    select
        server.hostname::text as name,
        'MX'::text as type,
        mx.hostname::text as content
    from public.server
    join public.server_relation_attribute as mx_attribute using (server_id)
    join public.server as mx on mx_attribute.value = mx.server_id
    where mx_attribute.attribute_id = 'mx'
union all
    select
        server.hostname::text as name,
        'SSHFP'::text as type,
        attribute.value::text as content
    from public.server
    join public.server_string_attribute as attribute using (server_id)
    where server.servertype_id in ('vm_external', 'hardware_external') and
        attribute.attribute_id = 'sshfp'
union all
    select
        public.ptr(server.intern_ip) as name,
        'PTR'::text as type,
        domain.hostname::text as content
    from public.server
    join public.server_relation_attribute as domain_attribute using (server_id)
    join public.server as domain on domain_attribute.value = domain.server_id
    where server.intern_ip is not null and
        hostmask(server.intern_ip) in ('0.0.0.0', '::') and
        domain_attribute.attribute_id = 'domain'
union all
    select
        public.ptr(attribute.value) as name,
        'PTR'::text as type,
        domain.hostname::text as content
    from public.server
    join public.server_inet_attribute as attribute using (server_id)
    join public.server_relation_attribute as domain_attribute using (server_id)
    join public.server as domain on domain_attribute.value = domain.server_id
    where server.intern_ip is not null and
        hostmask(attribute.value) in ('0.0.0.0', '::') and
        domain_attribute.attribute_id = 'domain'
) as r;

grant usage on schema dns_public to dns_public;
grant select on dns_public.domains to dns_public;
grant select on dns_public.cryptokeys to dns_public;
grant select on dns_public.domainmetadata to dns_public;
grant select on dns_public.records to dns_public;
grant select on public.server to dns_public;
grant select on public.server_string_attribute to dns_public;

commit;
