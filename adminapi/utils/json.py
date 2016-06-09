def json_encode_extra(obj):
    if isinstance(obj, set):
        return list(obj)
    return str(obj)
