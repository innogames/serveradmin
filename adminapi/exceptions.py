"""adminapi - Exceptions

Copyright (c) 2019 InnoGames GmbH
"""


class AdminapiException(Exception):
    """Adminapi exception parent class."""

    pass


class ConfigurationError(AdminapiException):
    """Missing or invalid configuration"""


class ApiError(AdminapiException):
    """An API request wasn't successful"""

    def __init__(self, *args, **kwargs):
        if 'status_code' in kwargs:
            self.status_code = kwargs.pop('status_code')
        else:
            self.status_code = 400
        super(Exception, self).__init__(*args, **kwargs)


class AuthenticationError(AdminapiException):
    """No suitable authentication credentials available"""

    pass


class DatasetError(AdminapiException):
    """Something went wrong within a dataset instance"""

    pass


class DatatypeError(AdminapiException):
    """A query or dataset attribute had the wrong value datatype"""

    pass


# XXX: Sub-class ValueError for backwards compatibility
class FilterValueError(DatatypeError, ValueError):
    """A filter value made no sense"""

    pass
