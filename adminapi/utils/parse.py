def parse_function_string(args, strict=True):
    state = 'start'
    args_len = len(args)
    parsed_args = []
    
    i = 0
    call_depth = 0
    while i < args_len:
        if state == 'start':
            if args[i] in ('"', "'"):
                state = 'string'
                string_start = i + 1
                string_type = args[i]
                string_buf = []
                i += 1
            elif args[i] == ' ':
                i += 1
            else:
                string_start = i
                state = 'unquotedstring'
        elif state == 'string':
            if args[i] == '\\':
                if i == args_len - 1:
                    if strict:
                        raise ValueError('Escape is not allowed at the end')
                if args[i+1] == '\\':
                    string_buf.append('\\')
                    i += 2
                elif args[i+1] == string_type:
                    string_buf.append(string_type)
                    i += 2
                else:
                    if strict:
                        raise ValueError('Invalid escape')
                    i += 1
            elif args[i] == string_type:
                parsed_args.append(('str', args[string_start:i]))
                i += 1
                state = 'start'
            else:
                i += 1
        elif state == 'unquotedstring':
            if args[i] == ' ':
                parsed_args.append(('str', args[string_start:i]))
                state = 'start'
            elif args[i] in ('(', '['):
                if string_start != i:
                    parsed_args.append(('func', args[string_start:i]))
                    call_depth += 1
                    state = 'start'
            elif args[i] in (')', ']') and call_depth != 0:
                if string_start != i:
                    parsed_args.append(('str', args[string_start:i]))
                parsed_args.append(('endfunc', ''))
                call_depth -= 1
                state = 'start'
            elif args[i] == '=':
                parsed_args.append(('key', args[string_start:i]))
                state = 'start'
            i += 1
    if state == 'unquotedstring':
        parsed_args.append(('str', args[string_start:]))
    elif state == 'string':
        if strict:
            raise ValueError('Unterminated string')
        else:
            parsed_args.append(('str', args[string_start:]))
    
    return parsed_args

def parse_query(term, filter_classes):
    parsed_args = parse_function_string(term, strict=True)
    if not parsed_args:
        raise ValueError(u'Empty query')

    # If first token is not a key, we assume that a hostname is meant
    token, value = parsed_args[0]
    if token != 'key':
        if any(x in term for x in ('.*', '.+', '[', ']', '|', '\\', '$', '^')):
            hostname = filter_classes['regexp'](term)
        else:
            hostname = term
        return {u'hostname': hostname}
    
    # Otherwise just parse all attributes
    query_args = {}
    stack = []
    call_depth = 0
    for arg in parsed_args:
        token, value = arg
        if token == 'key':
            if stack:
                query_args[stack[0][1]] = stack[1][1]
                stack = []
            stack.append(arg)
        elif token == 'func':
            call_depth += 1
            stack.append(arg)
        elif token == 'endfunc':
            call_depth -= 1
            fn_args = []
            while True:
                s_token, s_value = stack.pop()
                if s_token == 'func':
                    break
                else:
                    fn_args.append(s_value)
            fn_name = s_value.lower()
            fn_args.reverse()
            try:
                instance = filter_classes[fn_name](*fn_args)
            except KeyError:
                raise ValueError('Invalid function ' + fn_name)
            except TypeError:
                raise ValueError('Invalid function args ' + fn_name)
            stack.append(('instance', instance))
        elif token == 'str':
            # Do not allow strings without key or function context
            if not stack or (call_depth == 0 and stack[-1][0] != 'key'):
                raise ValueError('Invalid term')
            stack.append(arg)

    if stack and stack[0][0] == 'key':
        query_args[stack[0][1]] = stack[1][1]
    return query_args
