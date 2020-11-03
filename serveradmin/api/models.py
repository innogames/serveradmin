from django.db import models


class Lock(models.Model):
    class Meta:
        db_table = 'api_lock'

    hashsum = models.CharField(max_length=40, null=False, unique=True)
    until = models.DateTimeField()
    duration = models.PositiveIntegerField()
