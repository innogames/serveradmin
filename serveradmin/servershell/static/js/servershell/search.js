/**
 * Submit Search Term
 *
 * Take the current entered search term and the settings such as per_page etc.
 * and submit the query to the Serveradmin backend. On success extract the
 * result to the corresponding servershell properties.
 */
servershell.submit_search = function() {
    // Prevent somebody hitting enter like crazy
    if (servershell._ajax !== null) {
        return servershell.alert('Pending request, cancel it or wait for it to finish!', 'danger');
    }

    let data = {
        term: servershell.term.trimRight(), // Avoid error on trailing spaces
        shown_attributes: servershell.shown_attributes,
        deep_link: servershell.deep_link,
        offset: servershell.offset,
        limit: servershell.limit,
        order_by: servershell.order_by,
        async: false,
        timeout: 5000,
    };

    let url = $('#search_form').get(0).action;
    console.debug(`Submitting query to URL "${url}" with data:`);
    console.debug(data);

    spinner.enable();
    servershell._ajax = $.getJSON(url, data, function(data) {
        if ('message' in data) {
            return servershell.alert(data.message, 'danger');
        }

        // Update property used by bookmark link of search
        servershell.href = '?' + $.param({
            'term': servershell.term,
            'shown_attributes': servershell.shown_attributes,
            'deep_link': true,
        });

        servershell.editable_attributes = data.editable_attributes;
        servershell.num_servers = data.num_servers;
        servershell.servers = data.servers;
        servershell.status = data.status;
        servershell.understood = data.understood;

        // If the search term changes and we exceed the available pages with
        // our current settings then go to page 1
        if (servershell.page() > servershell.pages()) {
            servershell.offset = 0;
        }

        console.debug(`Query result status is: "${data.status}" with data:`);
        console.debug(data);

        // We will use this on other components to react on changes ...
        $(document).trigger('servershell_search_finished');

        // Indicator that we have successfully reloaded ...
        servershell._term = servershell.term;

        // Focus command input after successful search ...
        $('#command').focus();
    }).always(function() {
        spinner.disable();

        // Reset running ajax call variable
        servershell._ajax = null;
    })
};

$(document).ready(function() {
    // 2-Way Data Binding for search, command, understood elements

    // Update input elements when values change by e.g. submitted search
    $(document).on('servershell_property_set', function(event, data) {
        $(`[data-servershell-property-bind=${data.property}]`).val(servershell[data.property]);
    });

    // Update servershell object properties when input element value change
    $('[data-servershell-property-bind]').on('change', function(event) {
        let property = $(event.target).data('servershell-property-bind');
        servershell[property] = event.target.value;
    });

    // ------------------------------------------------------------------------

    // Submit form with Ajax and prevent normal submission
    $('#search_form').submit(function(event) {
        event.preventDefault();
        servershell.submit_search();
    });

    // Reload search if anything relevant changes ...
    let events = [
        'servershell_property_set_shown_attributes',
        'servershell_property_push_shown_attributes',
        'servershell_property_splice_shown_attributes',
    ];
    $(document).on(events.join(' '), function() {
        servershell.submit_search();
    });

    // Save search settings
    $('#search-options input').change(function() {
        $.getJSON(servershell.urls.settings, {
            'autocomplete': $('#autocomplete')[0].checked,
            'autocomplete_values': $('#autocomplete_values')[0].checked,
            'autocomplete_delay_search': $('#autocomplete_delay_search').val(),
            'autocomplete_delay_commands': $('#autocomplete_delay_commands').val(),
            'autoselect': $('#autoselect')[0].checked,
            'save_attributes': $('#save_attributes')[0].checked,
            'timeout': 5000,
        }).done(function (data) {
            servershell.search_settings = data;
        })
    });
});
