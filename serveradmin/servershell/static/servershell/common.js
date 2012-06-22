function parse_function_string(args)
{
    var state = 'start';
    var args_len = args.length;
    var parsed_args = [];
    
    var i = 0;
    var call_depth = 0;
    
    var string_start, string_type, string_buf;
    
    while (i < args_len) {
        if (state == 'start') {
            if (args[i] == '"' || args[i] == "'") {
                state = 'string';
                string_start = i + 1;
                string_type = args[i];
                string_buf = [];
                i++;
            } else if (args[i] == ' ') {
                i++;
            } else {
                string_start = i;
                state = 'unquotedstring';
            }
        } else if (state == 'string') {
            if (args[i] == '\\') {
                if ((i + 1) == args_len) {
                    // Do nothing, because the function string is not
                    // finished yet.
                } else if (args[i + 1] == '\\') {
                    string_buf.push('\\');
                    i += 2;
                } else if (args[i + 1] == string_type) {
                    string_buf.push(string_type);
                    i += 2
                }
            } else if (args[i] == string_type) {
                parsed_args.push({
                    'token': 'str',
                    'value': args.substring(string_start, i)
                });
                i++;
                state = 'start';
            } else {
                i++;
            }
        } else if (state == 'unquotedstring') {
            if (args[i] == ' ') {
                parsed_args.push({
                    'token': 'str',
                    'value': args.substring(string_start, i)
                });
                state = 'start';
            } else if (args[i] == '(') {
                if (string_start != i) {
                    parsed_args.push({
                        'token': 'func',
                        'value': args.substring(string_start, i)
                    });
                    call_depth++;
                    state = 'start';
                }
            } else if (args[i] == ')') {
                if (string_start != i) {
                    parsed_args.push({
                        'token': 'str',
                        'value': args.substring(string_start, i)
                    });
                }
                parsed_args.push({
                    'token': 'endfunc'
                });
                call_depth--;
                state = 'start';
            } else if (args[i] == '=') {
                parsed_args.push({
                    'token': 'key',
                    'value': args.substring(string_start, i)
                });
                state = 'start';
            }
            i++;
        }
    }
    if (state == 'unquotedstring' || state == 'string') {
        parsed_args.push({
            'token': 'str',
            'value': args.substring(string_start, i)
        });
    }
    return parsed_args;
}


function is_digit(x)
{
    return x == '0' || x == '1' || x == '2' || x == '3' || x == '4' ||
        x == '5' || x == '6' || x == '7' || x == '8' || x == '9';
}

function startswith(x, y)
{
    return x.substring(0, y.length) == y;
}

function _autocomplete_attr(term, parsed_args, autocomplete_list, suffix)
{
    if (typeof(suffix) == 'undefined') {
        suffix = '';
    }
    var attr_name = parsed_args[parsed_args.length - 1]['value'].toLowerCase();
    var prefix = term.substring(0, term.length - attr_name.length);
    for (attr in available_attributes) {
        if (attr.substr(0, attr_name.length).toLowerCase() == attr_name) {
            autocomplete_list.push({
                'label': 'Attr: ' + attr,
                'value': prefix + attr + suffix
            })
        }
    }
}
