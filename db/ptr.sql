-- Reverse DNS name of an address. Plain SQL (no STRICT, no sub-SELECT, only
-- immutable functions) so Postgres inlines it into the calling query; it
-- expands the address from the inet_send() wire bytes (4 header bytes, then
-- the address), so the netmask is ignored. Kept in sync with
-- serveradmin_extras/serveradmin_powerdns/migrations/0006_ptr_function.py.
create or replace function public.ptr(intern_ip inet) returns text
language sql immutable parallel safe as $$
select case family(intern_ip)
    when 4 then
        get_byte(inet_send(intern_ip), 7)::text || '.' ||
        get_byte(inet_send(intern_ip), 6)::text || '.' ||
        get_byte(inet_send(intern_ip), 5)::text || '.' ||
        get_byte(inet_send(intern_ip), 4)::text || '.in-addr.arpa'
    else
        regexp_replace(reverse(encode(substring(inet_send(intern_ip) from 5), 'hex')), '(.)', '\1.', 'g')
        || 'ip6.arpa'
end
$$;

create index concurrently server_ptr_idx on public.server(public.ptr(intern_ip) text_pattern_ops);

create index concurrently server_inet_attribute_ptr_idx on public.server_inet_attribute(public.ptr(value) text_pattern_ops);
