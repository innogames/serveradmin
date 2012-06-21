var filter_functions = ['Regexp', 'Any']

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
            _autocomplete_attr(term, parsed_args, autocomplete);
        }
        
        // Add filter functions to autocomplete
        if (prev_token == 'key' && parsed_args[plen -1]['token'] == 'str' && call_depth == 0) {
            for (var i = 0; i < filter_functions.length; i++) {
                var fn = filter_functions[i];
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
            for (var i = 0; i < filter_functions.length; i++) {
                var fn = filter_functions[i];
                autocomplete.push({
                    'label': 'Filter: ' + fn,
                    'value': term + fn + '('
                });
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
                    'value': hostnames[i]
                })
            }
            autocomplete_cb(autocomplete);
        });
    } else {
        autocomplete_cb(autocomplete);
    }
}

function build_server_table(servers, attributes, offset)
{
    if (typeof(offset) == 'undefined') {
        offset = 0;
    }
    // Build table header
    var table = $('<table class="valign-middle"></table>');
    var header_tr = $('<tr><th></th><th>No</th></tr>');
    for (var i = 0; i < attributes.length; i++) {
        header_tr.append($('<th></th>').text(attributes[i]));
    }
    table.append(header_tr);
    
    // Build server list for table
    var server_list = []
    for (server in servers) {
        servers[server]['object_id'] = server;
        server_list.push(servers[server]);
    }
    server_list.sort(function(a, b) {
        return a['hostname'] > b['hostname'] ? 1 : -1;
    });
    
    
    // Fill table
    search['no_mapping'] = {};
    for (var i = 0; i < server_list.length; i++) {
        var server = server_list[i];
        var row_class = i & 1 ? 'row_a' : 'row_b';
        var row = $('<tr class="' + row_class + '"></tr>');
        var check = $('<input type="checkbox" name="server"></input>')
            .attr('value', server['object_id'])
            .attr('id', 'server_' + server['object_id']);
        row.append($('<td></td>').append(check));
        row.append($('<td></td>').text(offset + i + 1));
        for (var j = 0; j < attributes.length; j++) {
            value = server[attributes[j]];
            var attr_obj = available_attributes[attributes[j]];
            if (attr_obj['type'] == 'ip') {
                value = new IP(value).as_ip();
            } else if (attr_obj['multi']) {
                value = value.join(', ');
            }
            row.append($('<td></td>').text(value));
        }
        table.append(row);
        search['no_mapping'][i + 1] = server;
    }
    var num_pages = Math.ceil(search['num_servers'] / search['per_page']);
    var heading = '<h3>Results (' + search['num_servers'] + ' servers, ';
    heading += 'page ' + search['page'] + '/' + num_pages + ')</h3>';
    $('#shell_servers').empty().append(heading).append(table);
}

var search = {
    'shown_attributes': ['hostname', 'intern_ip', 'servertype'],
    'servers': {},
    'num_servers': 0,
    'page': 1,
    'per_page': 25,
    'no_mapping': {}
};

function render_server_table() {
    var offset = (search['page'] - 1) * search['per_page'];
    build_server_table(search['servers'], search['shown_attributes'], offset);
}

function handle_command(command) {
    if (command == 'n' || command == 'next') {
        search['page']++;
        execute_search($('#shell_search').val());
    } else if (command == 'p' || command == 'previous') {
        search['page']--;
        if (search['page'] < 1) {
            search['page'] = 1;
        }
        execute_search($('#shell_search').val());
    } else if (command == 'all') {
        $('input[name="server"]').each(function(index) {
            this.checked = true;
        });
        return '';
    } else if (command == 'none') {
        $('input[name="server"]').each(function(index) {
            this.checked = false;
        });
        return '';
    } else if (is_digit(command[0])) {
        var mark_nos = [];
        var ranges = command.split(',');
        for(var i = 0; i < ranges.length; i++) {
            var range = ranges[i].split('-');
            if (range.length == 1) {
                mark_nos.push(parseInt($.trim(range[0]), 10));
            } else if (range.length == 2) {
                var first = parseInt($.trim(range[0]), 10);
                var second = parseInt($.trim(range[1]), 10);
                if (first < 0 || second < 0) {
                    continue;
                }
                for(var j = first; j <= second; j++) {
                    mark_nos.push(j);
                }
            }

        }
        for(var i = 0; i < mark_nos.length; i++) {
            var server = search['no_mapping'][mark_nos[i]];
            if (typeof(server) != 'undefined') {
                var check = $('#server_' + server['object_id'])[0];
                check.checked = !check.checked;
            }
        }
    } else {
        var parsed_args = parse_function_string(command);
        if (parsed_args[0]['token'] != 'str') {
            return;
        }
        var command_name = parsed_args[0]['value'];
        if (command_name == 'attr') {
            for(var i = 1; i < parsed_args.length; i++) {
                if (parsed_args[i]['token'] == 'str') {
                    var attr_name = parsed_args[i]['value'];
                    var index = search['shown_attributes'].indexOf(attr_name);
                    if (index == -1) {
                        search['shown_attributes'].push(attr_name);
                    } else {
                        search['shown_attributes'].remove(index);
                    }
                }
            }
            render_server_table();
            return '';
        }
    }
}

function execute_search(term) {
    var offset = (search['page'] - 1) * search['per_page'];
    var search_request = {
        'term': term,
        'offset': offset,
        'limit': search['per_page'],
        'no_mapping': {}
    };
    $.getJSON(shell_results_url, search_request, function(data) {
        if (data['status'] != 'success') {
            $('#shell_understood').text('Error: ' + data['message']);
            return;
        }
        search['servers'] = data['servers'];
        search['num_servers'] = data['num_servers'];
        $('#shell_understood').text(data['understood']);
        render_server_table();
        $('#shell_command').focus();
    });
}

function autocomplete_shell_command(term, autocomplete_cb)
{
    var autocomplete = [];
    var parsed_args = parse_function_string(term);
    var plen = parsed_args.length;

    var commands = {
        'attr': 'Show an attribute (e.g. "attr webserver")',
        'all': 'Mark all servers on this page',
        'none': 'Unmark all servers on this page',
        'multiadd': 'Add a value to a multi attribute (e.g. "multiadd webservers=nginx")',
        'multidel': 'Delete a value from a multi attribute (e.g. multidel webserver=apache)',
        'delete': 'Delete servers',
        'set': 'Set an attribute (e.g. "set os=wheezy")' 
    };
    
    if (plen == 1 && parsed_args[0]['token'] == 'str') {
        var command = parsed_args[0]['value'].toLowerCase();
        for (command_name in commands) {
            if (command_name.substring(0, command.length) == command) {
                var description = commands[command_name];
                autocomplete.push({
                    'label': command_name + ': ' + description,
                    'value': command_name + ' '
                });
            }
        }
        autocomplete_cb(autocomplete);
        return;
    }

    if (plen == 0 || parsed_args[0]['token'] != 'str') {
        return;
    }
    var command = parsed_args[0]['value'];
    
    if (command == 'attr') {
        if (parsed_args[plen -1]['token'] == 'str') {
            _autocomplete_attr(term, parsed_args, autocomplete); 
        }
    }
    autocomplete_cb(autocomplete);
}

function _autocomplete_attr(term, parsed_args, autocomplete_list)
{
    var attr_name = parsed_args[parsed_args.length - 1]['value'].toLowerCase();
    var prefix = term.substring(0, term.length - attr_name.length);
    for (attr in available_attributes) {
        if (attr.substr(0, attr_name.length).toLowerCase() == attr_name) {
            autocomplete_list.push({
                'label': 'Attr: ' + attr,
                'value': prefix + attr
            })
        }
    }
}

function is_digit(x) {
    return x == '0' || x == '1' || x == '2' || x == '3' || x == '4' ||
        x == '5' || x == '6' || x == '7' || x == '8' || x == '9';
}

$(function() {
    $('#shell_search_form').submit(function(ev) {
        search['page'] = 1;
        ev.stopPropagation();
        execute_search($('#shell_search').val());
        return false;
    });
    $('#shell_search').autocomplete({
        'source': function (request, response) {
            autocomplete_shell_search(request.term, response);
        }
    });

    $('#shell_search').bind('change keydown', function(ev) {
        $('#shell_understood').text('Nothing yet');
        $('#shell_servers').empty()
    });

    if ($('#shell_search').val() != '') {
        search['page'] = 1;
        execute_search($('#shell_search').val());
    }
    
    $('#shell_command_form').submit(function(ev) {
        ev.stopPropagation();
        var new_command = handle_command($.trim($('#shell_command').val()));
        if (typeof(new_command) != 'undefined' && new_command != null) {
            $('#shell_command').val(new_command);
        }
        return false;
    });

    $('#shell_command').autocomplete({
        'source': function (request, response) {
            autocomplete_shell_command($.trim(request.term), response);
        }
    });

    $('#shell_command').val('');
});
