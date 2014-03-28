from django.core.management.base import NoArgsCommand
from serveradmin.serverdb.models import Attribute, ServerTypeAttributes

class Command(NoArgsCommand):
    help = 'Set correct regexp for sshaccess for all servertypes'
    
    def handle_noargs(self, **options):
        ssh_regexp = r'^[a-z][a-z0-9._-]{1,30}:[a-z][a-z0-9._-]{1,30}$'
        self.add_validation('ssh_users', ssh_regexp)
        self.add_validation('ssh_groups', ssh_regexp)

    def add_validation(self, attr_name, regex):
        attr = Attribute.objects.get(name=attr_name)
        ServerTypeAttributes.objects.filter(attrib=attr).update(regex=regex)
