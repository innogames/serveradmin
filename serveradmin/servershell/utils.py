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
                parsed_args.append(('func', args[string_start:i]))
                call_depth += 1
                state = 'start'
            elif args[i] in (')', ']') and call_depth != 0:
                parsed_args.append(('str', args[string_start:i]))
                parsed_args.append(('funcend', ''))
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
