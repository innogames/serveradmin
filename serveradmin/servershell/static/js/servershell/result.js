/**
 * Generate HTML for result table
 *
 * Generates and updates the HTML for the result table based on the servershell
 * properties.
 */
servershell.update_result = function() {
    spinner.enable();

    let table = $('#result_table');

    // Memorize currently selected objects to restore
    let selected = servershell.get_selected();

    // Recreate table header
    let header = table.find('thead tr');
    header.empty();
    header.append('<th scope="col"></th>');
    header.append('<th scope="col">#</th>');
    servershell.shown_attributes.forEach((attribute, index) => header.append(`<th scope="col">${attribute}</th>`));

    // Recreate table body
    let body = table.find('tbody');
    body.empty();
    servershell.servers.forEach((object, index) => body.append(get_row_html(object, index + 1)));

    // Restore previous selected objects
    servershell.set_selected(selected);

    // Update result information on top and bottom showing page etc.
    let info = `Results (${servershell.num_servers} servers, page ${servershell.page()}/${servershell.pages()}, ${servershell.limit} per page)`;
    $('div.result_info').html(info);

    // Select first element if there is only one.
    if (servershell.servers.length === 1)
        $('#result_table input[name=server]').each((index, element) => element.checked = true);

    spinner.disable();
};

/**
 * Get HTML for table row
 *
 * Returns the HTML for the result table body row based on the object and row
 * number.
 *
 * @param object
 * @param number
 * @returns {jQuery|HTMLElement}
 */
get_row_html = function(object, number) {
    let row = $('<tr></tr>');
    row.data('oid', object.object_id);

    // Mark row as deleted. Make sure this wins over other colors
    // such as the state otherwise the user will not see objects marked for
    // deletion.
    if (servershell.to_commit.deleted.includes(object.object_id))
        row.addClass('delete');
    else if (object.hasOwnProperty('state'))
        row.addClass(`state-${object.state}`);

    // Standard columns which should always be present
    row.append(`<td><input tabindex="3" type="checkbox" name="server" value="${object.object_id}"/></td>`);
    row.append(`<td>${number + servershell.offset}</td>`);

    let changes = servershell.to_commit.changes;
    servershell.shown_attributes.forEach(function(attribute_id) {
        if (is_editable(object.object_id, attribute_id)) {
            let cell = $('<td></td>');
            cell.data('aid', attribute_id);

            // Some helper variables
            let object_id = object.object_id;
            let attribute = servershell.get_attribute(attribute_id);

            // Changes in to_commit we have to display
            let change;
            if (object_id in changes && attribute_id in changes[object_id])
                change = changes[object_id][attribute_id];

            if (change) {
                if (attribute.multi) {
                    let to_add = change.add.join(', ');
                    let to_delete = change.remove.join(', ');
                    let value = object[attribute_id].filter(v => !to_delete.includes(v)).join(', ');

                    cell.html(`${value} <del>${to_delete}</del> <u>${to_add}</u>`)
                }
                else {
                    let to_delete = change.old === null ? '' : change.old;
                    let new_value = change.new === undefined ? '': change.new;
                    cell.html(`<del>${to_delete}</del>&nbsp;<u>${new_value}</u>`);
                }
            }
            else {
                cell.html(get_string(object_id, attribute_id));
            }

            register_inline_editing(cell);
            row.append(cell);
        }
        else {
            let value = get_string(object.object_id, attribute_id);
            row.append(`<td class="disabled">${value}</td>`);
        }
    });

    return row;
};

/**
 * Get selected objects
 *
 * Get a list of selected object ids based on the HTML checkboxes.
 *
 * @returns Array
 */
servershell.get_selected = function() {
    return $.map($('#result_table input[name=server]:checked'), function(element) {
        return parseInt(element.value);
    });
};

/**
 * Set selected objects
 *
 * Tick the checkbox in the result table HTML for the given object ids.
 *
 * @param object_ids
 */
servershell.set_selected = function(object_ids) {
    let checkboxes = $('#result_table input[name=server]');
    object_ids.forEach(function(object_id) {
        let checkbox = checkboxes.filter(`input[value=${object_id}]`);
        if (checkbox.length)
            checkbox[0].checked = true;
    });
};

/**
 * Check if attribute is editable
 *
 * @param object_id
 * @param attribute_id
 * @returns boolean
 */
is_editable = function(object_id, attribute_id) {
    let object = servershell.get_object(object_id);
    return attribute_id in object && servershell.editable_attributes[object.servertype].includes(attribute_id);
};

/**
 * Get attribute value as string
 *
 * @param object_id
 * @param attribute_id
 * @returns {*}
 */
get_string = function(object_id, attribute_id) {
    let object = servershell.get_object(object_id);
    if (attribute_id in object && object[attribute_id] !== null) {
        if (servershell.get_attribute(attribute_id).multi)
            return object[attribute_id].join(', ');
        else
            return object[attribute_id].toString();
    }

    return '';
};

/**
 * Make row editable by double click
 *
 * This will add the inline edit functionality which allows us to double
 * click a cell manipulate it in a input or textarea and save it. This
 * is the same as the multiadd, multidel, setattr commands.
 *
 * @param cell jQuery td element
 */
register_inline_editing = function(cell) {
    cell.dblclick(function (event) {
        // Do not open another inline edit unless previous is finished
        let previous = $('#inline-edit-save');
        if (previous.length)
            return;

        let cell = $(event.target).closest('td');
        let row = cell.parent();
        let object_id = row.data('oid');
        let object = servershell.get_object(object_id);
        let attribute_id = cell.data('aid');
        let attribute = servershell.get_attribute(attribute_id);

        // Select row for convenience
        if (!servershell.get_selected().includes(object_id))
            row.children('td:first').children('input').click();

        let current_value;
        let changes = servershell.to_commit.changes;
        if (object_id in changes && attribute_id in changes[object_id]) {
            if (attribute.multi) {
                current_value = object[attribute_id].filter(v => !changes[object_id][attribute_id].remove.includes(v));
                current_value = current_value.concat(changes[object_id][attribute_id].add);
            } else {
                if (changes[object_id][attribute_id].action === 'delete') {
                    current_value = '';
                } else {
                    current_value = changes[object_id][attribute_id].new;
                }
            }
        } else {
            current_value = servershell.get_object(object_id)[attribute_id];
        }

        let content;
        if (attribute.multi)
            content = $(`<textarea rows="5" cols="30">${current_value.join('\n')}</textarea>`);
        else
            content = $(`<input type="text" value="${current_value === null ? '' : current_value}" />`);

        // Provide on-the-fly validation
        if ('regex' in attribute && attribute.regex !== null)
            content.data('pattern', attribute.regex);

        content.attr('id', 'inline-edit');
        content.data('oid', object_id);
        content.data('aid', attribute_id);
        content.data('multi', attribute.multi);

        let button = $('<button id="inline-edit-save" class="btn btn-success btn-sm">save</button>');
        button.click(function (event) {
            let value;
            let edit = $(event.target).prev();
            let multi = edit.data('multi');

            if (multi)
                value = edit.val().split('\n').map(v => v.trim()).filter(v => v !== '');
            else
                value = edit.val().trim();

            let object_id = edit.data('oid');
            let attribute_id = edit.data('aid');
            let attribute = servershell.get_attribute(attribute_id);

            // When the user types 'false' use empty string so that it casts to false
            if (attribute.type === 'boolean' && (value === 'false' || value === '0'))
                value = '';

            if (value === '') {
                servershell.delete_attribute(object_id, attribute_id)
            }
            else {
                if (multi) {
                    let current_value = servershell.get_object(object_id)[attribute_id];
                    let to_add = value.filter(v => !current_value.includes(v));
                    let to_remove = current_value.filter(v => !value.includes(v));

                    servershell.update_attribute(object_id, attribute_id, to_add);
                    servershell.update_attribute(object_id, attribute_id, to_remove, 'remove');
                }
                else {
                    servershell.update_attribute(object_id, attribute_id, value);
                }
            }

            servershell.update_result();
        });

        // Hit save button on enter or shift + enter if multi attribute
        $(document).keypress(function(event) {
            if (event.which === 13) {
                let save = $('#inline-edit-save');
                if (save.length) {
                    let type = save.prev().get(0).type;
                    if (type === 'textarea' && event.shiftKey || type === 'text') {
                        event.preventDefault();
                        save.click();
                    }
                }
            }
        });

        cell.html(content);
        cell.append(button);
        cell.append(`<div><b>${attribute.regex !== null ? attribute.regex : 'No Regexp'}</b></div>`);

        // Focus element and place cursor at the end of the text
        content.focus();
        content.get(0).setSelectionRange(-1, -1);
    });
};

$(document).ready(function() {
    // Update result table as soon as we have new data ...
    $(document).on('servershell_search_finished', servershell.update_result);
});
