begin;

create schema if not exists dns_public;

create table dns_public.supermasters (
    ip                    inet not null,
    nameserver            varchar(255) not null,
    account               varchar(40) not null,
    primary key(ip, nameserver)
);

grant select on table dns_public.supermasters to dns_public;

create table dns_public.comments (
    id                    serial primary key,
    domain_id             int not null,
    name                  varchar(255) not null,
    type                  varchar(10) not null,
    modified_at           int not null,
    account               varchar(40) default null,
    comment               varchar(65535) not null,
    constraint c_lowercase_name check (name = lower(name))
);

create index comments_domain_id_idx on dns_public.comments (domain_id);
create index comments_name_type_idx on dns_public.comments (name, type);
create index comments_order_idx on dns_public.comments (domain_id, modified_at);

grant select on table dns_public.comments to dns_public;

create table dns_public.domainmetadata (
    id                    serial primary key,
    domain_id             int,
    kind                  varchar(32),
    content               text
);

grant select, delete, insert on table dns_public.domainmetadata to dns_public;
grant usage on sequence dns_public.domainmetadata_id_seq to dns_public;

create index domainidmetaindex on dns_public.domainmetadata(domain_id);

create table dns_public.cryptokeys (
    id                    serial primary key,
    domain_id             int,
    flags                 int not null,
    active                bool,
    content               text
);

grant select, insert, delete on table dns_public.cryptokeys to dns_public;
grant usage on sequence dns_public.cryptokeys_id_seq to dns_public;

create index domainidindex on dns_public.cryptokeys(domain_id);

create table dns_public.tsigkeys (
    id                    serial primary key,
    name                  varchar(255),
    algorithm             varchar(50),
    secret                varchar(255),
    constraint c_lowercase_name check (name = lower(name))
);

grant select on table dns_public.tsigkeys to dns_public;
create unique index namealgoindex on dns_public.tsigkeys(name, algorithm);

commit;
