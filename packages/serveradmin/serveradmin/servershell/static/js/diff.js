let toggle_diff = function(element) {
    let button = $(element);

    if (button.attr('aria-pressed') === 'true') {
        $('tbody tr').show();
    }
    else {
        $('tbody tr').hide();
        $('tbody td.diff').parent('tr').show();
    }
};
