"""Serveradmin - adminapi

Copyright (c) 2019 InnoGames GmbH
"""

from adminapi.datatype import DatatypeError, str_to_datatype
from adminapi.filters import BaseFilter, Any, Regexp, filter_classes

_trigger_re_chars = ('.*', '.+', '[', ']', '|', '\\', '$', '^', '<')


def parse_query(term, hostname=None):  # NOQA: C901
    # Replace newlines with spaces to allow queries across multiple lines
    term = term.replace('\n', ' ').strip()

    parsed_args = parse_function_string(term, strict=True)
    if not parsed_args:
        return {}

    # If first token is not a key, we assume that a hostname is meant
    token, value = parsed_args[0]
    if token != 'key':
        if hostname:
            # We already parsed a hostname, so we don't expect another one
            raise DatatypeError("Garbled hostname: {0}".format(hostname))

        term_parts = term.split(None, 1)
        if len(term_parts) == 2:
            hostname_part, remaining_part = term_parts
            query_args = parse_query(remaining_part, hostname_part)
        else:
            hostname_part = term
            query_args = {}

        if any(x in hostname_part for x in _trigger_re_chars):
            hostname = Regexp(hostname_part)
        else:
            hostname = BaseFilter(hostname_part)

        if 'hostname' in query_args:
            query_args['hostname'] = Any(query_args['hostname'], hostname)
        else:
            query_args['hostname'] = hostname

        return query_args

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
            # Do not allow functions without preceding key
            # if they are on top level (e.g. call_depth = 0)
            if not stack or (call_depth == 0 and stack[-1][0] != 'key'):
                raise DatatypeError(
                    'Invalid term: top level function requires '
                    'preceding attribute'
                )
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
            fn_args.reverse()

            for filter_class in filter_classes:
                if filter_class.__name__.lower() == s_value.lower():
                    try:
                        instance = filter_class(*fn_args)
                    except TypeError:
                        raise DatatypeError(
                            'Invalid function args ' + filter_class.__name__
                        )
                    break
            else:
                raise DatatypeError('Invalid function ' + s_value)
            stack.append(('instance', instance))

        elif token == 'literal':
            # Do not allow literals without key or function context
            if not stack or (call_depth == 0 and stack[-1][0] != 'key'):
                raise DatatypeError(
                    'Invalid term: Top level literals are not '
                    'allowed when attributes are used'
                )
            if call_depth == 0:
                stack.append(('literal', BaseFilter(value)))
            else:
                stack.append(('literal', value))

    if stack and stack[0][0] == 'key':
        if len(stack) != 2:
            raise DatatypeError(
                'Invalid term: Attribute requires one argument'
            )
        query_args[stack[0][1]] = stack[1][1]

    return query_args


def parse_function_string(args, strict=True):   # NOQA C901
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
                        raise DatatypeError(
                            'Escape is not allowed at the end'
                        )
                if args[i + 1] == '\\':
                    string_buf.append('\\')
                    i += 2
                elif args[i + 1] == string_type:
                    string_buf.append(string_type)
                    i += 2
                else:
                    if strict:
                        raise DatatypeError('Invalid escape')
                    i += 1
            elif args[i] == string_type:
                parsed_args.append(('literal', args[string_start:i]))
                i += 1
                state = 'start'
            else:
                i += 1
        elif state == 'unquotedstring':
            if args[i] == ' ':
                parsed_args.append(
                    ('literal', str_to_datatype(args[string_start:i]))
                )
                state = 'start'
            elif args[i] == '(':
                if string_start != i:
                    parsed_args.append(('func', args[string_start:i]))
                    call_depth += 1
                    state = 'start'
            elif args[i] == ')' and call_depth != 0:
                if string_start != i:
                    parsed_args.append(
                        ('literal', str_to_datatype(args[string_start:i]))
                    )
                parsed_args.append(('endfunc', ''))
                call_depth -= 1
                state = 'start'
            # Do not parse key inside functions or of preceding token
            # was also a key
            elif args[i] == '=' and call_depth == 0 and (
                not parsed_args or parsed_args[-1][0] != 'key'
            ):
                parsed_args.append(('key', args[string_start:i]))
                state = 'start'
            i += 1
    if state == 'unquotedstring':
        parsed_args.append(('literal', str_to_datatype(args[string_start:])))
    elif state == 'string':
        if strict:
            raise DatatypeError('Unterminated string')
        else:
            parsed_args.append(('literal', args[string_start:]))

    return parsed_args
