/**
 * Update Table HTML with latest results
 *
 * Update table header and body html whenever the result has changes.
 */
let update_result = function() {
    spinner.enable();

    let table = $('#result_table');

    let header = table.find('thead tr');
    header.empty(''); // reset html ...
    header.append('<th scope="col"></th>');
    header.append('<th scope="col">#</th>');
    servershell.shown_attributes.forEach(function(attribute) {
        header.append(`<th scope="col">${attribute}</th>`);
    });

    let body = table.find('tbody');
    body.empty(); // reset html ...
    servershell.servers.forEach(function(object, number) {
        let row = $('<tr></tr>');
        row.append(`<td><input type="checkbox" name="server" value="${object.object_id}"/></td>`);
        row.append(`<td>${number + 1 + servershell.offset}</td>`);
        servershell.shown_attributes.forEach(function (attribute) {
            if (object.hasOwnProperty(attribute) && object[attribute]) {
                row.append(`<td>${object[attribute]}</td>`);
            } else {
                row.append(`<td class="disabled"></td>`);
            }
        });
        body.append(row);
    });

    let info = `Results (${servershell.num_servers} servers, page ${servershell.page()}/${servershell.pages()})`;
    $('div.result_info').html(info);

    spinner.disabled();
};

$(document).ready(function() {
    // Update result table as soon as we have new data ...
    $(document).on('servershell_property_set_servers', function() {
        update_result();
    })
});
