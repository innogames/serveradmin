from serveradmin.serverdb.models import ServerAttribute, Attribute
from django.db import connection


class ViewSQL:
    """Class to manage the "records" View which represents all configured DNS
    records bases on the serveradmin data."""

    @classmethod
    def update_view_schema(cls):
        with connection.cursor() as cursor:
            sql = cls.get_record_view_sql()
            cursor.execute(sql)

    @classmethod
    def get_record_view_sql(cls):
        from serveradmin.powerdns.models import RecordSetting

        # - todo: Escape parameters injected
        # - todo: check materialized view with proper indexes
        # - todo if view schema is safe, remove it and only REPLACE VIEW
        sql = 'DROP VIEW IF EXISTS powerdns_records;'
        sql += "CREATE OR REPLACE VIEW powerdns_records (object_id, name, type, content, domain, ttl) AS ("
        sub_queries = []
        for record_setting in RecordSetting.objects.all():
            name_expression = cls.get_name_expression(record_setting)
            type_expression = cls.get_record_type_expression(record_setting)
            content_expression = cls.get_content_expression(record_setting)
            domain_expression = cls.get_domain_expression(record_setting)
            attribute_join = cls.get_attribute_join(record_setting)
            domain_join = cls.get_domain_join(record_setting)
            if record_setting.record_type == 'PTR':
                content_expression = 's.hostname'

            sub_queries.append(
                f"""
                SELECT 
                    s.server_id as object_id,
                    {name_expression} as name,
                    {type_expression} as type,
                    {content_expression} as content,
                    {domain_expression} as domain,
                    {record_setting.ttl} as ttl
                FROM 
                    server s
                {attribute_join}
                {domain_join}
                WHERE 
                    s.servertype_id = '{record_setting.servertype}'
            """
            )
        sql += " UNION ALL ".join(sub_queries)
        sql += ");"

        return sql

    @staticmethod
    def get_content_expression(record_setting):
        if record_setting.source_value_special:
            attribute = Attribute.specials[record_setting.source_value_special]
            if attribute.type == 'inet':
                # get plain IP address from inet (which also contains the netmask)
                return f"host(s.{attribute.attribute_id})"
            else:
                return f"s.{attribute.attribute_id}::text"
        elif record_setting.source_value.type == "inet":
            # get plain IP from inet (which also contains the netmask)
            return "host(tt.value)"
        elif record_setting.source_value.type == "relation":
            return "rs.hostname"
        else:
            return "tt.value::text"

    @staticmethod
    def get_attribute_join(record_setting):
        if record_setting.source_value_special:
            # the needed attribute is already in the server table
            attribute_join = ""
        elif record_setting.source_value.type == "relation":
            attribute_join = f"""
                JOIN server_relation_attribute ra
                    ON ra.server_id = s.server_id 
                    AND ra.attribute_id = '{record_setting.source_value}'
                JOIN server as rs on ra.value = rs.server_id    
                    """
        else:
            target_table = ServerAttribute.get_model(record_setting.source_value.type)._meta.db_table
            attribute_join = f"""
                JOIN {target_table} tt
                    ON tt.server_id = s.server_id 
                    AND tt.attribute_id = '{record_setting.source_value}'
                    """

        return attribute_join

    @classmethod
    def get_record_type_expression(cls, record_setting):
        if record_setting.record_type == 'A_AAAA':
            # support meta record type to get A or AAAA based on IP family
            return f"case family({cls.get_content_expression(record_setting)}::inet) when 4 then 'A'::text else 'AAAA'::text end"

        return f"'{record_setting.record_type}'"

    @classmethod
    def get_name_expression(cls, record_setting):
        if record_setting.record_type == 'PTR':
            content = cls.get_content_expression(record_setting)
            return f"public.ptr({content}::inet)"
        elif record_setting.domain:
            return f"domain_name.hostname"
        else:
            return 's.hostname'

    @classmethod
    def get_domain_expression(cls, record_setting):
        if record_setting.record_type == 'PTR':
            # for the PTR we have to put the record in the correct pseudo arpa zone.
            return f"case family({cls.get_content_expression(record_setting)}::inet) when 4 then 'in-addr.arpa' else 'ip6.arpa' end"
        elif record_setting.domain:
            return f"domain_name.hostname"
        else:
            return 's.hostname'

    @classmethod
    def get_domain_join(cls, record_setting):
        if record_setting.domain:
            return f""" 
                JOIN server_relation_attribute domain
                    ON domain.server_id = s.server_id 
                    AND domain.attribute_id = '{record_setting.domain}'
                JOIN server domain_name
                     ON domain_name.server_id = domain.value"""
        return ""
