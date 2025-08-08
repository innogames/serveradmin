/**
 * Send the search term to the backend, process and display the results or show errors if there are any.
 *
 * @param url Serveradmin servershell query URL (e.g. /servershell/results)
 * @param search_term Text based query (e.g. project=foo)
 * @param pinned List ob object ids to query besides search_term
 * @param focus_command_input Focus on command input when done or not
 * @returns {Promise<{}>}
 */
async function _search(url, search_term, pinned = [], focus_command_input = false) {
    let request_data = {
        term: search_term,
        shown_attributes: servershell.shown_attributes,
        deep_link: servershell.deep_link,
        offset: servershell.offset,
        limit: servershell.limit,
        order_by: servershell.order_by,
        pinned,
        async: false,
        timeout: 5000,
    };
    servershell._ajax = $.getJSON(url, request_data);
    console.debug(request_data);
    let data = await servershell._ajax;

    if ('message' in data) {
        return servershell.alert(data.message, 'danger');
    }

    // Update property used by bookmark link of search
    servershell.href = '?' + $.param({
        'term': servershell.term,
        'shown_attributes': servershell.shown_attributes,
        'deep_link': true,
    });

    // Replace the URL with the requested one from the Ajax request to
    // avoid loosing the selection of attributes when using multiple tabs.
    window.history.pushState(null, null, servershell.href);

    // If the search term changes and we exceed the available pages with
    // our current settings then go to page 1
    if (servershell.page() > servershell.pages()) {
        servershell.offset = 0;
    }

    console.debug(`Query result status is: "${data.status}" with data:`);
    console.debug(data);

    // Indicator that we have successfully reloaded ...
    servershell._term = servershell.term;

    // Focus command input. Should only be set to true when the user has
    // submitted the form but not when the search is triggered by for example
    // changing the shown attributes.
    if (focus_command_input) {
        $('#command').focus();
    }

    return data;
}

/**
 * Submit Search Term
 *
 * Take the current entered search term and the settings such as per_page etc.
 * and submit the query to the Serveradmin backend. On success extract the
 * result to the corresponding servershell properties.
 */
servershell.submit_search = function(focus_command_input = false) {
    // Prevent somebody hitting enter like crazy
    if (servershell._ajax !== null) {
        return servershell.alert('Pending request, cancel it or wait for it to finish!', 'danger');
    }

    // Do not submit search on load.
    let params = new URLSearchParams(window.location.search);
    if (servershell.term === null && !params.has('term')) {
        servershell.term = '';
        return;
    }

    let url = $('#search_form').get(0).action;
    console.debug(`Submitting query to URL "${url}" with data:`);
    spinner.enable('search');

    let to_commit = servershell.to_commit || {};
    let pinned = servershell.pinned || [];
    let touched_objects = [
        ...pinned,
        ...(to_commit.deleted ?? []),
        ...(Object.keys((to_commit.changes ?? {})).map(val => Number.parseInt(val)))
    ];

    _search(url, servershell.term, touched_objects, focus_command_input)
        .then(data => {
            if (data) {
                servershell.editable_attributes = data.editable_attributes;
                servershell.servers = data.servers;
                servershell.num_servers = data.num_servers;
                servershell.status = data.status;
                servershell.understood = data.understood;
            }
        })
        .catch(function(xhr) {
            if (xhr.status === 0) {
                servershell.alert('Network error while requesting Serveradmin!', 'danger');
            }
            else if (xhr.status in [500, 502, 503, 504]) {
                servershell.alert(`HTTP error: ${xhr.status}! If retry does not help let us know.`)
            }
            else if (xhr.status === 401) {
                servershell.alert('Session expired. You need to login again!');
            }
        })
        .finally(function() {
            spinner.disable('search');

            // We will use this on other components to react on changes ...
            $(document).trigger('servershell_search_finished');

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
        // Trim the search term and update the input field
        servershell.term = servershell.term.trim();
        servershell.submit_search(true);
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
            'autocomplete_delay_search': $('#autocomplete_delay_search').val(),
            'autocomplete_delay_commands': $('#autocomplete_delay_commands').val(),
            'autoselect': $('#autoselect')[0].checked,
            'save_attributes': $('#save_attributes')[0].checked,
            'timeout': 5000,
        }).done(function(data) {
            servershell.search_settings = data;
        })
    });
});
