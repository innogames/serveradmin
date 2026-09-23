create or replace function public.ptr(intern_ip inet) returns text
immutable strict language plpgsql as $$
declare
    ip_part text;
    ip_text text;
    ip_arr text[];
    ip_filled boolean;
begin
    if family(intern_ip) = 4 then
        return (
            select string_agg(part, '.'  order by ord desc) || '.in-addr.arpa'
            from regexp_split_to_table(host(intern_ip), '\.') with ordinality as s(part, ord)
        );
    else
        ip_text := '';
        ip_arr := regexp_split_to_array(host(intern_ip), ':');
        ip_filled = false;

        foreach ip_part in array ip_arr loop
            if length(ip_part) = 0 and not ip_filled then
                ip_text := ip_text || repeat('0', 32 - (array_length(ip_arr, 1) - 1) * 4);
                ip_filled = true;
            else
                ip_text := ip_text || lpad(ip_part, 4, '0');
            end if;
        end loop;

        return (
            select string_agg(part[1], '.' order by ord desc) || '.ip6.arpa'
            from regexp_matches(ip_text, '.', 'g') with ordinality as s(part, ord)
        );
    end if;
end;
$$;

create index concurrently server_ptr_idx on public.server(public.ptr(intern_ip) text_pattern_ops);

create index concurrently server_inet_attribute_ptr_idx on public.server_inet_attribute(public.ptr(value) text_pattern_ops);
