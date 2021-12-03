from django.db import models


class Domain(models.Model):
    """PowerDNS Domain

    Model to access domain in the PowerDNS db.
    """
    TYPES = [
        ('MASTER', 'MASTER'),
        ('SLAVE', 'SLAVE'),
        ('NATIVE', 'NATIVE'),
    ]

    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255, null=False)
    master = models.CharField(max_length=128, default=None)
    type = models.CharField(max_length=6, null=False, choices=TYPES)

    class Meta:
        managed = False
        db_table = 'domains'
