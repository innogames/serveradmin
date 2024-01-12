from serveradmin.serverdb.models import ServerAttribute, Attribute
from django.db import connection


class ViewSQL:
    """Class to manage the "powerdns_records" View which represents all configured DNS
    records bases on the serveradmin data.
    The view contains ALL DNS related records in a powerdns-like schema and the "object_ids" which are responsible
    for tis record, like vm-server or related domain names
    """

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
        sql = 'DROP VIEW IF EXISTS powerdns_records;'
        sql += "CREATE OR REPLACE VIEW powerdns_records (object_ids, name, type, content, domain, ttl) AS ("
        sub_queries = []
        for record_setting in RecordSetting.objects.all():
            object_ids_expression = cls.get_object_ids_expression(record_setting)
            name_expression = cls.get_name_expression(record_setting)
            type_expression = cls.get_record_type_expression(record_setting)
            content_expression = cls.get_content_expression(record_setting, True)
            domain_expression = cls.get_domain_expression(record_setting)
            attribute_join = cls.get_attribute_join(record_setting)
            domain_join = cls.get_domain_join(record_setting)
            where_condition = cls.get_where_condition(record_setting)

            sub_queries.append(
                f"""
                SELECT 
                    {object_ids_expression} as object_ids,
                    {name_expression} as name,
                    {type_expression} as type,
                    {content_expression} as content,
                    {domain_expression} as domain,
                    {record_setting.ttl} as ttl
                FROM server s
                {attribute_join}
                {domain_join}
                {where_condition}
            """
            )
        sql += " UNION ALL ".join(sub_queries)
        sql += ");"

        return sql

    @staticmethod
    def get_content_expression(record_setting, main: bool = False):
        if record_setting.record_type == 'PTR' and main:
            if record_setting.domain:
                return f"domain_name.hostname"
            else:
                return 's.hostname'

        if record_setting.source_value_special:
            # the content is in the "server table already"
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
        """if the record content is in an non-special attribute, we need to JOIN the attribute table(s)"""
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
        """get the "name" field for the record"""
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
        """Get the JOIN for the domain, if needed"""
        if record_setting.domain:
            return f""" 
                JOIN server_relation_attribute domain
                    ON domain.server_id = s.server_id 
                    AND domain.attribute_id = '{record_setting.domain}'
                JOIN server domain_name
                     ON domain_name.server_id = domain.value"""
        return ""

    @classmethod
    def get_where_condition(cls, record_setting):
        """Add special WHERE conditions to the query, if needed"""
        if record_setting.servertype:
            return f"WHERE s.servertype_id = '{record_setting.servertype}'"
        return ''

    @classmethod
    def get_object_ids_expression(cls, record_setting):
        """Get the expression to get the object_ids for the record
        This are the object_ids of the server and the object_ids of the domain.
        So all objects which are kinda touching this record
        """
        ids = ['s.server_id']
        if record_setting.domain:
            ids.append('domain_name.server_id')

        return f"ARRAY[{','.join(ids)}]::integer[]"
