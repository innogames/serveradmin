/**
 * Transform value into matching type
 *
 * We get user input always as string. This method transforms values for
 * number, boolean etc. attributes in the matching type
 *
 * @param value
 * @param attribute
 * @returns {*}
 */
servershell.transform_value = function(value, attribute) {
    if (attribute.type === 'number') {
        return attribute.multi ? value.map(v => Number.parseInt(v)) : Number.parseInt(value);
    }
    else if (attribute.type === 'boolean') {
        return attribute.multi ? value.map(v => !!v) : !!value;
    }

    return value;
};

/**
 * Get changes staged for commit
 *
 * Returns the changes staged to commit for the given object and attribute
 * or false if there are none yet.
 *
 * @param object serveradmin object
 * @param attribute serveradmin attribute
 * @returns {boolean|*}
 */
servershell.get_changes = function(object, attribute) {
    let changes = servershell.to_commit.changes;

    if (!changes.hasOwnProperty(object.object_id)) {
        return false;
    }

    if (!changes[object.object_id].hasOwnProperty(attribute.attribute_id)) {
        return false;
    }

    return changes[object.object_id][attribute.attribute_id];
};

/**
 * Stage changes to commit for attributes
 *
 * Discard already staged changes to object and attribute and apply new
 * stages to commit.
 *
 * @param object_id e.g. 123456
 * @param attribute_id  e.g. state or responsible_admin
 * @param value e.g. maintenance
 */
servershell.update_attribute = function(object_id, attribute_id, value) {
    // Just shorthands to increase readability
    let changes = servershell.to_commit.changes;
    let object = servershell.get_object(object_id);
    let attribute = servershell.get_attribute(attribute_id);

    value = servershell.transform_value(value, attribute);

    // No change for this object about to commit yet
    if (!changes.hasOwnProperty(object_id)) {
        changes[object_id] = {};
    }

    if (attribute.multi) {
        // Remove duplicates in case user entered the same value twice
        value = [...new Set(value)];

        // Determine changes to add and remove for to_commit.
        let to_add = value.filter(v => !object[attribute_id].includes(v));
        let to_remove = object[attribute_id].filter(v => !value.includes(v));

        // It might be that there is nothing more to change for this attribute
        if (to_add.length === 0 && to_remove.length === 0) {
            delete changes[object_id][attribute_id];
        }
        else {
            // This will override previous staged - see above
            changes[object_id][attribute_id] = {
                'action': 'multi',
                'add': to_add,
                'remove': to_remove,
            }
        }
    }
    else {
        let current_value = object[attribute_id];
        if (value === current_value) {
            delete changes[object_id][attribute_id];
        }
        else {
            changes[object_id][attribute_id] = {
                'action': 'update',
                'new': value,
                'old': current_value,
            }
        }
    }

    // Nothing to commit (anymore) for this object ?
    if (Object.keys(changes[object_id]).length === 0) {
        delete changes[object_id];
    }
};

/**
 * Delete attribute value for object
 *
 * Deletes the attribute value for objects no matter if multi attribute or
 * normal single value attribute.
 *
 * @param object_id e.g. 12345
 * @param attribute_id e.g. state or responsible_admin
 */
servershell.delete_attribute = function(object_id, attribute_id) {
    let change;
    let changes = servershell.to_commit.changes;
    let attribute = servershell.get_attribute(attribute_id);
    let old_value = servershell.get_object(object_id)[attribute_id];

    if (attribute.multi) {
        change = {
            'action': 'multi',
            'add': [],
            'remove': old_value.sort(),
        };
    }
    else {
        change = {
            'action': 'delete',
            'old': old_value,
        };
    }

    if (!changes.hasOwnProperty(object_id)) {
        changes[object_id] = {};
    }

    if (!changes[object_id].hasOwnProperty(attribute_id)) {
        changes[object_id][attribute_id] = {};
    }

    changes[object_id][attribute_id] = change;
};

/**
 * Check if objects are selected
 *
 * Checks if at least and at most objects are selected and if not shows a
 * alert using the javascript alert function of the servershell.
 *
 * @param min positive integer or -1 for unlimited
 * @param max min positive integer or -1 for unlimited
 * @returns {boolean}
 */
function validate_selected(min=1, max=-1) {
    let selected = servershell.get_selected().length;
    if ((min !== -1 && selected < min) || (max !== -1 && selected > max)) {
        if (max === -1) {
            servershell.alert(`You must select at least ${min} object(s)`, 'warning');
        }
        else {
            servershell.alert(`Select at least ${min} and at most ${max} objects`, 'warning');
        }
        return false;
    }

    return true;
}

// Serveradmin Servershell plugins can provide help for custom commands by
// extending the servershell.commands_help array like in the example below in
// their static/js/$app.servershell.plugin.js
servershell.commands_help = [
    // Example:
    // {
    //     "command": "foo",
    //     "arguments": "attr_name",
    //     "description": "A foo that bars",
    // }
]

servershell.commands = {
    pin: function() {
        let selected_ids = servershell.get_selected();
        servershell.pinned.push(...selected_ids);
        servershell.pinned = [...new Set(servershell.pinned)];
        servershell.update_result();
    },
    unpin: function() {
        let selected_ids = servershell.get_selected();
        servershell.pinned = servershell.pinned.filter(value => selected_ids.indexOf(value) === -1);
        servershell.update_result();
    },
    search: function() {
        $('#term').focus();
    },
    next: function() {
        if (servershell.page() < servershell.pages()) {
            servershell.offset += servershell.limit;
            servershell.submit_search();
        }
        else {
            servershell.alert('No more pages!', 'warning');
        }
    },
    prev: function() {
        if (servershell.page() > 1) {
            servershell.offset -= servershell.limit;
            servershell.submit_search();
        }
        else {
            servershell.alert('Already on first page!', 'warning');
        }
    },
    goto: function(page) {
        if (isNaN(page) || page < 0 || page > servershell.pages()) {
            servershell.alert(`${page} is not a valid page number!`, 'warning');
            return;
        }

        servershell.offset = servershell.limit * (page - 1);
        servershell.submit_search();
    },
    perpage: function(limit) {
        if (isNaN(limit) || limit < 1) {
            servershell.alert(`${limit} must be a number greater zero!`, 'warning');
            return;
        }

        if (limit > 100) {
            servershell.alert('Do you really need to view that many objects at once ?', 'warning');
        }

        servershell.limit = Math.abs(limit);
        servershell.offset = 0;
        servershell.submit_search();
    },
    attr: function(attribute_ids) {
        attribute_ids = attribute_ids.split(',').map(a => a.trim()).filter(a => a !== '');
        let unknown = attribute_ids.filter(a => servershell.attributes.find(b => b.attribute_id === a) === undefined);

        if (unknown.length > 0) {
            servershell.alert(`The attribute(s) ${unknown.join(', ')} does not exist!`, 'warning');
            return;
        }

        // Avoid reloading by working with a copy
        let shown_attributes = servershell.shown_attributes;
        let to_remove = attribute_ids.filter(a => shown_attributes.find(b => b === a) !== undefined);
        let to_add = attribute_ids.filter(a => shown_attributes.find(b => b === a) === undefined);
        shown_attributes = shown_attributes.filter(a => !to_remove.includes(a));
        shown_attributes.splice(shown_attributes.length, 0, ...to_add);

        // Attribute currently ordered by is about to be removed
        if (to_remove.indexOf(servershell.order_by) !== -1) {
            servershell.order_by = 'object_id';
        }

        // Now trigger reload with all changes at once
        servershell.shown_attributes = shown_attributes;
    },
    bookmark: function(name) {
        if (!name) {
            servershell.alert('Missing name for bookmark', 'warning');
            return;
        }

        localStorage.setItem('bookmark.' + name, servershell.shown_attributes);
        servershell.alert(`Bookmark ${name} saved.`, 'success');
    },
    delbookmark: function(name) {
        if (!name) {
            servershell.alert('Missing name for bookmark', 'warning');
            return;
        }

        localStorage.removeItem('bookmark.' + name);
        servershell.alert(`Bookmark ${name} deleted.`, 'success');
    },
    loadbookmark: function(name) {
        let attribute_ids = localStorage.getItem('bookmark.' + name);
        if (attribute_ids) {
            servershell.shown_attributes = attribute_ids.split(',');
            servershell.alert(`Bookmark ${name} loaded.`, 'success');
        }
    },
    orderby: function(attribute_id) {
        if (!servershell.attributes.find(a => a.attribute_id === attribute_id)) {
            servershell.alert(`Attribute ${name} does not exist!`, 'warning');
            return;
        }

        if (servershell.order_by === attribute_id) {
            // Avoid unnecessary reload
            return;
        }
        else {
            servershell.order_by = attribute_id;
        }

        // Attribute not visible yet ...
        if (!servershell.shown_attributes.includes(attribute_id)) {
            servershell.shown_attributes.push(attribute_id);
        }
        else {
            servershell.submit_search();
        }
    },
    export: function(attribute_ids) {
        if (!validate_selected()) {
            return;
        }

        if (attribute_ids.length > 0) {
            attribute_ids = attribute_ids.split(',').map(a => a.trim()).filter(a => a !== '');
        } else {
            // if no attributes are passed, export all selected ones
            attribute_ids = servershell.shown_attributes;
        }

        let unknown = attribute_ids.filter(a => servershell.attributes.find(b => b.attribute_id === a) === undefined);
        if (unknown.length > 0) {
            return servershell.alert(`The attribute(s) ${unknown.join(', ')} does not exist!`, 'warning');
        }

        // If no attributes are given add hostname as default
        if (attribute_ids.length === 0) {
            attribute_ids = ['hostname']
        }

        // Add not yet visible attributes ...
        let to_add = attribute_ids.filter(a => servershell.shown_attributes.find(b => b === a) === undefined);
        servershell.shown_attributes.splice(servershell.shown_attributes.length, 0, ...to_add);

        $(document).one('servershell_search_finished', function() {
            let to_export = '';
            let selected = servershell.get_selected();
            let servers = servershell.servers.filter(s => selected.includes(s.object_id));
            servers.forEach(function(object) {
                attribute_ids.forEach(function(attribute_id) {
                    if (object.hasOwnProperty(attribute_id)) {
                        let attribute = servershell.get_attribute(attribute_id);
                        if (attribute.multi) {
                            to_export += object[attribute_id].join(',');
                        }
                        else {
                            to_export += object[attribute_id];
                        }
                    }
                    to_export += ';'
                });
                to_export += '\n';
            });

            $('#export_text').val(to_export);
            $('#modal_export').modal('show');
        });
    },
    selectall: function() {
        $('#result_table input[name=server]').each((i,e) => e.checked = true);
    },
    unselectall: function() {
        $('#result_table input[name=server]').each((i,e) => e.checked = '');
    },
    select: function(selection) {
        selection.split(',').forEach(function(number) {
            let range = number.split('-');
            let start = parseInt(range[0]);
            let stop = parseInt(range.length === 1 ? range[0] : range[1]);
            let checkboxes = $('#result_table input[name=server]');
            checkboxes.slice(start - 1 - servershell.offset, stop - servershell.offset).click();
        })
    },
    graph: function() {
        if (!validate_selected()) {
            return;
        }

        let query_string = servershell.get_selected().map(o => `object_id=${o}`).join('&');
        let url = servershell.urls.graphite + '?' + query_string;
        window.open(url, '_blank');

        servershell.alert('Opened graph results in new browser tab.', 'info');
    },
    inspect: function() {
        if (!validate_selected()) {
            return;
        }

        servershell.get_selected().forEach(function(object_id) {
           let url = servershell.urls.inspect + `?object_id=${object_id}`;
           window.open(url, '_blank');

           servershell.alert(`Opened ${object_id} inspection in new browser tab.`, 'info');
        });
    },
    edit: function() {
        if (!validate_selected()) {
            return;
        }

        servershell.get_selected().forEach(function(object_id) {
            let url = servershell.urls.edit + `?object_id=${object_id}`;
            window.open(url, '_blank');

            servershell.alert(`Opened ${object_id} for editing in new browser tab.`, 'info');
        });
    },
    new: function(servertype_id) {
        let url = servershell.urls.new + `?servertype=${servertype_id}`;
        window.open(url, '_self');
    },
    clone: function() {
        if (!validate_selected(1, 1)) {
            return;
        }

        let url = servershell.urls.clone + `?object_id=${servershell.get_selected()[0]}`;
        window.open(url, '_self');
    },
    changes: function() {
        let url;
        let selection = servershell.get_selected();
        if (selection.length > 0) {
            url = servershell.urls.changes + `?object_id=${selection[0]}`;
        }
        else {
            url = servershell.urls.changes;
        }

        window.open(url, '_blank');
        servershell.alert('Opened changes in new browser tab.', 'info');
    },
    delete: function() {
        if (!validate_selected()) {
            return;
        }

        servershell.get_selected().forEach(function(object_id) {
            // Avoid duplicate deletion ...
            if (!servershell.to_commit.deleted.includes(object_id)) {
                servershell.to_commit.deleted.push(object_id);
                servershell.update_result();
            }
        });
    },
    setattr: function(attribute_value_string) {
        if (!validate_selected()) {
            return;
        }

        let [attribute_id, new_value] = attribute_value_string.split('=', 2).map(a => a.trim());
        let attribute = servershell.get_attribute(attribute_id);
        if (!attribute) {
            servershell.alert(`Attribute ${attribute_id} does not exist`, 'warning');
            return;
        }

        if (attribute.multi) {
            servershell.alert(`${attribute_id} IS a multi attribute use, multiadd and multidel commands`, 'warning');
            return;
        }

        // User wants to type false but mean '' (empty string) which casts to false
        new_value = attribute.type === 'boolean' && (new_value === 'false' || new_value === '0') ? '' : new_value;

        // Attribute not visible yet ...
        if (!servershell.shown_attributes.includes(attribute_id)) {
            servershell.shown_attributes.push(attribute_id);

            // Wait for attribute to be available in servers property ...
            $(document).one('servershell_search_finished', function() {
                // Try not to set new values for objects which do not have the attribute ...
                let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
                if (new_value === '') {
                    editable.forEach(o => servershell.delete_attribute(o, attribute_id));
                }
                else {
                    editable.forEach(o => servershell.update_attribute(o, attribute_id, new_value));
                }
                servershell.update_result();
            });
        }
        else {
            // Try not to set new values for objects which do not have the attribute ...
            let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
            if (new_value === '') {
                editable.forEach(o => servershell.delete_attribute(o, attribute_id));
            }
            else {
                editable.forEach(o => servershell.update_attribute(o, attribute_id, new_value));
            }
            servershell.update_result();
        }
    },
    multiadd: function(attribute_values_string) {
        if (!validate_selected()) {
            return;
        }

        [attribute_id, values] = attribute_values_string.split('=', 2).map(a => a.trim());
        let to_add = values.split(',').map(v => v.trim());
        let attribute = servershell.get_attribute(attribute_id);
        if (!attribute) {
            servershell.alert(`Attribute ${attribute_id} does not exist`, 'warning');
            return;
        }

        if (!attribute.multi) {
            servershell.alert(`${attribute_id} IS NOT a multi attribute, use setattr and delattr commands`, 'warning');
            return;
        }

        let merge_changes = function() {
            let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
            editable.forEach(function(object_id) {
                let object = servershell.get_object(object_id);
                let values = object[attribute_id];

                // Merge previous changes with current ones
                let changes = servershell.get_changes(object, attribute);
                if (changes !== false) {
                    values = values.filter(v => !changes['remove'].includes(v));
                    values = values.concat(changes['add']);
                }

                // Now add values which should be added
                values = values.concat(to_add);

                servershell.update_attribute(object_id, attribute_id, values);
            });
            servershell.update_result();
        };

        // Attribute not visible yet ...
        if (!servershell.shown_attributes.includes(attribute_id)) {
            servershell.shown_attributes.push(attribute_id);

            // Wait for attribute to be available in servers property ...
            $(document).one('servershell_search_finished', merge_changes);
        }
        else {
           merge_changes();
        }
    },
    multidel: function(attribute_values_string) {
        if (!validate_selected()) {
            return;
        }

        [attribute_id, values] = attribute_values_string.split('=', 2).map(a => a.trim());
        let to_remove = values.split(',').map(v => v.trim());

        // Parse values to separate exact matches from regex patterns
        let exact_matches = [];
        let regex_patterns = [];
        const regexp_pattern = /^Regexp\((.+)\)$/i;

        for (let v of to_remove) {
            let match = v.match(regexp_pattern);
            if (match) {
                try {
                    regex_patterns.push(new RegExp(match[1]));
                } catch (e) {
                    servershell.alert(`Invalid regex pattern: ${match[1]}`, 'warning');
                    return;
                }
            } else {
                exact_matches.push(v);
            }
        }

        let attribute = servershell.get_attribute(attribute_id);
        if (!attribute) {
            servershell.alert(`Attribute ${attribute_id} does not exist`, 'warning');
            return;
        }

        if (!attribute.multi) {
            servershell.alert(`${attribute_id} IS NOT a multi attribute, use setattr and delattr commands`, 'warning');
            return;
        }

        let merge_changes = function() {
            let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
            editable.forEach(function(object_id) {
                let object = servershell.get_object(object_id);
                let values = object[attribute_id];

                // Merge previous changes with current ones
                let changes = servershell.get_changes(object, attribute);
                if (changes !== false) {
                    values = values.filter(v => !changes['remove'].includes(v));
                    values = values.concat(changes['add']);
                }

                // Now remove values matching exact or regex patterns
                values = values.filter(v => {
                    if (exact_matches.includes(v)) return false;
                    if (regex_patterns.some(re => re.test(v))) return false;
                    return true;
                });

                servershell.update_attribute(object_id, attribute_id, values);
            });
            servershell.update_result();
        };

        // Attribute not visible yet ...
        if (!servershell.shown_attributes.includes(attribute_id)) {
            servershell.shown_attributes.push(attribute_id);

            // Wait for attribute to be available in servers property ...
            $(document).one('servershell_search_finished', merge_changes);
        }
        else {
           merge_changes();
        }
    },
    delattr: function(attribute_id) {
        if (!validate_selected()) {
            return;
        }

        let attribute = servershell.get_attribute(attribute_id);
        if (!attribute) {
            servershell.alert(`Attribute ${attribute_id} does not exist`, 'warning');
            return;
        }

        if (!servershell.shown_attributes.includes(attribute_id)) {
            servershell.shown_attributes.push(attribute_id);

            $(document).one('servershell_search_finished', function() {
                // Try not to set new values for objects which do not have the attribute ...
                let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
                editable.forEach(o => servershell.delete_attribute(o, attribute_id));
                servershell.update_result();
            });
        }
        else {
            // Try not to set new values for objects which do not have the attribute ...
            let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
            editable.forEach(o => servershell.delete_attribute(o, attribute_id));
            servershell.update_result();
        }
    },
    history: function(attribute_id) {
        if (!validate_selected(1, 1)) {
            return;
        }

        let object_id = servershell.get_selected()[0];
        let url = servershell.urls.history + `?object_id=${object_id}`;

        if (attribute_id) {
            url += `&attribute_filter=${attribute_id}`;
        }

        window.open(url, '_blank');

        servershell.alert(`History for ${object_id} opened in a new tab`, 'success');
    },
    commit: function() {
        spinner.enable('commit');
        let settings = {
            type: 'POST',
            url: servershell.urls.commit,
            data: {'commit': JSON.stringify(servershell.to_commit)},
            headers: {'X-CSRFToken': Cookies.get('csrftoken')},
            success: function (response) {
                if (response.status === 'error') {
                    servershell.alert(response.message, 'danger', false);
                }
                else {
                    servershell.alert('Data successfully committed!', 'success');
                    servershell.to_commit = {deleted: [], changes: {}};
                    servershell.submit_search();
                }
            },
        };
        $.post(settings).fail(function() {
            servershell.alert('Commit request failed retrying in 5 seconds!', 'danger');
            setTimeout(servershell.commands.commit, 5000);
        }).always(function() {
            spinner.disable('commit');
        });
    },
    cancel: function() {
        if (servershell._ajax === null) {
            servershell.alert('No running request to cancel', 'warning');
            return;
        }

        servershell._ajax.fail = function() {};
        servershell._ajax.abort();
        servershell.alert('Pending request cancelled', 'success');
    },
    diff: function(attribute_ids) {
        if (!validate_selected(2)) {
            return;
        }

        attribute_ids = attribute_ids.split(',').map(a => a.trim()).filter(a => a !== '');
        let unknown = attribute_ids.filter(a => servershell.attributes.find(b => b.attribute_id === a) === undefined);

        if (unknown.length > 0) {
            servershell.alert(`The attribute(s) ${unknown.join(', ')} does not exist!`, 'warning');
            return;
        }

        let objects = servershell.get_selected().map(o => `object=${o}`).join('&');
        let attrs = attribute_ids.map(a => `attr=${a}`).join('&');
        let url = servershell.urls.diff + '?' + objects + '&' + attrs;

        window.open(url, '_blank');
    },
    sum: function(attribute_id) {
        if (!validate_selected()) {
            return;
        }
        let attribute = servershell.get_attribute(attribute_id);
        if (!attribute) {
            servershell.alert(`Attribute ${attribute_id} does not exist`, 'warning');
            return;
        }
        if (attribute.type !== 'number') {
            servershell.alert(`Attribute ${attribute_id} is not a number`, 'warning');
            return;
        }
        // Add not yet visible attributes ...
        let to_add = [attribute_id].filter(a => servershell.shown_attributes.find(b => b === a) === undefined);
        servershell.shown_attributes.splice(servershell.shown_attributes.length, 0, ...to_add);

        $(document).one('servershell_search_finished', function() {
            let sum = 0;
            let selected = servershell.get_selected();
            let servers = servershell.servers.filter(s => selected.includes(s.object_id));
            servers.forEach(function(object) {
                if (object.hasOwnProperty(attribute_id)) {
                    sum += isNaN(object[attribute_id]) ? 0 : object[attribute_id];
                }
            });

            $('#sum_text').text(sum);
            $('#sum_attribute_text').text(attribute_id);
            $('#modal_sum').modal('show');
        });
    }
};

/**
 * Tries to run the command specified in the #command input.
 * Returns true if the input should be cleared
 *
 * @returns {boolean}
 */
function execute_command() {
    let command = servershell.command.split(' ', 1).pop();
    let params = servershell.command.substring(command.length).trim();
    if (Object.keys(servershell.commands).includes(command)) {
        servershell.commands[command](params);

        return true;
    }

    if (servershell.command.match(/^([0-9]+(,|-|\s)?([0-9]+)?)+$/)) {
        // User specified a one, more or a range of servers to select
        servershell.commands.select(servershell.command);

        return true;
    }

    let [attribute_name, value] = servershell.command.split('=');
    let attribute = servershell.attributes.find(attribute => attribute.attribute_id === attribute_name.trim());

    if (attribute && !value) {
        servershell.commands.attr(servershell.command);

        return true;
    }

    if (attribute && value && attribute.multi) {
        servershell.commands.multiadd(servershell.command);

        return true;
    }

    if (attribute && value && !attribute.multi) {
        servershell.commands.setattr(servershell.command);

        return true;
    }

    // User had a nervous finger lets ignore this
    if (command !== '') {
        servershell.alert(`Unknown command ${command}!`, 'warning');
    }

    return false;
}

$(document).ready(function() {

    // Gather description for custom commands from Servershell plugins and add
    // them to the help modal.
    servershell.commands_help.forEach(function(command_help) {
        let row = document.createElement("tr");
        row.id = `cmd-${command_help["command"]}`;

        for (let index of ["command", "arguments", "description"]) {
            let cell = document.createElement("td");
            cell.innerText = command_help[index];
            row.appendChild(cell);
        }

        $("#help_command").append(row);
    });

    $('#command_form').submit(function(event) {
        event.preventDefault();

        // Workaround:
        //
        // The input change event is not fired or somehow interrupted in
        // Safari, Epihany and other like browsers, they all have in common to
        // have "AppleWebKit/605.1.15" in the user agent.
        //
        // We just trigger the event manually here to make it work for those.
        // This will fire it twice for other browser but that does not harm.
        $('#command').change();

       if (execute_command()) {
           servershell.command = '';
       }
    });
});
