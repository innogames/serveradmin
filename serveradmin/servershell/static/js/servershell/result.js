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
            let column = $(`<td data-attr="${attribute_id}" data-value="${object[attribute_id]}"></td>`);

            let change = object_id in changes && attribute_id in changes[object_id] ? changes[object_id][attribute_id] : null;
            if (change) {
                if (attribute.multi) {
                    let to_add = change.add.join(', ');
                    let to_delete = change.remove.join(', ');
                    let current_value = server[attribute_id].filter(v => !to_delete.includes(v)).join(', ');

                    column.html(`${current_value} <del>${to_delete}</del> <u>${to_add}</u>`)
                } else {
                    column.html(`<del>${change.old}</del>&nbsp;<u>${change.new}</u>`);
                }
            }
            else {
                if (attribute.multi)
                    column.html(object[attribute_id].join(', '));
                else
                    column.html(object[attribute_id]);
            }
            row.append(column);
        }
        else {
            row.append(`<td class="disabled"></td>`);
        }
    });

    return row;
};

$(document).ready(function() {
    // Update result table as soon as we have new data ...
    $(document).on('servershell_search_finished', servershell.update_result);
});
