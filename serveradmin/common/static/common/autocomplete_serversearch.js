function startswith(x, y)
{
    return x.substring(0, y.length) == y;
}

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
                    i++;
                } else if (args[i + 1] == '\\') {
                    string_buf.push('\\');
                    i += 2;
                } else if (args[i + 1] == string_type) {
                    string_buf.push(string_type);
                    i += 2
                } else {
                    i++;
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

var _autocomplete_state = {'xhr': null};
function autocomplete_shell_search(term, autocomplete_cb)
{
    var parsed_args = parse_function_string(term);
    var autocomplete = [];
    var plen = parsed_args.length;
    if (plen == 0) {
        autocomplete_cb(autocomplete);
        return;
    } else {
        var hostname = null;
        // Add hostname to autocomplete
        if (parsed_args[0]['token'] != 'key') {
            hostname = term;
        }
        
        // Check call depth
        var call_depth = 0;
        for(var i = 0; i < plen; i++) {
            if (parsed_args[i]['token'] == 'func') {
                call_depth++;
            } else if(parsed_args[i]['token'] == 'endfunc') {
                call_depth--;
            }
        }
        
        // Add attribute to autocomplete
        var prev_token = null;
        if (plen > 1) {
            prev_token = parsed_args[plen - 2]['token'];
        }
        if (prev_token != 'key' && parsed_args[plen - 1]['token'] == 'str' && call_depth == 0) {
            _autocomplete_attr(term, parsed_args, autocomplete, '=');
        }
        
        // Add filter functions to autocomplete
        if (prev_token == 'key' && parsed_args[plen -1]['token'] == 'str' && call_depth == 0) {
            for (fn_name in filter_functions) {
                var fn = filter_functions[fn_name];
                var filter_name = parsed_args[plen - 1]['value'].toLowerCase();
                var prefix = term.substring(0, term.length - filter_name.length);
                if (fn.substr(0, filter_name.length).toLowerCase() == filter_name) {
                    autocomplete.push({
                        'label': 'Filter: ' + fn,
                        'value': prefix + fn + '('
                    });
                }
            }
        } else if (parsed_args[plen -1]['token'] == 'key') {
            for (fn_name in filter_functions) {
                var fn = filter_functions[fn_name];
                autocomplete.push({
                    'label': 'Filter: ' + fn,
                    'value': term + fn + '('
                });
            }
        }
    }
    if (hostname != null) {
        // Selecting an item while the request is running will result in
        // weird behavior (no item selected after request is finished)
        //autocomplete_cb(autocomplete);
        if (_autocomplete_state['xhr'] != null) {
            _autocomplete_state['xhr'].abort();
        }
        var autocomplete_request = {'hostname': hostname};
        var xhr = $.getJSON(shell_autocomplete_url, autocomplete_request, function(data) {
            _autocomplete_state['xhr'] = null;
            var hostnames = data['autocomplete'];
            for (var i = 0; i < hostnames.length; i++) {
                autocomplete.push({
                    'label': 'Host: ' + hostnames[i],
                    'value': hostnames[i]
                })
            }
            autocomplete_cb(autocomplete);
        });
        _autocomplete_state['xhr'] = xhr;
    } else {
        autocomplete_cb(autocomplete);
    }
}

function _autocomplete_attr(term, parsed_args, autocomplete_list, suffix, filter_fn)
{
    if (typeof(suffix) == 'undefined') {
        suffix = '';
    }
    if (typeof(filter_fn) == 'undefined') {
        filter_fn = function(attr) { return true; }
    }
    var attr_name = parsed_args[parsed_args.length - 1]['value'].toLowerCase();
    var prefix = term.substring(0, term.length - attr_name.length);
    for (attr in available_attributes) {
        if (attr.substr(0, attr_name.length).toLowerCase() == attr_name && filter_fn(attr)) {
            autocomplete_list.push({
                'label': 'Attr: ' + attr,
                'value': prefix + attr + suffix
            })
        }
    }
}
