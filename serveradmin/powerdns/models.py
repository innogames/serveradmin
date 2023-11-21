from django.db import models, connection
from django.utils.translation import gettext_lazy as _

from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServerAttribute,
    ServertypeAttribute,
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
    )  # XXX: Make this choices: A, AAAA, SSHFP
    source_value = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, related_name="+"
    )
    domain = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, related_name="+"
    )  # Restrict to relatation attribute

    def __str__(self):
        return f"{self.servertype} => {self.record_type}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # select hostname as name, 'AAAA' as type, intern_ip as content  from server where servertype_id = 'vm';
        # XXX:
        # - Avoid executing this for all settings
        # - Escape parameters injected
        sql = "CREATE OR REPLACE VIEW records (name, type, content) AS ("

        sub_queries = []
        for record_setting in RecordSetting.objects.all():
            target_table = ServerAttribute.get_model(record_setting.source_value.type)._meta.db_table

            sub_queries.append(
                f"""
                SELECT 
                    hostname as name,
                    '{record_setting.record_type}' as type,
                    CASE tt.value host(tt.value) as content                    
                FROM 
                    server s, {target_table} tt
                WHERE 
                    servertype_id = '{record_setting.servertype}' AND
                    s.server_id = tt.server_id AND
                    tt.attribute_id = '{record_setting.source_value}'
            """
            )
        sql += " UNION ALL ".join(sub_queries)
        sql += ")"

        with connection.cursor() as cursor:
            cursor.execute(sql)


# @receiver(post_save, sender=RecordSetting)
# def update_record_setting(sender, instance, **kwargs):
#    print(instance)
