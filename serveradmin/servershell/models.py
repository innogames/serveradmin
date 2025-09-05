from django.contrib.auth.models import User
from django.db import models

from serveradmin.serverdb.models import Attribute


class AttributeSelection(models.Model):
    name = models.CharField(max_length=80, unique=True)
    attributes = models.ManyToManyField(Attribute)

    def __str__(self):
        return self.name