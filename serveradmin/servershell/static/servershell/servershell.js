var search = {
    'shown_attributes': ['hostname', 'intern_ip', 'servertype', 'state'],
    'avail_attributes': {},
    'servers': [],
    'num_servers': 0,
    'page': 1,
    'per_page': 100,
    'order_by': null,
    'no_mapping': {},
    'first_server': null
};

var commit = {
    'deleted': [],
    'changes': {}
};

function refresh_servers(callback) {
    var search_request = {
        'term': search['term'],
        'shown_attributes': search['shown_attributes'].join(','),
        'offset': (search['page'] - 1) * search['per_page'],
        'limit': search['per_page'],
        'no_mapping': {},
    };
    if (search['order_by'])
        search_request['order_by'] = search['order_by'];

    $.getJSON(shell_results_url, search_request, function(data) {
        if (data['status'] != 'success') {
            var error = $('<span class="error"></span>').text(data['message']);
            $('#shell_understood').empty().append(error);
            return;
        }
        search['servers'] = data['servers'];
        search['num_servers'] = data['num_servers'];
        search['avail_attributes'] = data['avail_attributes'];
        search['num_pages'] = Math.max(1, Math.ceil(search['num_servers'] / search['per_page']));

        if (search['page'] > search['num_pages']) {
            search['page'] = search['num_pages'];
            return refresh_servers(callback);
        }

        $('#shell_understood').text(data['understood']);
        regenerate_link();
        return callback();
    });
}

function regenerate_link() {
    var attrs = $('input[name=attr]:checked').map(function() {
        return this.value;
    }).get().join(',');
    var args = {
        'term': search['term'],
        'attrs': attrs
    };
    $('#shell_search_link').attr('href', '?' + $.param(args)).show();

}

function build_server_table(servers, attributes, offset) {
    if (typeof offset == 'undefined') {
        offset = 0;
    }
    // Build table header
    var table = $('<table class="valign-middle"></table>');
    var header_tr = $('<tr><th></th><th>No</th></tr>');
    for (var i = 0; i < attributes.length; i++) {
        header_tr.append($('<th></th>').text(attributes[i]));
    }
    table.append(header_tr);

    var delete_set = {};
    for (var i = 0; i < commit['deleted'].length; i++) {
        delete_set[commit['deleted'][i]] = true;
    }

    var avail_attrs = search['avail_attributes'];

    // Fill table
    search['no_mapping'] = {};
    var marked_servers = get_marked_servers();
    for (var i = 0; i < servers.length; i++) {
        var server = servers[i];
        var row_class = i & 1 ? 'row_a' : 'row_b';
        if (delete_set[server['object_id']]) {
            row_class = 'row_del';
        } else if (server['state'] == 'retired') {
            row_class = 'row_state_retired';
        } else if (server['state'] == 'maintenance') {
            row_class = 'row_state_maintenance';
        } else if ([' ', 'deploy_offline', 'deploy_online'].indexOf(server['state']) > 0) {
            row_class = 'row_state_deploy';
        } else if (server['cancelled']) {
            row_class = 'row_cancelled';
        }
        var row = $('<tr class="' + row_class + '"></tr>');
        var check = $('<input type="checkbox" name="server"></input>')
            .attr('value', server['object_id'])
            .attr('id', 'server_' + server['object_id']);
        if (marked_servers.indexOf(server['object_id']) != -1) {
            check.prop('checked', true);
        }
        row.append($('<td></td>').append(check));
        row.append($('<td></td>').text(offset + i + 1));
        for (var j = 0; j < attributes.length; j++) {
            var attr_name = attributes[j];
            var value = server[attr_name];
            var changes = commit['changes'];
            if (typeof changes[server['object_id']] != 'undefined' &&
                    typeof changes[server['object_id']][attr_name] != 'undefined') {
                var change = changes[server['object_id']][attr_name];
                if (change['action'] == 'update') {
                    var value_str = format_value(value, attr_name);
                    var new_value_str = format_value(change['new'], attr_name);
                    // TODO: highlight of old value does not match
                    var del_value = $('<del></del>').text(value_str);
                    var ins_value = $('<ins></ins>').text(new_value_str);
                    var table_cell = $('<td></td>').append(del_value)
                        .append(' ').append(ins_value);
                    _make_attr_editable(table_cell, server, attr_name, change['new']);
                    row.append(table_cell);
                } else if (change['action'] == 'new') {
                    var new_value_str = format_value(change['new'], attr_name);
                    var ins_value = $('<ins></ins>').text(new_value_str);
                    var table_cell = $('<td></td>').append(ins_value);
                    _make_attr_editable(table_cell, server, attr_name, change['new']);
                    row.append(table_cell);
                } else if (change['action'] == 'delete') {
                    var value_str = format_value(value, attr_name);
                    var del_value = $('<del></del>').text(value_str);
                    var table_cell = $('<td></td>').append(del_value);
                    _make_attr_editable(table_cell, server, attr_name, '');
                    row.append(table_cell);
                } else if (change['action'] == 'multi') {
                    var table_cell = $('<td></td>');
                    if (typeof value == 'undefined') {
                        value = [];
                    }
                    if (typeof change['remove'] == 'undefined') {
                        change['remove'] = [];
                    }
                    if (typeof change['add'] == 'undefined') {
                        change['add'] = [];
                    }
                    var current_values = [];

                    for (var k = 0; k < value.length; k++) {
                        var value_str = format_value(value[k], attr_name, true);
                        if (change['remove'].indexOf(value[k]) != -1) {
                            table_cell.append($('<del></del>').text(value_str));
                        } else {
                            current_values.push(value[k]);
                            table_cell.append($('<span></span>').text(value_str));
                        }

                        if (k != value.length - 1 || change['add'].length) {
                            table_cell.append(', ');
                        }
                    }
                    for (var k = 0; k < change['add'].length; k++) {
                        var value_str = format_value(change['add'][k], attr_name, true);
                        table_cell.append($('<ins></ins>').text(value_str));
                        if (k != change['add'].length - 1) {
                            table_cell.append(', ');
                        }
                        current_values.push(change['add'][k]);
                    }

                    if (!avail_attrs[server['servertype']][attr_name]) {
                        table_cell.addClass('cell-disabled');
                    } else {
                        _make_attr_editable(table_cell, server, attr_name, current_values);
                    }
                    row.append(table_cell);
                }
            } else {
                var value_str = format_value(value, attr_name);
                var table_cell = $('<td></td>').text(value_str);
                row.append(table_cell);
                var has_attr = avail_attrs[server['servertype']][attr_name];
                if (attr_name != 'servertype' && has_attr) {
                    _make_attr_editable(table_cell, server, attr_name, value);
                }
                if (!has_attr) {
                    table_cell.addClass('cell-disabled');
                }
            }
        }
        table.append(row);
        search['no_mapping'][offset + i + 1] = server;
        if (servers.length == 0) {
            search['first_server'] = null;
        } else {
            search['first_server'] = servers[0];
        }
    }
    var heading = '<h3>Results (' + search['num_servers'] + ' servers, ';
    heading += 'page ' + search['page'] + '/' + search['num_pages'] + ')</h3>';
    $('#shell_servers').empty().append(heading).append(table);
}

function _make_attr_editable(cell, server, attr_name, value) {
    cell.dblclick(function(ev) {
        if ($('#edit_attr').length) {
            return;
        }
        var attr_obj = available_attributes[attr_name];

        var form = $('<form method="post"></form>');

        if (attr_obj.multi) {
            multi_value_strs = [];
            for (var i = 0; i < value.length; i++) {
                multi_value_strs.push(format_value(value[i], attr_name, true));
            }
            var input = $('<textarea id="edit_attr" rows="5" cols="30"/></textarea>').val(
                    multi_value_strs.join('\n'));
            form.append('<br/>').append(input);
        } else {
            var input = $('<input type="text" id="edit_attr" />').val(
                    format_value(value, attr_name));
            form.append(input);
        }
        var ok_button = $('<input type="submit" value="edit" />');
        form.append(ok_button);

        var stype_attr = search['avail_attributes'][server['servertype']][attr_name];
        if (stype_attr.regexp !== null) {
            form.append($('<div/>').text('Regexp: ' + stype_attr.regexp));
        }
        if (stype_attr.default !== null) {
            form.append($('<div/>').text('Default: ' + stype_attr.default));
        }

        form.submit(function(ev) {
            ev.preventDefault();
            ev.stopPropagation();
            if (attr_obj.multi) {
                var unparsed_values = $('#edit_attr').val();
                if ($.trim(unparsed_values) === '') {
                    unparsed_values = [];
                } else {
                    unparsed_values = unparsed_values.split(/[\n,]+/);
                }
                commit_data = {'action': 'multi', 'add': [], 'remove': []};
                var edit_values = [];
                var was_changed = false;
                for (var i = 0; i < unparsed_values.length; i++) {
                    var unparsed_value = $.trim(unparsed_values[i]);
                    if (unparsed_value === '') {
                        continue;
                    }
                    var edit_value = parse_value(unparsed_value, attr_name);
                    edit_values.push(edit_value);

                    if (server[attr_name].indexOf(edit_value) == -1) {
                        commit_data['add'].push(edit_value);
                        was_changed = true;
                    }
                }
                for (var i = 0; i < server[attr_name].length; i++) {
                    if (edit_values.indexOf(server[attr_name][i]) == -1) {
                        commit_data['remove'].push(server[attr_name][i]);
                        was_changed = true;
                    }
                }

                // We removed all data from multi attribute
                if (unparsed_values.length == 0 && server[attr_name].length != 0) {
                    was_changed = true;
                }

                if (!was_changed) {
                    commit_data = null;
                }
            } else {
                var new_value = parse_value($('#edit_attr').val(), attr_name);
                if (new_value == value) {
                    render_server_table();
                    return;
                } else if (new_value == server[attr_name]) {
                    _restore_attr(server['object_id'], attr_name);
                    render_server_table();
                    return;
                }
                if (typeof server[attr_name] == 'undefined') {
                    if (new_value !== '') {
                        commit_data = {
                            'action': 'new',
                            'new': new_value
                        };
                    } else {
                        commit_data = null;
                    }
                } else {
                    if (server[attr_name] == new_value) {
                        commit_data = null;
                    } else if (new_value !== '') {
                        commit_data = {
                            'action': 'update',
                            'new': new_value,
                            'old': server[attr_name]
                        };
                    } else {
                        commit_data = {
                            'action': 'delete',
                            'old': server[attr_name]
                        };
                    }
                }
            }
            if (commit_data === null) {
                // Since we might remove uncomitted data, we have to delete
                // them from the outstanding commit.
                if (typeof commit['changes'][server['object_id']] != 'undefined') {
                    delete commit['changes'][server['object_id']][attr_name];
                }
                render_server_table();
                return;
            }
            if (typeof commit['changes'][server['object_id']] == 'undefined') {
                commit['changes'][server['object_id']] = {};
            }
            commit['changes'][server['object_id']][attr_name] = commit_data;
            render_server_table();
        }).keypress(function(ev) {
            if (ev.keyCode == 27) {
                render_server_table();
            }
        });
        cell.empty().append(form);
        input.focus();
        if (input[0].setSelectionRange) {
            var len = input.val().length;
            input[0].setSelectionRange(len, len);
        }
    });
}

function _restore_attr(server_id, attr_name) {
    if (typeof commit['changes'][server_id] != 'undefined') {
        if (typeof commit['changes'][server_id][attr_name] != 'undefined') {
            delete commit['changes'][server_id][attr_name];
        }
    }
}

function format_value(value, attr_name, single_value) {
    var attr_obj = available_attributes[attr_name];
    if (typeof value == 'undefined') {
        value = '';
    } else if (attr_obj['multi'] && !single_value) {
        value = value.sort().join(', ');
    }
    return value;
}

function parse_value(value, attr_name) {
    var attr_obj = available_attributes[attr_name];
    if (value === '') {
        return null;
    }
    if (attr_obj['type'] == 'number') {
        return Number(value);
    }
    if (attr_obj['type'] == 'boolean') {
        return value == 'true' || value == '1' || value == 'True';
    }
    return value;
}

function render_server_table() {
    var offset = (search['page'] - 1) * search['per_page'];
    var shown_attributes = [];
    for (var i = 0; i < search['shown_attributes'].length; i++) {
        if (shown_attributes.indexOf(search['shown_attributes'][i]) == -1) {
            shown_attributes.push(search['shown_attributes'][i]);
        }
    }
    $('#shell_attributes input[name="attr"]').prop('checked', false);
    for (var i = 0; i < shown_attributes.length; i++) {
        $('#shell_attributes input[value="' + shown_attributes[i] + '"]').prop('checked', true);
    }
    build_server_table(search['servers'], shown_attributes, offset);
}

function autocomplete_shell_command(term, autocomplete_cb) {
    var autocomplete = [];
    var parsed_args = parse_function_string(term);
    var plen = parsed_args.length;

    var commands = {
        'attr': 'Show an attribute (e.g. "attr webserver")',
        'selectall': 'Select all servers on this page',
        'unselectall': 'Unselect all servers on this page',
        'multiadd': 'Add a value to a multi attribute (e.g. "multiadd webservers=nginx")',
        'multidel': 'Delete a value from a multi attribute (e.g. multidel webserver=apache)',
        'delete': 'Delete servers',
        'setattr': 'Set an attribute (e.g. "setattr os=wheezy")',
        'delattr': 'Delete an attribute (e.g. "delattr os")',
        'goto': 'Goto page n (e.g. "goto 42")',
        'search': 'Focus search field',
        'next': 'Next page',
        'prev': 'Previous page',
        'orderby': 'Order results intuitively (e.g. "order intern_ip [asc]")',
        'commit': 'Commit outstanding changes',
        'export': 'Export all hostnames for usage in shell',
        'perpage': 'Show a specific number of hosts per page (e.g. "perpage 50")',
        'graph': 'Show configured Graphite graph table for selected hosts',
        'new': 'Create a new server',
        'clone': 'Clone a server with it\'s attributes',
        'inspect': 'List all attributes of a server',
        'edit': 'Edit all attributes of a server',
        'changes': 'Show all changes',
        'history': 'Show history for selected hosts',
        'bookmark': 'Bookmark current Search'
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
    if (command == 'attr' || command == 'delattr') {
        if (parsed_args[plen - 1]['token'] == 'str') {
            _autocomplete_attr(term, parsed_args, autocomplete, ' ');
        }
    } else if (command == 'setattr') {
        // Do not autocomplete values with names of attributes
        if (plen > 2) {
            return;
        }
        if (parsed_args[plen - 1]['token'] == 'str') {
            function only_single(attr) {
                return !available_attributes[attr]['multi'];
            }
            _autocomplete_attr(term, parsed_args, autocomplete, '=', only_single);
        }
    } else if (command == 'multiadd' || command == 'multidel') {
        if (parsed_args[plen - 1]['token'] == 'str' && (plen < 3 || parsed_args[plen - 2]['token'] != 'key')) {
            function only_multi(attr) {
                return available_attributes[attr]['multi'];
            }
            _autocomplete_attr(term, parsed_args, autocomplete, '=', only_multi);
        }
    } else if (command == 'orderby' && parsed_args[1]['token'] == 'str') {
        _autocomplete_attr(term, parsed_args, autocomplete, ' ');
    } else if (command == 'new' && parsed_args[1]['token'] == 'str') {
        _autocomplete_server(term, parsed_args, autocomplete, ' ');
    }
    autocomplete_cb(autocomplete);
}

function execute_on_servers(callback) {
    var marked_servers = get_marked_servers();
    if (marked_servers.length == 0) {
        if (search['first_server'] != null) {
            callback(search['first_server']);
        }
    } else {
        for (var i = 0; i < search['servers'].length; i++) {
            var server = search['servers'][i];

            if (marked_servers.indexOf(server['object_id']) >= 0) {
                if (callback(server) === false) {
                    break;
                }
            }
        }
    }
}

function handle_command(command) {
    if (command === '') {
        return '';
    } else if (command == 'n' || command == 'next') {
        return handle_command_next_page();
    } else if (command == 'p' || command == 'prev') {
        return handle_command_prev_page();
    } else if (command == 'selectall') {
        return handle_command_select(true);
    } else if (command == 'unselectall') {
        return handle_command_select(false);
    } else if (command == 'search') {
        return handle_command_search();
    } else if (command == 'export') {
        return handle_command_export();
    } else if (command == 'graph') {
        return handle_command_graph();
    } else if (command == 'clone') {
        return handle_command_clone();
    } else if (command == 'inspect') {
        return handle_command_inspect();
    } else if (command == 'edit') {
        return handle_command_edit();
    } else if (command == 'delete') {
        return handle_command_delete();
    } else if (command == 'changes') {
        return handle_command_changes();
    } else if (command == 'history') {
        return handle_command_history();
    } else if (is_digit(command[0])) {
        return handle_command_range(command);
    } else {
        return handle_command_other(command);
    }
}

function handle_command_next_page() {
    if (search['page'] < search['num_pages']) {
        search['page']++;
        refresh_servers(function() {
            render_server_table();
        });
    }
}

function handle_command_prev_page() {
    search['page']--;
    if (search['page'] < 1) {
        search['page'] = 1;
    }
    refresh_servers(function() {
        render_server_table();
    });
}

function handle_command_select(value) {
    $('input[name="server"]').each(function(index) {
        this.checked = value;
    });
    return '';
}

function handle_command_search() {
    $('#shell_search').focus();
    return '';
}

function handle_command_bookmark(parsed_args) {
    if (parsed_args.length < 2) {
        alert('Please provide a bookmark name!')
        return '';
    }

    name = ''
    for (i = 1; i < parsed_args.length; i++) {
        name += parsed_args[i].value + ' '
    }

    query_string = { 'term': $('#shell_search').val(), 'name': name}
    $.get(shell_bookmark_url, query_string, function(data) {
          alert(data['message'])        
    });
    return ''
}

function handle_command_export() {
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

function handle_command_graph() {
    var marked_servers = get_marked_servers();
    var hostnames = search['servers'].filter(function(server) {
        return marked_servers.indexOf(server['object_id']) >= 0;
    }).map(function(server) {
        return server['hostname'];
    });

    // The established behavior of the Servershell commands is to select
    // the first server, if none of them are explicitly selected.
    if (hostnames.length == 0 && search['first_server'] != null) {
        hostnames = [search['first_server']['hostname']];
    }

    if (hostnames.length > 0) {
        var query_str = '?' + hostnames.map(function(hostname) {
            return 'hostname=' + hostname;
        }).join('&');

        $.get(shell_graph_url + query_str, function(data) {
            var dialog = $('<div title="Graphite Graph Table"></div>');
            dialog.append(data);
            dialog.dialog({
                'width': 1550
            });
        });
    }

    return '';
}

function handle_command_clone() {
    function clone_server(server) {
        var clone_url = shell_clone_url + '?hostname=' + server['hostname'];
        window.location.href = clone_url;
    }
    execute_on_servers(clone_server);
    return '';
}

function handle_command_edit() {
    execute_on_servers(function(server) {
        var query_str = '?' + $.param({'object_id': server['object_id']});
        $.get(shell_edit_url + query_str, function(data) {
            var dialog = $('<div title="' + server['hostname'] + '"></div>');
            dialog.append(data);
            dialog.dialog({
                'width': 1000
            });
        });
        return true;
    });
    return '';
}

function handle_command_inspect() {
    execute_on_servers(function(server) {
        var query_str = '?' + $.param({'object_id': server['object_id']});
        $.get(shell_inspect_url + query_str, function(data) {
            var dialog = $('<div title="' + server['hostname'] + '"></div>');
            dialog.append(data);
            dialog.dialog({
                'width': 1000
            });
        });
        return true;
    });
    return '';
}

function handle_command_delete() {
    execute_on_servers(function(server) {
        commit['deleted'].push(server['object_id']);
        return true;
    });
    render_server_table();
    return '';
}

function handle_command_changes() {
    window.location = shell_changes_url;
}

function handle_command_history() {
    function show_history(server) {
        var query_str = '?' + $.param({'server_id': server['object_id']});
        $.get(serverdb_history_url + query_str, function(data) {
            var dialog = $('<div title="History of #' + server['object_id'] + '"></div>');
            dialog.append(data);
            dialog.dialog({
                'width': 800
            });
        });
        return true;
    }
    execute_on_servers(show_history);
    return '';
}

function handle_command_range(command) {
    var mark_nos = [];
    var ranges = command.split(',');
    for (var i = 0; i < ranges.length; i++) {
        var range = ranges[i].split('-');
        if (range.length == 1) {
            mark_nos.push(parseInt($.trim(range[0]), 10));
        } else if (range.length == 2) {
            var first = parseInt($.trim(range[0]), 10);
            var second = parseInt($.trim(range[1]), 10);
            if (first < 0 || second < 0) {
                continue;
            }
            for (var j = first; j <= second; j++) {
                mark_nos.push(j);
            }
        }

    }
    for (var i = 0; i < mark_nos.length; i++) {
        var server = search['no_mapping'][mark_nos[i]];
        if (typeof server != 'undefined') {
            var check = $('#server_' + server['object_id'])[0];
            check.checked = !check.checked;
        }
    }
    return '';
}

function handle_command_other(command) {
    var parsed_args = parse_function_string(command);
    if (parsed_args[0]['token'] != 'str') {
        return;
    }
    var command_name = parsed_args[0]['value'];
    if (command_name == 'attr') {
        return handle_command_attr(parsed_args);
    } else if (command_name == 'new') {
        return handle_command_new(parsed_args);
    } else if (command_name == 'goto') {
        return handle_command_goto(parsed_args);
    } else if (command_name == 'orderby') {
        return handle_command_order(parsed_args);
    } else if (command_name == 'setattr') {
        return handle_command_setattr(parsed_args);
    } else if (command_name == 'delattr') {
        return handle_command_delattr(parsed_args);
    } else if (command_name == 'multiadd') {
        return handle_command_multiattr(parsed_args, 'add');
    } else if (command_name == 'multidel') {
        return handle_command_multiattr(parsed_args, 'remove');
    } else if (command_name == 'commit') {
        return handle_command_commit(parsed_args);
    } else if (command_name == 'perpage') {
        return handle_command_perpage(parsed_args);
    } else if (command_name == 'bookmark') {
        return handle_command_bookmark(parsed_args)
    }
}

function handle_command_attr(parsed_args) {
    var value_added = false;

    for (var i = 1; i < parsed_args.length; i++) {
        if (parsed_args[i]['token'] == 'str') {
            var attr_name = parsed_args[i]['value'];
            if (typeof available_attributes[attr_name] == 'undefined') {
                return;
            }

            var index = search['shown_attributes'].indexOf(attr_name);
            if (index == -1) {
                value_added = true;
                search['shown_attributes'].push(attr_name);
            } else {
                search['shown_attributes'].remove(index);
            }
        }
    }

    if (value_added) {
        refresh_servers(function() {
            render_server_table();
        });
    } else {
        render_server_table();
    }

    return '';
}

function handle_command_new(parsed_args) {
    if (parsed_args[1]['token'] != 'str') {
        return;
    }
    var new_url = shell_new_url + '?servertype=' + parsed_args[1]['value'];
    window.location.href = new_url;
    return '';
}

function handle_command_goto(parsed_args) {
    if (parsed_args[1]['token'] != 'str') {
        return;
    }
    var goto_page = parseInt(parsed_args[1]['value'], 10);
    if (goto_page >= 1 && goto_page <= search['num_pages']) {
        search['page'] = goto_page;
        refresh_servers(function() {
            render_server_table();
        });
        return '';
    }
}

function handle_command_order(parsed_args) {
    if (parsed_args[1]['token'] != 'str') {
        return;
    }

    search['order_by'] = parsed_args[1]['value'];
    refresh_servers(function() {
        render_server_table();
    });
    return '';
}

function handle_command_perpage(parsed_args) {
    if (parsed_args[1]['token'] != 'str') {
        return;
    }
    search['per_page'] = parseInt(parsed_args[1]['value'], 10);
    refresh_servers(function() {
        render_server_table();
    });
    return '';
}

function handle_command_setattr(parsed_args) {
    if (parsed_args.length != 3 || parsed_args[1]['token'] != 'key' ||
            parsed_args[2]['token'] != 'str') {
        return;
    }

    var attr_name = parsed_args[1]['value'];
    if (search['shown_attributes'].indexOf(attr_name) == -1) {
        search['shown_attributes'].push(attr_name);
    }

    refresh_servers(function() {
        var new_value = parsed_args[2]['value'];
        var marked_servers = get_marked_servers();

        var error = null;
        if (typeof available_attributes[attr_name] == 'undefined') {
            error = 'No such attribute';
        } else if (available_attributes[attr_name].multi) {
            error = 'This is a multi attribute. Use multiadd/multidel instead!';
        } else if (marked_servers.length == 0) {
            error = 'Please select some servers.';
        }
        if (error) {
            $('<div title="Error"></div>').text(error).dialog({
                'buttons': {
                    'OK': function() {
                        $(this).dialog('close');
                    }
                }
            });
            return ;
        }

        var changes = commit['changes'];
        for (var i = 0; i < search['servers'].length; i++) {
            var server = search['servers'][i];
            var server_id = server['object_id'];

            if (marked_servers.indexOf(server_id) < 0) {
                continue;
            }

            if (!search['avail_attributes'][server['servertype']][attr_name]) {
                continue;
            }

            if (typeof changes[server_id] == 'undefined') {
                changes[server_id] = {};
            }
            var old_value = server[attr_name];
            if (typeof old_value == 'undefined') {
                changes[server_id][attr_name] = {
                    'action': 'new',
                    'new': parse_value(new_value, attr_name)
                };
            } else {
                changes[server_id][attr_name] = {
                    'action': 'update',
                    'new': parse_value(new_value, attr_name),
                    'old': old_value
                };
            }
        }
        render_server_table();
    });
    return '';
}

function handle_command_delattr(parsed_args) {
    if (parsed_args.length != 2 || parsed_args[1]['token'] != 'str') {
        return;
    }

    var attr_name = parsed_args[1]['value'];
    if (search['shown_attributes'].indexOf(attr_name) == -1) {
        search['shown_attributes'].push(attr_name);
    }

    refresh_servers(function() {
        var marked_servers = get_marked_servers();
        var changes = commit['changes'];

        for (var i = 0; i < search['servers'].length; i++) {
            var server = search['servers'][i];
            var server_id = server['object_id'];
            var attr_obj = available_attributes[attr_name];

            if (marked_servers.indexOf(server_id) < 0) {
                continue;
            }

            if (typeof changes[server_id] == 'undefined') {
                changes[server_id] = {};
            }

            if (attr_obj.multi) {
                changes[server_id][attr_name] = {
                    'action': 'multi',
                    'add': [],
                    'remove': server[attr_name].slice(0)
                };
            } else {
                if (attr_name in server) {
                    changes[server_id][attr_name] = {
                        'action': 'delete',
                        'old': server[attr_name]
                    };
                }
            }
        }
        render_server_table();
    });
    return '';
}

function handle_command_multiattr(parsed_args, action) {
    if (parsed_args.length != 3 || parsed_args[1]['token'] != 'key' ||
            parsed_args[2]['token'] != 'str') {
        return;
    }
    var attr_name = parsed_args[1]['value'];
    if (search['shown_attributes'].indexOf(attr_name) == -1) {
        search['shown_attributes'].push(attr_name);
    }

    refresh_servers(function() {
        var values = parsed_args[2]['value'].split(',');

        var marked_servers = get_marked_servers();
        if (marked_servers.length == 0) {
            $('<div title="Select servers">You have to select servers first</div>').dialog({
                buttons: {
                    'OK': function() {
                        $(this).dialog('close');
                    }
                }
            });
            return;
        }
        var changes = commit['changes'];
        for (var i = 0; i < search['servers'].length; i++) {
            var server = search['servers'][i];
            var server_id = server['object_id'];

            if (marked_servers.indexOf(server_id) < 0) {
                continue;
            }

            // Don't modify multiattr if it doesn't exist
            if (!search['avail_attributes'][server['servertype']][attr_name]) {
                continue;
            }

            if (typeof changes[server_id] == 'undefined') {
                changes[server_id] = {};
            }
            if (typeof changes[server_id][attr_name] == 'undefined') {
                changes[server_id][attr_name] = {
                    'action': 'multi',
                    'add': [],
                    'remove': []
                };
            }
            for (var j = 0; j < values.length; j++) {
                var value = values[j];
                var parsed_value = parse_value(value, attr_name);
                if (action == 'remove') {
                    var index = changes[server_id][attr_name]['add'].indexOf(parsed_value);
                    if (index != -1) {
                        changes[server_id][attr_name]['add'].splice(index, 1);
                    } else {
                        changes[server_id][attr_name]['remove'].push(parsed_value);
                    }
                } else if (action == 'add') {
                    var index = changes[server_id][attr_name]['remove'].indexOf(parsed_value);
                    if (index != -1) {
                        changes[server_id][attr_name]['remove'].splice(index, 1);
                    } else {
                        var contains_value = false;
                        if (typeof server[attr_name] != 'undefined') {
                            contains_value = server[attr_name].indexOf(parsed_value) != -1;
                        }
                        if (!contains_value) {
                            changes[server_id][attr_name]['add'].push(parsed_value);
                        }
                    }
                }
            }
        }
        render_server_table();
    });
    return '';
}

function handle_command_commit(parsed_args) {
    $.post(shell_commit_url, {'commit': JSON.stringify(commit)}, function(result) {
        if (result['status'] == 'error') {
            $('<div class="commit-message" title="Commit error"></div>').text(result['message']).dialog();
        } else if (result['message']) {
            $('<div class="commit-message" title="Commit message"></div>').text(result['message']).dialog();
        }
        commit = {'deleted': [], 'changes': {}};
        refresh_servers(function() {
            render_server_table();
        });
    });
    return '';
}

function get_marked_servers() {
    var marked_servers = [];
    $('input[name="server"]:checked').each(function() {
        marked_servers.push(parseInt(this.value, 10));
    });
    return marked_servers;
}

$(function() {
    $('#shell_search_form').submit(function(ev) {
        $('#shell_understood').text('');
        $('#shell_servers').empty();
        search['page'] = 1;
        ev.stopPropagation();
        search['term'] = $('#shell_search').val();
        refresh_servers(function() {
            render_server_table();
            $('#shell_command').focus();
        });
        return false;
    });

    $('#shell_search').bind('change', function(ev) {
        $('#shell_understood').text('');
        $('#shell_servers').empty();
    });

    $('#shell_command_form').submit(function(ev) {
        ev.stopPropagation();
        var command_value = $.trim($('#shell_command').val());
        var new_command = handle_command(command_value);
        if (typeof new_command != 'undefined' && new_command != null) {
            $('#shell_command').val(new_command);
            $.post(shell_store_command_url, {'command': command_value});
            if (shell_history['commands'].indexOf(command_value) === -1) {
                shell_history['commands'].push(command_value);
            }
            shell_history['index'] = shell_history['commands'].length - 1;
        }
        return false;
    });

    $('#shell_command').autocomplete({
        'source': function(request, response) {
            autocomplete_shell_command($.trim(request.term), response);
        },
        'delay': 0,
        'autoFocus': true
    });

    $('#shell_command').keydown(function(ev) {
        var new_command = null;
        if (shell_history['index'] == -1) {
            return true; // We have no history.
        }

        if (ev.shiftKey && ev.which == 38) { // Arrow up
            $(this).autocomplete('close');
            if (shell_history['index'] != 0) {
                shell_history['index']--;
            }
            new_command = shell_history['commands'][shell_history['index']];
        } else if (ev.shiftKey && ev.which == 40) { // Arrow down
            $(this).autocomplete('close');
            if (shell_history['index'] < shell_history['commands'].length - 1) {
                shell_history['index']++;
            }
            new_command = shell_history['commands'][shell_history['index']];
        } else {
            return true;
        }

        if (new_command != null) {
            $(this).val(new_command);
        }
    });

    $('#shell_command_help_icon').click(function() {
        $('#shell_command_help').dialog({
            'width': '70em'
        });
    });

    $('#shell_search_help_icon').click(function() {
        $('#shell_search_help').dialog({
            'width': '70em'
        });
    });

    $('#shell_command').val('');

    $('#shell_attributes input[name="attr"]').each(function() {
        if (this.checked) {
            search['shown_attributes'].push(this.value);
        }
    });

    $('#shell_attributes input[name="attr"]').bind('change', function(ev) {
        var s_index = search['shown_attributes'].indexOf(this.value);
        if (s_index != -1 && !this.checked) {
            search['shown_attributes'].splice(s_index, 1);
        }

        var index = search['shown_attributes'].indexOf(this.value);
        if (index == -1 && this.checked) {
            search['shown_attributes'].push(this.value);
        } else if (index != -1 && !this.checked) {
            search['shown_attributes'].splice(index, 1);
        }

        if (this.checked) {
            refresh_servers(render_server_table);
        } else {
            render_server_table();
        }

        regenerate_link();
    });

    $('#shell_attributes li').each(function() {
        var attr_item = $(this);
        var attribute_type = attr_item.attr('data-attr-type');
        var symbol;
        switch (attribute_type) {
            case 'reverse':
                symbol = 'Я';
                break;
            case 'supernet':
                symbol = 'P';
                break;
            default:
                symbol = attribute_type.charAt(0).toUpperCase();
        }
        if (attr_item.attr('data-attr-multi') == 'True') {
            symbol = '[' + symbol + ']';
        }

        var link = $('<span class="link">' + symbol + '</span>');
        link.click(function(ev) {
            var attr_name = attr_item.attr('data-attr');

            $.get(shell_values_url + '?attribute=' + attr_name, function(data) {
                $('<div title="' + attr_name + '"></div>').append(data).dialog();
            });
        });

        attr_item.prepend(link);
    });

    $('#shell_attributes li .attr-tooltip').each(function() {
        $(this).tooltip();
    });

    $('#shell_attributes_toggle').click(function() {
        var attribute_list = $('#shell_attributes_content').toggle();
        if (attribute_list.is(':visible')) {
            $('#shell_attributes_toggle').text('(hide)');
        } else {
            $('#shell_attributes_toggle').text('(show)');
        }

    });

    $('#shell_command').bind('keydown', function(ev) {
        var key = ev.keyCode || ev.which;
        if (key == 9) {
            ev.preventDefault();
        }
    });

    if ($('#shell_search').val() !== '') {
        search['page'] = 1;
        search['term'] = $('#shell_search').val();
        refresh_servers(function() {
            render_server_table();
            $('#shell_command').focus();
        });
    }
});


function apply_bookmark(element)
{
    $('#shell_search')[0].value = element.value
}
