from django.conf import settings


class PowerdnsRouter:
    """Route all database operations of PowerDNS to a dedicated DB"""

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'powerdns':
            return 'powerdns'

        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'powerdns':
            return 'powerdns'

        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'powerdns':
            if app_label == 'powerdns':
                return True
            else:
                return False
        else:
            if app_label == 'powerdns':
                return False

        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None
