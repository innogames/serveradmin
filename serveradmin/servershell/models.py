from django.db import models


class Bookmark(models.Model):
    """Bookmark servershell queries to share"""

    name = models.CharField(max_length=80, unique=True)
    term = models.CharField(max_length=500)

    def __str__(self):
        return self.name
