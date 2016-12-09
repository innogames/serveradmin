def log2(x):
    i = -1
    while x:
        x >>= 1
        i += 1
    return i


def format_obj(obj):
    if isinstance(obj, str):
        return obj
    if hasattr(obj, '__iter__'):
        return ', '.join(sorted(str(x) for x in obj))
    return str(obj)
