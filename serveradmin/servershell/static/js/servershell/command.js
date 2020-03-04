/**
 * Update (multi) attribute values
 *
 * Adds or removes values for the given object no matter if it is a multi
 * attribute or a normal single value attribute. It will detect if multi
 * changes nullify each other (mostly) and remove the changes to commit
 * no changes to backend.
 *
 * This method does NOT validate anything in any way. You must have checked
 * if the object, attribute and values before hand.
 *
 * @param object_id e.g. 123456
 * @param attribute_id  e.g. state or responsible_admin
 * @param new_value e.g. maintenance or ['john.doe', 'doe.john']
 * @param multi_action add or delete (only relevant for multi attribute)
 */
servershell.update_attribute = function(object_id, attribute_id, new_value, multi_action = 'add') {
    let attribute = servershell.get_attribute(attribute_id);
    let changes = servershell.to_commit.changes;
    let server = servershell.get_object(object_id);

    if (!changes.hasOwnProperty(object_id))
        changes[object_id] = {};

    if (!changes[object_id].hasOwnProperty(attribute_id)) {
        if (attribute.multi)
            changes[object_id][attribute_id] = {'action': 'multi'};
        else
            changes[object_id][attribute_id] = {'action': 'update'};
    }

    let change = changes[object_id][attribute_id];
    if (attribute.multi) {
        let new_value_add;
        let new_value_remove;

        // For multi attributes we want to merge changes of previous commands
        if (multi_action === 'add') {
            // Don't add values which are already in last commit ...
            new_value_add = new_value.filter(v => !server[attribute_id].includes(v));
            // Don't remove values which should not be added but keep the rest ...
            new_value_remove = 'remove' in change ? change.remove.filter(v => !new_value.includes(v)) : [];
        }
        else {
            // Don't remove values which are not present in last commit ...
            new_value_remove = new_value.filter(v => server[attribute_id].includes(v));
            // Don't add values which should be removed but keep the rest ...
            new_value_add = 'add' in change ? change.add.filter(v => !new_value.includes(v)) : [];
        }

        change['add'] = new_value_add.sort();
        change['remove'] = new_value_remove.sort();
    }
    else {
        change['new'] = new_value;
        change['old'] = server[attribute_id];
    }

    // If the sum of changes change nothing do nothing ...
    if (attribute.multi) {
        let attr_changes = server[attribute_id];
        let final_changes = server[attribute_id]
            .filter(v => !change['remove'].includes(v))
            .concat(change['add'].filter(v => !server[attribute_id].includes(v)));
        if (attr_changes.every(v => final_changes.includes(v)) && final_changes.every(v => attr_changes.includes(v)))
            delete changes[object_id][attribute_id];
    } else {
        if (change['new'] === change['old'])
            delete changes[object_id][attribute_id];
    }

    // If there are no changes for the object remove it from to_commit to
    // avoid possible request to backend ...
    if (Object.keys(changes[object_id]).length === 0) {
            delete changes[object_id];
            servershell.to_commit.changes = changes;
    } else {
        changes[object_id][attribute_id] = change;
        servershell.to_commit.changes = changes;
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

    if (!servershell.to_commit.changes.hasOwnProperty(object_id))
        servershell.to_commit.changes[object_id] = {};

    if (!servershell.to_commit.changes[object_id].hasOwnProperty(attribute_id))
        servershell.to_commit.changes[object_id][attribute_id] = {};

    servershell.to_commit.changes[object_id][attribute_id] = change;
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
    if ((min !== -1 && selected < min) || (max !== -1 && selected.length > max)) {
        servershell.alert(`Select at least ${min} and at most ${max} objects`, 'warning');
        return false;
    }

    return true;
}

servershell.commands = {
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
        if (isNaN(limit) || limit < 0) {
            servershell.alert(`${limit} must be a number greater zero!`, 'warning');
            return;
        }

        if (limit > 100)
            servershell.alert('Do you really need to view that many objects at once ?', 'warning');

        servershell.limit = Math.abs(limit);
        servershell.submit_search();
    },
    attr: function(attribute_ids) {
        attribute_ids = attribute_ids.split(',').map(a => a.trim());
        let unknown = attribute_ids.filter(a => servershell.attributes.find(b => b.attribute_id === a) === undefined);

        if (unknown.length > 0) {
            servershell.alert(`The attribute(s) ${unknown.join(', ')} doe not exist!`, 'warning');
            return;
        }

        // Avoid reloading by working with a copy
        let shown_attributes = servershell.shown_attributes;
        let to_remove = attribute_ids.filter(a => shown_attributes.find(b => b === a) !== undefined);
        let to_add = attribute_ids.filter(a => shown_attributes.find(b => b === a) === undefined);
        shown_attributes = shown_attributes.filter(a => !to_remove.includes(a));
        shown_attributes.splice(shown_attributes.length, 0, ...to_add);

        // Now trigger reload with all changes at once
        servershell.shown_attributes = shown_attributes;
    },
    orderby: function(attribute_id) {
        if (servershell.attributes.find(a => attribute_id === attribute_id)) {
            servershell.alert(`Attribute ${name} does not exist!`, 'warning');
            return;
        }

        // Avoid unnecessary reload ...
        if (servershell.order_by !== attribute_id) {
            servershell.order_by = attribute_id;
            servershell.submit_search();
        }
    },
    export: function(attribute_ids) {
        attribute_ids = attribute_ids.split(',').map(a => a.trim());
        let unknown = attribute_ids.filter(a => servershell.attributes.find(b => b.attribute_id === a) === undefined);

        if (unknown.length > 0) {
            servershell.alert(`The attribute(s) ${unknown.join(', ')} doe not exist!`, 'warning');
            return;
        }

        // Add not yet visible attributes ...
        let to_add = attribute_ids.filter(a => servershell.shown_attributes.find(b => b === a) === undefined);
        servershell.shown_attributes.splice(servershell.shown_attributes.length, 0, ...to_add);

        $(document).one('servershell_search_finished', function() {
            let to_export = '';
            servershell.servers.forEach(function(object) {
                attribute_ids.forEach(function(attribute_id) {
                    if (object.hasOwnProperty(attribute_id)) {
                        let attribute = servershell.get_attribute(attribute_id);
                        if (attribute.multi)
                            to_export += object[attribute_id].join(',');
                        else
                            to_export += object[attribute_id];
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
            checkboxes.slice(start - 1, stop).click();
        })
    },
    graph: function() {
        if (!validate_selected())
            return;

        let query_string = servershell.get_selected().map(o => `object_id=${o}`).join('&');
        let url = servershell.urls.graphite + '?' + query_string;
        window.open(url, '_blank');

        servershell.alert('Opened graph results in new browser tab.', 'info');
    },
    inspect: function() {
        if (!validate_selected())
            return;

        servershell.get_selected().forEach(function(object_id) {
           let url = servershell.urls.inspect + `?object_id=${object_id}`;
           window.open(url, '_blank');

           servershell.alert(`Opened ${object_id} inspection in new browser tab.`, 'info');
        });
    },
    edit: function() {
        if (!validate_selected())
            return;

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
        if (!validate_selected(1, 1))
            return;

        let url = servershell.urls.clone + `?object_id=${servershell.get_selected()[0]}`;
        window.open(url, '_self');
    },
    changes: function() {
        if (!validate_selected())
            return;

        let url;
        let selection = servershell.get_selected();
        if (selection.length > 0)
            url = servershell.urls.changes + `?object_id=${selection[0]}`;
        else
            url = servershell.urls.change;

        window.open(url, '_blank');
        servershell.alert('Opened changes in new browser tab.', 'info');
    },
    delete: function() {
        if (!validate_selected())
            return;

        servershell.get_selected().forEach(function(object_id) {
            // Avoid duplicate deletion ...
            if (!servershell.to_commit.deleted.includes(object_id)) {
                servershell.to_commit.deleted.push(object_id);
                servershell.update_result();
            }
        });
    },
    setattr: function(attribute_value_string) {
        if (!validate_selected())
            return;

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

        // Attribute not visible yet ...
        if (!servershell.shown_attributes.includes(attribute_id)) {
            servershell.shown_attributes.push(attribute_id);

            // Wait for attribute to be available in servers property ...
            $(document).one('servershell_search_finished', function() {
                // Try not to set new values for objects which do not have the attribute ...
                let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
                editable.forEach(o => servershell.update_attribute(o, attribute_id, new_value));
                servershell.update_result();
            });
        }
        else {
            // Try not to set new values for objects which do not have the attribute ...
            let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
            editable.forEach(o => servershell.update_attribute(o, attribute_id, new_value));
            servershell.update_result();
        }
    },
    multiadd: function(attribute_values_string) {
        if (!validate_selected())
            return;

        [attribute_id, values] = attribute_values_string.split('=', 2).map(a => a.trim());
        let new_values = values.split(',').map(v => v.trim());
        let attribute = servershell.get_attribute(attribute_id);
        if (!attribute) {
            servershell.alert(`Attribute ${attribute_id} does not exist`, 'warning');
            return;
        }

        if (!attribute.multi) {
            servershell.alert(`${attribute_id} IS NOT a multi attribute, use setattr and delattr commands`, 'warning');
            return;
        }

        // Attribute not visible yet ...
        if (!servershell.shown_attributes.includes(attribute_id)) {
            servershell.shown_attributes.push(attribute_id);

            // Wait for attribute to be available in servers property ...
            $(document).one('servershell_search_finished', function() {
                // Try not to set new values for objects which do not have the attribute ...
                let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
                editable.forEach(o => servershell.update_attribute(o, attribute_id, new_values));
                servershell.update_result();
            });
        }
        else {
            // Try not to set new values for objects which do not have the attribute ...
            let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
            editable.forEach(o => servershell.update_attribute(o, attribute_id, new_values));
            servershell.update_result();
        }
    },
    multidel: function(attribute_values_string) {
        if (!validate_selected())
            return;

        [attribute_id, values] = attribute_values_string.split('=', 2).map(a => a.trim());
        let new_values = values.split(',').map(v => v.trim());
        let attribute = servershell.get_attribute(attribute_id);
        if (!attribute) {
            servershell.alert(`Attribute ${attribute_id} does not exist`, 'warning');
            return;
        }

        if (!attribute.multi) {
            servershell.alert(`${attribute_id} IS NOT a multi attribute, use setattr and delattr commands`, 'warning');
            return;
        }

        // Attribute not visible yet ...
        if (!servershell.shown_attributes.includes(attribute_id)) {
            servershell.shown_attributes.push(attribute_id);

            // Wait for attribute to be available in servers property ...
            $(document).one('servershell_search_finished', function() {
                // Try not to set new values for objects which do not have the attribute ...
                let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
                editable.forEach(o => servershell.update_attribute(o, attribute_id, new_values, 'del'));
                servershell.update_result();
            });
        }
        else {
            // Try not to set new values for objects which do not have the attribute ...
            let editable = servershell.get_selected().filter(object_id => attribute_id in servershell.get_object(object_id));
            editable.forEach(o => servershell.update_attribute(o, attribute_id, new_values, 'del'));
            servershell.update_result();
        }
    },
    delattr: function(attribute_id) {
        if (!validate_selected())
            return;

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
    commit: function() {
        spinner.enable();

        let settings = {
            type: 'POST',
            url: servershell.urls.commit,
            data: {'commit': JSON.stringify(servershell.to_commit)},
            headers: {'X-CSRFToken': Cookies.get('csrftoken')},
            success: function (response) {
                if (response.status === 'error') {
                    servershell.alert(response.message, 'danger', false);
                } else {
                    servershell.alert('Data successfully committed!', 'success');
                    servershell.submit_search();
                    servershell.to_commit = {deleted: [], changes: {}};
                }
            },
            complete: function() {
                spinner.disable();
            }
        };
        $.post(settings);
    }
};

$(document).ready(function() {
   $('#command_form').submit(function(event) {
        event.preventDefault();

        let command = servershell.command.split(' ', 1).pop();
        let params = servershell.command.substring(command.length).trim();
        if (Object.keys(servershell.commands).includes(command)) {
            servershell.commands[command](params);
        }
        else if (servershell.command.match(/^([0-9]+(,|-|\s)?([0-9]+)?)+$/)) {
            // User specified a one, more or a range of servers to select
            servershell.commands.select(servershell.command);
        }
        else {
            // User had a nervous finger lets ignore this
            if (command !== '')
                servershell.alert(`Unknown command ${command}!`, 'warning');

            return;
        }

        servershell.command = '';
   })
});