from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q

from serveradmin.powerdns.sync.objects import RecordType
from serveradmin.powerdns.sync.utils import get_dns_zone
from serveradmin.powerdns.view_sql import ViewSQL
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
)


class Record(models.Model):
    """PowerDNS Record VIEW representation, so no real table!
    """

    object_ids = ArrayField(models.IntegerField(), primary_key=True)
    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=8, choices=[(name.name, name.name) for name in RecordType]
    )
    content = models.CharField(max_length=65535)
    domain = models.CharField(max_length=500)
    ttl = models.IntegerField()

    class Meta:
        managed = False
        db_table = "powerdns_records"

    def __str__(self):
        return f"{self.object_ids} {self.name} {self.type} {self.domain}"

    def get_zone(self):
        return get_dns_zone(self.domain)


class RecordSetting(models.Model):
    servertype = models.ForeignKey(Servertype, on_delete=models.CASCADE, blank=True, null=True)
    record_type = models.CharField(
        # Support all powerdns record types and an automagic A/AAAA record based on IP family
        max_length=8, choices=[("A_AAAA", "A/AAAA")] + [(name.name, name.name) for name in RecordType]
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
        blank=True, null=True,
        limit_choices_to={'type': 'relation'},
    )
    ttl = models.IntegerField(default=3600)

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
