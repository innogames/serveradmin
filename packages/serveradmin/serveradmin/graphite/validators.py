from collections import Counter
from urllib.parse import parse_qsl

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


def validate_unique_uri_parameters(query_string: str):
    """Validate no key in Query string appears more than once

    :param query_string:
    :return:
    """

    errors = []
    counter = Counter([param[0] for param in parse_qsl(query_string)])

    for key, occurences in counter.most_common():
        if occurences > 1:
            errors.append(ValidationError(
                _('Parameter "%(key)s" must only appear once!'),
                params={'key': key}))

    if errors:
        raise ValidationError(*errors)
