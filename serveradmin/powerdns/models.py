import logging

from django.db import models, connection
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServerAttribute,
)


class RecordSetting(models.Model):
    class RecordType(models.TextChoices):
        A = "A", _("A")
        AAAA = "AAAA", _("AAAA")
        SSHFP = "SSHFP", _("SSHFP")
        TXT = "TXT", _("TXT")
        MX = "MX", _("MX")

    servertype = models.ForeignKey(Servertype, on_delete=models.CASCADE)
    record_type = models.CharField(
        max_length=8, choices=RecordType.choices
    )

    source_value = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, related_name="+", null=True,
        blank=True
    )
    source_value_special = models.CharField(
        max_length=30,
        choices=[(name, name) for name in Attribute.specials.keys()],
        null=True,
        blank=True,
    )

    domain = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, related_name="+"
    )  # Restrict to relatation attribute

    class Meta:
        constraints = [
            models.CheckConstraint(
                # todo xor on NULL
                check=Q(source_value=None) | Q(source_value_special=None),
                name="only_one_source_value",
            ),
        ]

    def __str__(self):
        display_name = f"{self.servertype} => {self.record_type}"
        if self.source_value:
            display_name += f" ({self.source_value})"
        else:
            display_name += f" ({self.source_value_special})"

        return display_name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        with connection.cursor() as cursor:
            sql = self.get_record_view_sql()
            cursor.execute(sql)

    # XXX: Put all methods to SQL module
    def get_record_view_sql(self):
        # XXX:
        # - Avoid executing this for all settings
        # - Escape parameters injected
        sql = "CREATE OR REPLACE VIEW records (name, type, content) AS ("
        sub_queries = []
        for record_setting in RecordSetting.objects.all():
            attribute_join = self.get_attribute_join(record_setting)
            content_expression = self.get_content_expression(record_setting)

            sub_queries.append(
                f"""
                SELECT 
                    hostname as name,
                    '{record_setting.record_type}' as type,
                    {content_expression} as content,
                    (SELECT hostname from server where server_id = domain.value) as domain_id            
                FROM 
                    server s
                {attribute_join}
                LEFT JOIN server_relation_attribute domain
                    ON s.server_id = domain.server_id 
                    AND domain.attribute_id = '{record_setting.domain}'
                WHERE 
                    servertype_id = '{record_setting.servertype}'
            """
            )
        sql += " UNION ALL ".join(sub_queries)
        sql += ")"

        return sql

    def get_attribute_join(self, record_setting):
        if record_setting.source_value_special:
            attribute_join = ""
        else:
            target_table = ServerAttribute.get_model(record_setting.source_value.type)._meta.db_table
            attribute_join = f"""
                JOIN {target_table} tt
                    ON s.server_id = tt.server_id 
                    AND tt.attribute_id = '{record_setting.source_value}'
                    """
        return attribute_join

    def get_content_expression(self, record_setting):
        if record_setting.source_value_special:
            attribute = Attribute.specials[record_setting.source_value_special]
            if attribute.type == 'inet':
                return f"host(s.{attribute.attribute_id})"
            else:
                return f"s.{attribute.attribute_id}::text"
        elif record_setting.source_value.type == "inet":
            return "host(tt.value)"
        else:
            return "tt.value::text"
