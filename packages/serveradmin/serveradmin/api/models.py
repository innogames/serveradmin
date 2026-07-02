import hashlib

from django.db import models


class Lock(models.Model):
    class Meta:
        db_table = 'api_lock'

    hash_sum = models.CharField(max_length=40, null=False, unique=True)
    until = models.DateTimeField(null=True)
    duration = models.PositiveIntegerField(null=True)

    @classmethod
    def get_hash_sum(cls, identifier: str):
        """Get Hash sum for identifier"""

        return hashlib.sha1(str(identifier).encode()).hexdigest()
