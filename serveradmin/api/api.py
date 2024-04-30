from datetime import timedelta

from django.utils import timezone

from serveradmin.api.decorators import api_function
from serveradmin.api.models import Lock


@api_function(group='api')
def lock(identifier, seconds=60):
    """Mark identifier as in-use for n seconds

    Allow clients to mark resources with an identifier as in-use so that
    distributed clients can check whatever something is in use or not.

    :param identifier: A unique identifier (e.g. 10.0.0.1)
    :param seconds: seconds until the lock expires

    :return: True on success or seconds left if already in use
    """

    # Remove expired locks first
    Lock.objects.filter(until__lt=timezone.now()).delete()

    # Use hash sum because this has a constant length
    hash_sum = Lock.get_hash_sum(identifier)
    obj, created = Lock.objects.get_or_create(
        hash_sum=hash_sum, defaults={'duration': seconds, 'until': timezone.now() + timedelta(seconds=seconds)}
    )

    if created:
        return True

    return (obj.until - timezone.now()).seconds
