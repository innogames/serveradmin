def build_function_description(fn):
    code = fn.func_code
    is_args = code.co_flags & 0x04
    is_kwargs = code.co_flags & 0x08

    if is_kwargs and is_args:
        extra_args = 2
    elif is_kwargs or is_args:
        extra_args = 1
    else:
        extra_args = 0
    
    arguments = list(code.co_varnames[:code.co_argcount + extra_args])
    
    if is_kwargs:
        arguments[-1] = '**' + arguments[-1]
        if is_args:
            arguments[-2] = '*' + arguments[-2]
    elif is_args:
        arguments[-1] = '*' + arguments[-1]
    
    defaults = fn.func_defaults if fn.func_defaults else []
    for i, default_value in enumerate(reversed(defaults)):
        idx = code.co_argcount - i - 1
        arguments[idx] = '{0}={1!r}'.format(arguments[idx], default_value)

    return '{0}({1})'.format(fn.func_name, ', '.join(arguments))
