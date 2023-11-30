import logging

from django.db import models, connection
from django.db.models import Q

from serveradmin.powerdns.http_client.objects import RecordType
from serveradmin.powerdns.view_sql import ViewSQL
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
)

logger = logging.getLogger(__name__)


# represents the view records
class Record(models.Model):
    """PowerDNS Record
    See https://doc.powerdns.com/authoritative/backends/generic-postgresql.html#default-schema
    """

    object_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=8, choices=[(name.name, name.name) for name in RecordType]
    )
    content = models.CharField(max_length=65535)
    domain = models.CharField(max_length=500)

    class Meta:
        managed = False
        db_table = "records"

    def __str__(self):
        return f"{self.object_id} {self.name} {self.type} {self.domain}"


class Domain(models.Model):
    """PowerDNS Domain
    Model to access domain in the PowerDNS db.
    See https://doc.powerdns.com/authoritative/backends/generic-postgresql.html#default-schema
    """
    TYPES = [
        ('MASTER', 'MASTER'),
        ('SLAVE', 'SLAVE'),
        ('NATIVE', 'NATIVE'),
    ]

    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255, null=False)
    type = models.CharField(max_length=6, null=False, choices=TYPES)

    class Meta:
        managed = False
        db_table = 'domains'


class RecordSetting(models.Model):
    servertype = models.ForeignKey(Servertype, on_delete=models.CASCADE)
    record_type = models.CharField(
        max_length=8, choices=[(name.name, name.name) for name in RecordType]
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
        Attribute, on_delete=models.CASCADE, related_name="+",
        blank=True, null=True
    )  # todo: Restrict to relatation attribute

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
            # todo if view schema is safe, remove it and only REPLACE VIEW
            cursor.execute('DROP VIEW IF EXISTS records')

            sql = ViewSQL.get_record_view_sql()
            cursor.execute(sql)
