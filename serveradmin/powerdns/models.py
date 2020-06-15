from time import time

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Domain(models.Model):
    """Model to access PowerDNS domains relation

    Purpose of this model is to be able to access the PowerDNS domain relation
    using the Django tools instead of writing raw SQLs
    """
    TYPE_CHOICES = [
        ('NATIVE', 'NATIVE'),
        ('MASTER', 'MASTER'),
    ]

    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255, null=False)
    type = models.CharField(max_length=6, null=False, choices=TYPE_CHOICES,
                            default=TYPE_CHOICES[0][0])

    class Meta:
        managed = False
        db_table = 'domains'


class Record(models.Model):
    """Model to access PowerDNS records relation

    Purpose of this model is to be able to access the PowerDNS records relation
    using the Django tools instead of writing raw SQLs
    """

    TTL_VALIDATORS = [MinValueValidator(300), MaxValueValidator(86400)]

    id = models.AutoField(primary_key=True)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, to_field='id')
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10)
    content = models.CharField(max_length=65535)
    ttl = models.IntegerField(validators=TTL_VALIDATORS, default=3600)
    change_date = models.IntegerField()
    disabled = models.BooleanField(default=False)
    record_id = models.IntegerField()
    object_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'records'

    def save(self, *args, **kwargs):
        self.change_date = int(time())
        super().save(*args, **kwargs)
