/**
 * Render modal to choose ip address
 *
 * Renders a modal where one can choose the ip address for a host
 *
 * @param intern_ip e.g. 10.0.0.1
 */
servershell.choose_ip_address = function(params) {
    spinner.enable('choose_ip_address');
    $.get(servershell.urls.choose_ip_address, params, function(html) {
        let modal = $('#modal_choose_ip_address');

        $('#modal_choose_ip_address .modal-body').html(html);
        $(modal).modal('show');
    }).always(function() {
        spinner.disable('choose_ip_address');
    });
};

let submit_ip_address = function(new_value) {
    $('input[name="attr_intern_ip"]').val(new_value);
    $('.modal').modal('hide');
};

let search = function(search_term) {
    let search_elements = $('#modal_choose_ip_address [data-search-values]');

    if (!search_term) {
        search_elements.css('display', '');

        return;
    }

    search_elements.css('display', 'none');
    $(`#modal_choose_ip_address [data-search-values*="${search_term}"]`).css('display', '');
};
