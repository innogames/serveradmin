vacuum;

begin;

--
-- Orphan attributes
--

delete from server_relation_attribute as extra
where not exists (
    select 1
    from attribute
    where attribute.attribute_id = extra.attribute_id and
        attribute.type = 'relation'
) or not exists (
    select 1
    from server
    join servertype_attribute using (servertype_id)
    where server.server_id = extra.server_id and
        servertype_attribute.attribute_id = extra.attribute_id and
        servertype_attribute.related_via_attribute_id is null
)
returning *;

delete from server_number_attribute as extra
where not exists (
    select 1
    from attribute
    where attribute.attribute_id = extra.attribute_id and
        attribute.type = 'number'
) or not exists (
    select 1
    from server
    join servertype_attribute using (servertype_id)
    where server.server_id = extra.server_id and
        servertype_attribute.attribute_id = extra.attribute_id and
        servertype_attribute.related_via_attribute_id is null
)
returning *;

delete from server_string_attribute as extra
where not exists (
    select 1
    from attribute
    where attribute.attribute_id = extra.attribute_id and
        attribute.type in ('string', 'integer', 'boolean')
) or not exists (
    select 1
    from server
    join servertype_attribute using (servertype_id)
    where server.server_id = extra.server_id and
        servertype_attribute.attribute_id = extra.attribute_id and
        servertype_attribute.related_via_attribute_id is null
)
returning *;

delete from server_inet_attribute as extra
where not exists (
    select 1
    from attribute
    where attribute.attribute_id = extra.attribute_id and
        attribute.type = 'inet'
) or not exists (
    select 1
    from server
    join servertype_attribute using (servertype_id)
    where server.server_id = extra.server_id and
        servertype_attribute.attribute_id = extra.attribute_id and
        servertype_attribute.related_via_attribute_id is null
)
returning *;

delete from server_macaddr_attribute as extra
where not exists (
    select 1
    from attribute
    where attribute.attribute_id = extra.attribute_id and
        attribute.type = 'macaddr'
) or not exists (
    select 1
    from server
    join servertype_attribute using (servertype_id)
    where server.server_id = extra.server_id and
        servertype_attribute.attribute_id = extra.attribute_id and
        servertype_attribute.related_via_attribute_id is null
)
returning *;

--
-- Single but multi attributes
--

delete from server_relation_attribute as extra
where not exists (
    select 1
    from attribute
    where attribute.attribute_id = extra.attribute_id and
        attribute.multi
) and exists (
    select 1
    from server_relation_attribute as attribute
    where attribute.server_id = extra.server_id and
        attribute.attribute_id = extra.attribute_id and
        attribute.id > extra.id
)
returning *;

delete from server_number_attribute as extra
where not exists (
    select 1
    from attribute
    where attribute.attribute_id = extra.attribute_id and
        attribute.multi
) and exists (
    select 1
    from server_number_attribute as attribute
    where attribute.server_id = extra.server_id and
        attribute.attribute_id = extra.attribute_id and
        attribute.id > extra.id
)
returning *;

delete from server_string_attribute as extra
where not exists (
    select 1
    from attribute
    where attribute.attribute_id = extra.attribute_id and
        attribute.multi
) and exists (
    select 1
    from server_string_attribute as attribute
    where attribute.server_id = extra.server_id and
        attribute.attribute_id = extra.attribute_id and
        attribute.id > extra.id
)
returning *;

--
-- Hostname attributes targeting wrong server
--

delete from server_relation_attribute as extra
using attribute, server as target
where attribute.attribute_id = extra.attribute_id
and target.server_id = extra.value
and attribute.target_servertype_id != target.servertype_id
returning attribute.attribute_id, target.hostname;

commit;
