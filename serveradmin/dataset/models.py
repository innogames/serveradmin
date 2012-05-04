from django.db import models

class Attribute(models.Model):
    attrib_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    type = models.CharField(max_length=64)
    base = models.BooleanField(default=False)
    multi = models.BooleanField(default=False)
    modifier = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = 'attrib'

    def __unicode__(self):
        return self.name

class ServerType(models.Model):
    servertype_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)

    class Meta:
        db_table = 'servertype'

class ServerObject(models.Model):
    server_id = models.IntegerField(primary_key=True)
    hostname = models.CharField(max_length=64)
    intern_ip = models.PositiveIntegerField()
    comment = models.CharField(max_length=255, null=True, blank=True)
    servertype = models.ForeignKey(ServerType, null=True, blank=True)
    segment = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        db_table = 'admin_server'

class AttributeValue(models.Model):
    server = models.ForeignKey(ServerObject)
    attrib = models.ForeignKey(Attribute)
    value = models.CharField(max_length=1024)
