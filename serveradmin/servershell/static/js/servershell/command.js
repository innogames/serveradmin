servershell.commands = {
    search: function() {
        $('#search').focus();
    },
    next: function() {
        if (servershell.page() < servershell.pages()) {
            servershell.offset += servershell.limit;
            servershell.submit_search();
        }
        else {
            servershell.alert('No more pages!', 'secondary', true);
        }
    },
    prev: function() {
        if (servershell.page() > 1) {
            servershell.offset -= servershell.limit;
            servershell.submit_search();
        }
        else {
            servershell.alert('No previous pages!', 'secondary', true);
        }
    },
    goto: function(page) {
        if (page > 0 && page <= servershell.pages()) {
            servershell.offset = servershell.limit * (page - 1);
            servershell.submit_search();
        }
        else {
            servershell.alert(`No such page ${page}!`, 'secondary', true);
        }
    },
    perpage: function(limit) {
        if (limit > 100)
            servershell.alert('Please try to avoid big queries if possible', 'warning', true);
        servershell.limit = Math.abs(limit);
        servershell.submit_search();
    },
    attr: function(names) {
        // @TODO: If somebody enters multiple attributes we reload the search
        //        for each change. Maybe we can use more clever methods of
        //        array to add or remove them at once ...
        names.split(',').forEach(function(name) {
            // Check if attribute name exists
            if (servershell.attributes.some(a => a.attribute_id === name)) {
                let index = servershell.shown_attributes.indexOf(name);
                if (index > -1) {
                    // Hide in result table
                    servershell.shown_attributes.splice(index, 1);
                }
                else {
                    // Show in result table
                    servershell.shown_attributes.push(name);
                }
            }
            else {
                servershell.alert(`Attribute ${name} does not exist!`, 'danger', true);
            }
        });
    },
    orderby: function(name) {
        if (servershell.attributes.some(a => a.attribute_id === name)) {
            if (servershell.shown_attributes.indexOf(name) === -1) {
                servershell.commands.attr(name);
            }
            servershell.order_by = name;
        }
        else {
            servershell.alert(`Attribute ${name} does not exist!`, 'danger', true);
        }
    },
    export: function(names) {
        let attr_names = names.split(',');
        let to_export = '';

        servershell.servers.forEach(function(server) {
            attr_names.forEach(function(attr_name) {
                if (server.hasOwnProperty(attr_name)) {
                    to_export += server[attr_name];
                }
                to_export += '\t'
            });
            to_export += '\n';
        });

        $('#export_text').val(to_export);
        $('#modal_export').modal('show');
    },
    selectall: function() {
        $('#result_table tbody input[name=server]').each(function() {
            this.checked = true;
        });
    },
    unselectall: function() {
        $('#result_table tbody input[name=server]').each(function() {
            this.checked = false;
        });
    },
    select: function(selection) {
        selection.split(',').forEach(function(number) {
            let range = number.split('-');
            let start = parseInt(range[0]);
            let stop = parseInt(range.length === 1 ? range[0] : range[1]);
            let checkboxes = $('#result_table tbody input[name=server]');

            checkboxes.slice(start - 1, stop).click();
        })
    },
    graph: function() {
        let selected = servershell.get_selected();
        if (selected.length === 0) {
            servershell.alert('Select at least one server!', 'danger', true);
            return;
        }

        let query_string = selected.map(o => `object_id=${o}`).join('&');
        let url = servershell.urls.graphite + '?' + query_string;
        window.open(url, '_blank');
    },
    inspect: function() {
        let selected = servershell.get_selected();
        if (selected.length === 0) {
            servershell.alert('Select at least one server!', 'danger', true);
            return;
        }

        selected.forEach(function(object_id) {
           let url = servershell.urls.inspect + `?object_id=${object_id}`;
           window.open(url, '_blank');
        });
    },
    edit: function() {
        let selected = servershell.get_selected();
        if (selected.length === 0) {
            servershell.alert('Select at least one server!', 'danger', true);
            return;
        }

        selected.forEach(function(object_id) {
            let url = servershell.urls.edit + `?object_id=${object_id}`;
            window.open(url, '_blank');
        });
    },
    setattr: function(arguments) {
        let attr_value = arguments.split('=');

        if (attr_value.length !== 2) {
            servershell.alert('Wrong syntax! Use setattr attribute_id=value', 'danger', true);
            return;
        }

        let attribute_id = attr_value[0];
        let new_value = attr_value[1];

        // Check if attribute exists or typo
        if (!servershell.attributes.find(a => a.attribute_id === attribute_id)) {
            servershell.alert(`Attribute ${attribute_id} does not exist!`, true);
            return;
        }

        // If attribute is not visible make it visible first
        if (!servershell.shown_attributes.find(a => a === attribute_id))
             servershell.shown_attributes.push(attribute_id);

        servershell.get_selected().forEach(function(object_id) {
            servershell.save_change(object_id, attribute_id, new_value);
            servershell.edit_row(object_id, attribute_id, new_value);
        });
    }
};

$(document).ready(function() {
   $('#command_form').submit(function(event) {
        event.preventDefault();

        let cmd = servershell.command.split(' ');

        // User specified a one, more or a range of servers to select
        if (cmd[0].match(/^([0-9]+(,|-)?([0-9]+)?)+$/)) {
            servershell.commands.select(servershell.command);
            return;
        }

        if (Object.keys(servershell.commands).indexOf(cmd[0])) {
            servershell.commands[cmd[0]](...cmd.slice(1));
        }
   })
});