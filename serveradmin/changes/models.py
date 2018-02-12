import json

from django.db import models
from django.utils.timezone import now
from django.contrib.auth.models import User

from serveradmin.apps.models import Application


class Commit(models.Model):
    change_on = models.DateTimeField(default=now, db_index=True)
    user = models.ForeignKey(
        User,
        null=True,
        on_delete=models.PROTECT,
    )
    app = models.ForeignKey(
        Application,
        null=True,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return str(self.change_on)


class Addition(models.Model):
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE)
    server_id = models.IntegerField(db_index=True)
    attributes_json = models.TextField()

    class Meta:
        unique_together = [['commit', 'server_id']]

    @property
    def attributes(self):
        return json.loads(self.attributes_json)

    def __str__(self):
        return '{0}: {1}'.format(str(self.commit), self.server_id)


class Modification(models.Model):
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE)
    server_id = models.IntegerField(db_index=True)
    updates_json = models.TextField()

    class Meta:
        unique_together = [['commit', 'server_id']]

    @property
    def updates(self):
        return json.loads(self.updates_json)

    def __str__(self):
        return '{0}: {1}'.format(str(self.commit), self.server_id)


class Deletion(models.Model):
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE)
    server_id = models.IntegerField(db_index=True)
    attributes_json = models.TextField()

    class Meta:
        unique_together = [['commit', 'server_id']]

    @property
    def attributes(self):
        return json.loads(self.attributes_json)

    def __str__(self):
        return '{0}: {1}'.format(str(self.commit), self.server_id)
