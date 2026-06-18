$(document).ready(function() {
    // Update servershell object shown_attributes property on (un)selection
    // of attributes which will also submit the search again.
    $('[data-servershell-attribute]').on('change', function(event) {
        let attribute_id = $(event.target).data('servershell-attribute');
        let index = servershell.shown_attributes.indexOf(attribute_id);

        if (!event.target.checked && index > -1)
            servershell.shown_attributes.splice(index, 1);
        else if (event.target.checked && index === -1)
            servershell.shown_attributes.push(attribute_id);
    });

    // If the servershell object shown_attributes property changes keep the
    // (un)select the attributes list as well.
    $(document).on('servershell_property_set_shown_attributes', function() {
        // Reset checkbox selection
        $('#accordion-attributes input[type=checkbox]').each(function(i, e) {
            e.checked = '';
        });

        servershell.shown_attributes.forEach(function(attribute_id) {
            $(`input[data-servershell-attribute=${attribute_id}]`)[0].checked = 'true';
        });
    });
});