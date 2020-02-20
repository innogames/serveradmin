$(document).ready(function() {
    // Update servershell object shown_attributes property on (un)selection
    // of attributes which will also submit the search again.
    $('[data-servershell-attribute]').on('change', function(event) {
        let attribute_id = $(event.target).data('servershell-attribute');
        let index = servershell.shown_attributes.indexOf(attribute_id);

        if (index > -1)
            servershell.shown_attributes.splice(index, 1);
        else
            servershell.shown_attributes.push(attribute_id);
    });

    // If the servershell object shown_attributes property changes keep the
    // (un)select the attributes list as well.
    let events = [
        'servershell_property_set_shown_attributes',
        'servershell_property_push_shown_attributes',
        'servershell_property_splice_shown_attributes',
    ];
    $(document).on(events.join(' '), function() {
        servershell.shown_attributes.forEach(function(attribute_id) {
            $(`input[data-servershell-attribute=${attribute_id}]`).attr('checked', true);
        });
    });
});