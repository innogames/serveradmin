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
                parsed_args.push({
                    'token': 'func',
                    'value': args.substring(string_start, i)
                });
                call_depth++;
                state = 'start';
            } else if (args[i] == ')') {
                parsed_args.push({
                    'token': 'str',
                    'value': args.substring(string_start, i)
                });
                parsed_args.push({
                    'token': 'funcenc'
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
        if (parsed_args[0]['token'] == 'str' && plen == 1) {
            hostname = parsed_args[0]['value'];
        }

        // Add attribute to autocomplete
        var prev_token = null;
        if (plen > 1) {
            prev_token = parsed_args[plen - 2]['token'];
        }
        if (prev_token != 'key' && parsed_args[plen - 1]['token'] == 'str') {
            var attr_name = parsed_args[plen - 1]['value'];
			var prefix = term.substring(0, term.length - attr_name.length);
            for (attr in attributes) {
                if (attr.substr(0, attr_name.length) == attr_name) {
                    autocomplete.push({
                        'label': 'Attr: ' + attr,
                        'value': prefix + attr
                    })
                }
            }
        }
    }
    if (hostname != null) {
        autocomplete_cb(autocomplete);
        var autocomplete_request = {'hostname': hostname};
        $.getJSON(shell_autocomplete_url, autocomplete_request, function(data) {
            var hostnames = data['autocomplete'];
            for (var i = 0; i < hostnames.length; i++) {
                autocomplete.push({
                    'label': 'Host: ' + hostnames[i],
                    'value': hostname
                })
            }
            autocomplete_cb(autocomplete);
        });
    } else {
        autocomplete_cb(autocomplete);
    }
}

$(function() {
    $('#shell_search').autocomplete({
        'source': function (request, response) {
            autocomplete_shell_search(request.term, response);
        }
    });
});
