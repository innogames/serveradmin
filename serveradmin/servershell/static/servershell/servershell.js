var search = {
    'shown_attributes': ['hostname', 'intern_ip', 'servertype'],
    'servers': {},
    'num_servers': 0,
    'page': 1,
    'per_page': 25,
    'order_by': null,
    'order_dir': 'asc',
    'no_mapping': {}
};

var commit = {
    'deleted': [],
    'changed': {}
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

function execute_search(term)
{
    var offset = (search['page'] - 1) * search['per_page'];
    var search_request = {
        'term': term,
        'offset': offset,
        'limit': search['per_page'],
        'no_mapping': {}
    };
    if (search['order_by'] != null) {
        search_request['order_by'] = search['order_by'];
        search_request['order_dir'] = search['order_dir'];
    }
    $.getJSON(shell_results_url, search_request, function(data) {
        if (data['status'] != 'success') {
            var error = $('<span class="error"></span>').text(data['message']);
            $('#shell_understood').empty().append(error);
            return;
        }
        search['servers'] = data['servers'];
        search['num_servers'] = data['num_servers'];
        search['shown_attributes'] = data['shown_attributes'];
        $('#shell_understood').text(data['understood']);
        render_server_table();
        $('#shell_command').focus();
    });
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
        var sort_attr;
        if (typeof(search['order_by']) == 'string') {
            sort_attr = search['order_by'];
        } else {
            sort_attr = 'hostname';
        }
        var x = a[sort_attr];
        var y = b[sort_attr];
        
        if (available_attributes[sort_attr]['multi']) {
            x = array_min(x);
            y = array_min(y);
        }

        if (search['order_dir'] == 'desc') {
            return x > y ? -1 : 1;
        } else {
            return x > y ? 1 : -1;
        }
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
            if (typeof(value) == 'undefined') {
                value = '';
            } else if (attr_obj['multi']) {
                value.sort();
                if (attr_obj['type'] == 'ip') {
                    value = value.map(function(x) {
                        return new IP(x).as_ip();
                    });
                }
                value = value.join(', ');
            } else if (attr_obj['type'] == 'ip') {
                value = new IP(value).as_ip();
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

function render_server_table()
{
    var offset = (search['page'] - 1) * search['per_page'];
    build_server_table(search['servers'], search['shown_attributes'], offset);
}

function autocomplete_shell_command(term, autocomplete_cb)
{
    var autocomplete = [];
    var parsed_args = parse_function_string(term);
    var plen = parsed_args.length;

    var commands = {
        'attr': 'Show an attribute (e.g. "attr webserver")',
        'select': 'Select all servers on this page',
        'unselect': 'Unselect all servers on this page',
        'multiadd': 'Add a value to a multi attribute (e.g. "multiadd webservers=nginx")',
        'multidel': 'Delete a value from a multi attribute (e.g. multidel webserver=apache)',
        'delete': 'Delete servers',
        'set': 'Set an attribute (e.g. "set os=wheezy")',
        'goto': 'Goto page n (e.g. "goto 42")',
        'search': 'Focus search field',
        'next': 'Next page',
        'prev': 'Previous page',
        'orderby': 'Order results intuitively (e.g. "order intern_ip [asc]")',
        'commit': 'Commit outstanding changes',
        'export': 'Export all hostnames for usage in shell'
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
            _autocomplete_attr(term, parsed_args, autocomplete, ' '); 
        }
    } else if (command == 'orderby') {
        if (plen == 2 && parsed_args[1]['token'] == 'str') {
            _autocomplete_attr(term, parsed_args, autocomplete, ' ');
        } else if (plen == 3 && parsed_args[2]['token'] == 'str') {
            var order_dir = parsed_args[2]['value'];
            var prefix = term.substring(0, term.length - order_dir.length);
            if (startswith('asc', order_dir)) {
                autocomplete.push({
                    'label': 'Ascending',
                    'value': prefix + 'asc'
                });
            }
            if (startswith('desc', order_dir)) {
                autocomplete.push({
                    'label': 'Descending',
                    'value': prefix + 'desc'
                });
            }
        }
    }
    autocomplete_cb(autocomplete);
}

function handle_command(command)
{
    if (command == 'n' || command == 'next') {
        return handle_command_next_page();
    } else if (command == 'p' || command == 'prev') {
        return handle_command_prev_page();
    } else if (command == 'select') {
        return handle_command_select(true);
    } else if (command == 'unselect') {
        return handle_command_select(false)
    } else if (command == 'search') {
        return handle_command_search();
    } else if (command == 'export') {
        return handle_command_export();
    } else if (is_digit(command[0])) {
        return handle_command_range(command);
    } else {
        return handle_command_other(command);
    }
}

function handle_command_next_page()
{
    var num_pages = Math.ceil(search['num_servers'] / search['per_page']);
    if (search['page'] < num_pages) {
        search['page']++;
        execute_search($('#shell_search').val());
    }
}

function handle_command_prev_page()
{
    search['page']--;
    if (search['page'] < 1) {
        search['page'] = 1;
    }
    execute_search($('#shell_search').val());
}

function handle_command_select(value)
{
    $('input[name="server"]').each(function(index) {
        this.checked = value;
    });
    return '';
}

function handle_command_search()
{
    $('#shell_search').focus();
    return '';    
}

function handle_command_export()
{
    $.get(shell_export_url, {'term': $('#shell_search').val()}, function(hostnames) {
        var box = $('<textarea rows="20" cols="70"></textarea>').text(hostnames);
        var dialog = $('<div title="Exported hostnames"></div>').css(
            'text-align', 'center').append(box);
        $(dialog).dialog({
            'width': '50em'
        });
        box.focus();
    });
    return '';
}

function handle_command_range(command)
{
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
}

function handle_command_other(command)
{
    var parsed_args = parse_function_string(command);
    if (parsed_args[0]['token'] != 'str') {
        return;
    }
    var command_name = parsed_args[0]['value'];
    if (command_name == 'attr') {
        return handle_command_attr(parsed_args);
    } else if (command_name == 'goto') {
        return handle_command_goto(parsed_args);
    } else if (command_name == 'orderby') {
        return handle_command_order(parsed_args);    
    } else if (command_name == 'setattr') {
        return handle_command_set_attr(parsed_args);
    } else if (command_name == 'delattr') {
        return handle_command_del_attr(parsed_args);
    } else if (command_name == 'multiadd') {
        return handle_command_multi_attr(parsed_args, 'add');
    } else if (command_name == 'multidel') {
        return handle_command_multi_attr(parsed_args, 'del');
    }
}

function handle_command_attr(parsed_args)
{
    for(var i = 1; i < parsed_args.length; i++) {
        if (parsed_args[i]['token'] == 'str') {
            var attr_name = parsed_args[i]['value'];
            if (typeof(available_attributes[attr_name]) == 'undefined') {
                return;
            }
            
            // FIXME: Handle all virtual attributes
            if (attr_name == 'all_ips') {
                return;
            }
            
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

function handle_command_goto(parsed_args)
{
    if (parsed_args[1]['token'] != 'str') {
        return;
    }
    var goto_page = parseInt(parsed_args[1]['value'], 10);
    var num_pages = Math.ceil(search['num_servers'] / search['per_page']);
    if (goto_page >= 1 && goto_page <= num_pages) {
        search['page'] = goto_page;
        execute_search($('#shell_search').val());
        return '';
    }
}

function handle_command_order(parsed_args)
{
    if (parsed_args[1]['token'] != 'str') {
        return;
    }

    if (parsed_args.length == 3) {
        if (parsed_args[2]['token'] != 'str') {
            return;
        }
        search['order_dir'] = parsed_args[2]['value'];
    }
    
    search['order_by'] = parsed_args[1]['value'];
    execute_search($('#shell_search').val());
    return '';
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
        },
        'delay': 150,
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
        },
        'delay': 0,
        'autoFocus': true
    });

    $('#shell_command_help_icon').click(function() {
        $('#shell_command_help').dialog({
            'width': '70em',
        });
    });

    $('#shell_command').val('');
});
