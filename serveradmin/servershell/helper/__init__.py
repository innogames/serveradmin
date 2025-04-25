from serveradmin.serverdb.models import Attribute, ServertypeAttribute


def get_default_shown_attributes():
    """Get the default selection of shown attributes

    :return: list
    """

    shown_attributes = list(Attribute.specials.keys())
    shown_attributes.remove('object_id')
    shown_attributes.remove('intern_ip')
    default_attributes = ServertypeAttribute.objects.filter(
        default_visible=True).only('attribute_id').order_by(
        'attribute_id').distinct('attribute_id')
    shown_attributes.extend([attr.attribute_id for attr in default_attributes])
    shown_attributes.sort()

    return shown_attributes
