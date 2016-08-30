def json_encode_extra(obj):

    # Proxied sets are used by MultiAttr
    if hasattr(obj, '_proxied_set'):
        return list(obj._proxied_set)

    if isinstance(obj, set):
        return list(obj)

    return str(obj)
