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

class ServerTypeAttributes(models.Model):
    servertype = models.ForeignKey(ServerType, primary_key=True)
    attrib = models.ForeignKey(Attribute, primary_key=True)
    required = models.BooleanField(default=False)
    attrib_default = models.CharField(max_length=255, null=True, blank=True)
    regex = models.CharField(max_length=255)
    default_visible = models.BooleanField(default=False)

    class Meta:
        db_table = 'servertype_attributes'

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

    class Meta:
        db_table = 'attrib_values'

class ServerObjectCache(models.Model):
    server = models.ForeignKey(ServerObject, null=True, blank=True)
    repr_hash = models.BigIntegerField()

    class Meta:
        unique_together = (('server', 'repr_hash'))
