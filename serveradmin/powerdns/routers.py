class PowerDNSRouter:
    """
    A router to control all database operations on models in the
    auth and contenttypes applications.
    """
    route_app_labels = {'powerdns'}

    def db_for_read(self, model, **hints):
        """
        Attempts to read powerdns models go to the pdns db.
        """
        if model._meta.app_label in self.route_app_labels:
            return 'pdns'
        return None

    def db_for_write(self, model, **hints):
        """
        Attempts to write powerdns models go to the pdns db.
        """
        if model._meta.app_label in self.route_app_labels:
            return 'pdns'
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Apply migrations to PowerDNS db only if target_db hint is set to pdns.

        :param db:
        :param app_label:
        :param model_name:
        :param hints:
        :return:
        """
        if 'target_db' in hints:
            return db == hints['target_db']

        return db != 'pdns'
