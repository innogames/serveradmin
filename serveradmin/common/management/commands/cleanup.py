from django.core.management.base import NoArgsCommand
from serveradmin.common.signals import cleanup

class Command(NoArgsCommand):
    help = 'Cleanup some things'
    
    def handle_noargs(self, **options):
        cleanup.send(sender=self)
