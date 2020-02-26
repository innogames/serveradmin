/**
 * Update Table HTML with latest results
 *
 * Update table header and body html whenever the result has changes.
 */
update_result = function() {
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
    servershell.servers.forEach(function(object, number) {
        let row = $(`<tr data-oid="${object.object_id}"></tr>`);

        if (object.hasOwnProperty('state'))
            row.addClass(`state-${object.state}`);

        row.append(`<td><input type="checkbox" name="server" value="${object.object_id}"/></td>`);
        row.append(`<td>${number + 1 + servershell.offset}</td>`);
        servershell.shown_attributes.forEach(function (attribute) {
            if (object.hasOwnProperty(attribute) && object[attribute] !== null) {
                let column = `<td data-attr="${attribute}" data-value="${object[attribute]}">`;
                column += object[attribute];
                column += '</td>';
                row.append(column);
            } else {
                row.append(`<td class="disabled"></td>`);
            }
        });
        body.append(row);
    });

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

$(document).ready(function() {
    // Update result table as soon as we have new data ...
    $(document).on('servershell_search_finished', function() {
        // Keep selection on reload of search ...
        let selected = servershell.get_selected();
        update_result();
        servershell.set_selected(selected);
    });

    $(document).on('', function() {

    });
});
