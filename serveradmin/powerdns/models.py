from django.db import models
from django.db.models import Q

from serveradmin.powerdns.sync.objects import RecordType
from serveradmin.powerdns.view_sql import ViewSQL
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
)


class Record(models.Model):
    """PowerDNS Record VIEW representation, so no real table!
    """

    object_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=8, choices=[(name.name, name.name) for name in RecordType]
    )
    content = models.CharField(max_length=65535)
    domain = models.CharField(max_length=500)
    zone = models.CharField(max_length=500)

    class Meta:
        managed = False
        db_table = "records"

    def __str__(self):
        return f"{self.object_id} {self.name} {self.type} {self.domain}"


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
                # todo native xor seems to be not in django 3.2, please recheck
                check=(Q(source_value__isnull=False) & Q(source_value_special__isnull=True)) |
                      (Q(source_value__isnull=True) & Q(source_value_special__isnull=False)),
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

    # todo maybe use signals instead of overriding save/delete?
    def delete(self, *args, **kwargs):
        super().save(*args, **kwargs)

        ViewSQL.update_view_schema()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        ViewSQL.update_view_schema()
