from django.db import models
from django.core.cache import cache

from serveradmin.common import dbfields

TYPE_CHOICES = (
        ('integer', 'Integer'),
        ('string', 'String'),
        ('ip', 'IPv4 address'),
        ('boolean', 'Boolean'),
        ('datetime', 'Datetime')
)

class Attribute(models.Model):
    special = None
    def __init__(self, *args, **kwargs):
        if 'special' in kwargs:
            self.special = kwargs[u'special']
            del kwargs[u'special']
        super(Attribute, self).__init__(*args, **kwargs)

    attrib_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64)
    type = models.CharField(max_length=64, choices=TYPE_CHOICES)
    base = models.BooleanField(default=False)
    multi = models.BooleanField(default=False)

    class Meta:
        db_table = 'attrib'

    def __unicode__(self):
        return self.name

class ServerType(models.Model):
    servertype_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, unique=True)

    def copy(self, new_name):
        if ServerType.objects.filter(name=new_name).count():
            raise Exception('Duplicate') # FIXME

        new_servertype = ServerType.objects.create(name=new_name)
        for attr in self.used_attributes.all():
            ServerTypeAttributes.objects.create(
                    servertype=new_servertype,
                    attrib=attr.attrib,
                    required=attr.required,
                    attrib_default=attr.attrib_default,
                    regex=attr.regex,
                    default_visible=attr.default_visible)
            cache.delete('dataset_lookups_version')


    class Meta:
        db_table = 'servertype'

    def __unicode__(self):
        return self.name

class ServerTypeAttributes(models.Model):
    servertype = models.ForeignKey(ServerType, related_name='used_attributes')
    attrib = models.ForeignKey(Attribute)
    required = models.BooleanField(default=False)
    attrib_default = models.CharField(max_length=255, null=True, blank=True)
    regex = models.CharField(max_length=255, null=True, blank=True)
    default_visible = models.BooleanField(default=False)

    class Meta:
        db_table = 'servertype_attributes'
        unique_together = (('servertype', 'attrib'), )

class ServerObject(models.Model):
    server_id = models.AutoField(primary_key=True)
    hostname = models.CharField(max_length=64)
    intern_ip = dbfields.IPv4Field()
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

class Segment(models.Model):
    segment = models.CharField(max_length=20, db_column='segment_id',
            primary_key=True)

    class Meta:
        db_table = 'segment'
