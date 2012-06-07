from adminapi.dataset.base import MultiAttr
from adminapi.utils import IP

def json_encode_extra(obj):
    if isinstance(obj, MultiAttr):
        return list(obj._proxied_set)
    if isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, IP):
        return obj.ip
    raise TypeError()
