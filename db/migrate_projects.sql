begin;

alter table server
alter column project_id drop not null;

insert into servertype (servertype_id, description, ip_addr_type)
values ('project', 'Project', 'null');

insert into attribute (attribute_id, type, "group", target_servertype_id, clone)
values ('project', 'relation', 'base', 'project', true);

update servertype_attribute
set consistent_via_attribute_id = 'project'
from attribute
join servertype on attribute.target_servertype_id = servertype.servertype_id
where attribute.attribute_id = servertype_attribute.attribute_id
and servertype.fixed_project_id is null;

insert into servertype_attribute (servertype_id, attribute_id, required, default_value, regexp)
select servertype_id, 'project', true, fixed_project_id, '\A[a-z][a-z0-9_]+\Z'
from servertype
where servertype_id != 'project';

insert into server (hostname, servertype_id)
select project_id, 'project'
from project
where project_id != 'acl';

insert into server_relation_attribute (server_id, attribute_id, value)
select server.server_id, 'project', project.server_id
from server
join server as project on server.project_id = project.hostname;

commit;
