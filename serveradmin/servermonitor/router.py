class ServermonitorRouter(object):
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'servermonitor':
            return 'servermonitor'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'servermonitor':
            return 'servermonitor'
        return None

    def allow_syncdb(self, db, model):
        if db == 'servermonitor':
            return model._meta.app_label == 'servermonitor'
        elif model._meta.app_label == 'servermonitor':
            return False
        return None
