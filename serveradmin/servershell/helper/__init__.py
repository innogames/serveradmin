from serveradmin.serverdb.models import Attribute


def get_default_shown_attributes():
    """Get the default selection of shown attributes

    :return: list
    """

    shown_attributes = list(Attribute.specials.keys())
    shown_attributes.remove('object_id')
    shown_attributes.append('state')
    shown_attributes.sort()

    return shown_attributes
