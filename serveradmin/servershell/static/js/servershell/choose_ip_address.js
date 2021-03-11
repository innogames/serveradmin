/**
 * Render modal to choose ip address
 *
 * Renders a modal where one can choose the ip address for a host
 *
 * @param intern_ip e.g. 10.0.0.1
 */
servershell.choose_ip_address = function(intern_ip) {
    let data = {
        network: intern_ip,
        async: false,
    };

    spinner.enable();
    $.get(servershell.urls.choose_ip_address, data, function(html) {
        let modal = $('#modal_choose_ip_address');

        $('#modal_choose_ip_address .modal-body').html(html);
        $(modal).modal('show');
    }).always(function() {
        spinner.disable();
    });
};

let submit_ip_address = function(new_value) {
    $('input[name="attr_intern_ip"]').val(new_value);
    $('.modal').modal('hide');
};