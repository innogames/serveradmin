from serveradmin.serverdb.models import ServerAttribute, Attribute


class ViewSQL:
    """Class to generate SQL for views for DNS related tables"""

    @classmethod
    def get_record_view_sql(cls):
        from serveradmin.powerdns.models import RecordSetting

        # XXX:
        # - Escape parameters injected
        sql = "CREATE OR REPLACE VIEW records (object_id, name, type, content, domain) AS ("
        sub_queries = []
        for record_setting in RecordSetting.objects.all():
            name_expression = cls.get_name_expression(record_setting)
            type_expression = cls.get_record_type_expression(record_setting)
            content_expression = cls.get_content_expression(record_setting)
            domain_expression = cls.get_domain_expression(record_setting)
            attribute_join = cls.get_attribute_join(record_setting)
            if record_setting.record_type == 'PTR':
                content_expression = 's.hostname'

            sub_queries.append(
                f"""
                SELECT 
                    s.server_id as object_id,
                    {name_expression} as name,
                    {type_expression} as type,
                    {content_expression}::text as content,
                    {domain_expression} as domain         
                FROM 
                    server s
                {attribute_join}
                LEFT JOIN server_relation_attribute domain
                    ON s.server_id = domain.server_id 
                    AND domain.attribute_id = '{record_setting.domain}'
                WHERE 
                    s.servertype_id = '{record_setting.servertype}'
            """
            )
        sql += " UNION ALL ".join(sub_queries)
        sql += ")"

        return sql

    @staticmethod
    def get_content_expression(record_setting):
        if record_setting.source_value_special:
            attribute = Attribute.specials[record_setting.source_value_special]
            if attribute.type == 'inet':
                return f"host(s.{attribute.attribute_id})"
            else:
                return f"s.{attribute.attribute_id}"
        elif record_setting.source_value.type == "inet":
            return "host(tt.value)"
        elif record_setting.source_value.type == "relation":
            return "rs.hostname"
        else:
            return "tt.value"

    @staticmethod
    def get_attribute_join(record_setting):
        if record_setting.source_value_special:
            # the needed attribute is already in the server table
            attribute_join = ""
        elif record_setting.source_value.type == "relation":
            attribute_join = f"""
                JOIN server_relation_attribute ra
                    ON s.server_id = ra.server_id 
                    AND ra.attribute_id = '{record_setting.source_value}'
                JOIN server as rs on ra.value = rs.server_id    
                    """
        else:
            target_table = ServerAttribute.get_model(record_setting.source_value.type)._meta.db_table
            attribute_join = f"""
                JOIN {target_table} tt
                    ON s.server_id = tt.server_id 
                    AND tt.attribute_id = '{record_setting.source_value}'
                    """

        return attribute_join

    @classmethod
    def get_record_type_expression(cls, record_setting):
        if record_setting.record_type in ['A', 'AAAA']:
            # todo: magic okay here?
            return f"case family({cls.get_content_expression(record_setting)}::inet) when 4 then 'A'::text else 'AAAA'::text end"

        return f"'{record_setting.record_type}'"

    @classmethod
    def get_name_expression(cls, record_setting):
        if record_setting.record_type == 'PTR':
            content = cls.get_content_expression(record_setting)
            return f"public.ptr({content}::inet)"

        return 's.hostname'

    @classmethod
    def get_domain_expression(cls, record_setting):
        if record_setting.domain:
            return f"(SELECT hostname from server sd where server_id = domain.value)"
        elif record_setting.record_type == 'PTR':
            return "'ip6.arpa'"  # todo ipv4/6
        else:
            return 'get_last_two_parts(s.hostname)'
