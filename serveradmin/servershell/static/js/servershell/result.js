/**
 * Update Table HTML with latest results
 *
 * Update table header and body html whenever the result has changes.
 */
servershell.update_result = function() {
    spinner.enable();

    let table = $('#result_table');
    let selected = servershell.get_selected();

    let header = table.find('thead tr');
    header.empty(''); // reset html ...
    header.append('<th scope="col"></th>');
    header.append('<th scope="col">#</th>');
    servershell.shown_attributes.forEach(function(attribute) {
        header.append(`<th scope="col">${attribute}</th>`);
    });

    let body = table.find('tbody');
    body.empty(); // reset html
    servershell.servers.forEach((object, number) => body.append(get_row_html(object, number)));

    // Restore previous selection
    servershell.set_selected(selected);

    let info = `Results (${servershell.num_servers} servers, page ${servershell.page()}/${servershell.pages()})`;
    $('div.result_info').html(info);

    spinner.disable();
};

/**
 * Get selected rows in result table
 *
 * Returns a list of object_ids from the currently selected rows in the result
 * table.
 *
 * @returns {jQuery}
 */
servershell.get_selected = function() {
    return $.map($('#result_table input[name=server]:checked'), function(element) {
        return parseInt(element.value);
    });
};

/**
 * Set selected rows in result table
 *
 * Mark the rows with the given object_id in result table as selected.
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
 * Get row HTML
 *
 * Returns the row HTML for the given object which includes all necessary
 * CSS styles and changes made visible.
 *
 * @param object
 * @param number
 * @returns {jQuery|HTMLElement}
 */
get_row_html = function(object, number) {
    let row = $(`<tr data-oid="${object.object_id}"></tr>`);

    // Mark row as deleted (red) if it is about to get deleted with the next
    // commit. Otherwise color it depending on its state (see state.css).
    // It is important that delete wins here otherwise the user would not be
    // able to see which objects get deleted.
    if (servershell.to_commit.deleted.includes(object.object_id))
        row.addClass('delete');
    else if (object.hasOwnProperty('state'))
        row.addClass(`state-${object.state}`);

    // Standard columns which should always be present
    row.append(`<td><input type="checkbox" name="server" value="${object.object_id}"/></td>`);
    row.append(`<td>${number + 1 + servershell.offset}</td>`);

    let changes = servershell.to_commit.changes;
    servershell.shown_attributes.forEach(function (attribute_id) {
        // Not all objects (servertypes) have all attributes e.g. a loadbalancer has no hypervisor
        if (object.hasOwnProperty(attribute_id) && object[attribute_id] !== null) {
            let object_id = object.object_id;
            let server = servershell.get_object(object_id);
            let attribute = servershell.get_attribute(attribute_id);
            let cell = $(`<td data-attr="${attribute_id}" data-value="${object[attribute_id]}"></td>`);

            let change = object_id in changes && attribute_id in changes[object_id] ? changes[object_id][attribute_id] : null;
            if (change) {
                if (attribute.multi) {
                    let to_add = change.add.join(', ');
                    let to_delete = change.remove.join(', ');
                    let current_value = server[attribute_id].filter(v => !to_delete.includes(v)).join(', ');

                    cell.html(`${current_value} <del>${to_delete}</del> <u>${to_add}</u>`)
                } else {
                    cell.html(`<del>${change.old}</del>&nbsp;<u>${change.new}</u>`);
                }
            }
            else {
                if (attribute.multi)
                    cell.html(object[attribute_id].join(', '));
                else
                    cell.html(object[attribute_id]);
            }

            register_inline_editing(cell);
            row.append(cell);
        }
        else {
            row.append(`<td class="disabled"></td>`);
        }
    });

    return row;
};

/**
 * Make row editable by double click
 *
 * This will add the inline edit functionality which allows us to double
 * click a cell manipulate it in a input or textarea and save it. This
 * is the same as the multiadd, multidell, setattr commands.
 *
 * @param cell jQuery td element
 */
register_inline_editing = function(cell) {
    cell.dblclick(function (event) {
        let cell = $(event.target);
        let row = cell.parent();
        let object_id = row.data('oid');
        let object = servershell.get_object(object_id);
        let attribute_id = cell.data('attr');
        let attribute = servershell.get_attribute(attribute_id);

        // Select row for convenience ...
        if (!servershell.get_selected().includes(object_id))
            row.children('td:first').children('input').click();

        let current_value;
        let changes = servershell.to_commit.changes;
        if (object_id in changes && attribute_id in changes[object_id]) {
            if (attribute.multi) {
                current_value = object[attribute_id].filter(v => !changes[object_id][attribute_id].remove.includes(v));
                current_value = current_value.concat(changes[object_id][attribute_id].add);
            } else {
                current_value = changes[object_id][attribute_id].new;
            }
        } else {
            current_value = servershell.get_object(object_id)[attribute_id];
        }

        let content;
        if (attribute.multi)
            content = $(`<textarea rows="5" cols="30">${current_value.join('\n')}</textarea>`);
        else
            content = $(`<input type="text" value="${current_value}" />`);

        content.data('oid', object_id);
        content.data('aid', attribute_id);
        content.data('multi', attribute.multi);

        let button = $('<button class="btn btn-success btn-sm">save</button>');
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
            if (multi) {
                let current_value = servershell.get_object(object_id)[attribute_id];
                let to_add = value.filter(v => !current_value.includes(v));
                let to_remove = current_value.filter(v => !value.includes(v));
                update_attribute(object_id, attribute_id, to_add);
                update_attribute(object_id, attribute_id, to_remove, 'remove');
            }
            else {
                update_attribute(object_id, attribute_id, value);
            }

            servershell.update_result();
        });
        cell.html(content);
        cell.append(button);
    });
};

$(document).ready(function() {
    // Update result table as soon as we have new data ...
    $(document).on('servershell_search_finished', servershell.update_result);
});
