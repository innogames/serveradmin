/*
 * Autocomplete History - Copyright (c) 2026 InnoGames GmbH
 *
 * This module ads auto complete while searching the query history
 */

servershell.autocomplete_history_enabled = false;

servershell.close_history_autocomplete = function () {
    const autocomplete_search_input = $('#term');
    autocomplete_search_input.autocomplete('destroy');
    servershell.autocomplete_history_enabled = false;
    servershell.enable_search_autocomplete();
    $('#history-toggle').removeClass('active');
}

servershell.open_history_autocomplete = function () {
    const autocomplete_search_input = $('#term');
    autocomplete_search_input.autocomplete('destroy');
    autocomplete_search_input.autocomplete({
        source: function (request, response) {
            const displayLimit = 20;
            const search = request.term;

            const history = servershell.history.get()
            const possibleChoices = history.filter((entry) => entry.search.toLowerCase().includes(search.toLowerCase()))
                .map((entry) => entry.search);
            response(possibleChoices.slice(0, Math.min(displayLimit, possibleChoices.length)));
        },

        select: function (_, ui) {
            autocomplete_search_input.trigger('change', ui.item.value);
            servershell.close_history_autocomplete()
        }
    });
    autocomplete_search_input.autocomplete('enable');
    autocomplete_search_input.autocomplete('option', 'autoFocus', $('#autoselect')[0].checked);
    autocomplete_search_input.autocomplete('option', 'minLength', 0);
    autocomplete_search_input.autocomplete('option', 'delay', 50); // Searching local storage is fast
    autocomplete_search_input.autocomplete('search', "");
    autocomplete_search_input.focus();
    servershell.autocomplete_history_enabled = true;
    $('#history-toggle').addClass('active');
}

$(document).ready(function () {
    $(document).keydown(function (event) {
        if (event.shiftKey && event.ctrlKey) {
            if (event.key !== 'F') {
                return;
            }
            if (servershell.autocomplete_history_enabled) {
                servershell.close_history_autocomplete();
                return;
            }
            servershell.open_history_autocomplete();
        }
    });

    $('#term').on('focusout', () => {
        // If the user clicks away from the search box we want to return to normal mode
        if (servershell.autocomplete_history_enabled) {
            servershell.close_history_autocomplete();
        }
    })
});