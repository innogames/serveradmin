/*
 * Autocomplete Search - Copyright (c) 2020 InnoGames GmbH
 *
 * This adds the autocomplete while entering a search term. We support
 * autocomplete for hostnames, attributes, attribute values and filters by
 * now.
 */
$(document).ready(function () {
    let _build_value = function (full_term, cur_term, attribute, value) {
        let result = full_term.replace(cur_term, '') + attribute;
        if (value) {
            result += `=${value}`;
        }
        return result;
    };

    $('#term').autocomplete({
        delay: 300, // Wait n ms before starting to auto complete to avoid needles requests to backend
        minLength: 0,
        autoFocus: true,
        source: function (request, response) {
            let limit = 20;
            let choices = [];
            let url = $('#term').data('servershell-autocomplete-url');

            spinner.enable();

            // project=onyx function=db, always focus on last part of query
            let cur_term = request.term.split(' ').pop();

            // Autocomplete values of attributes e.g. function=<autocomplete>
            let match = cur_term.match(/([a-z_]+)=([\S]+)?/);
            if (match) {
                let last_attribute = match[1];
                let last_value = match[2] === undefined ? '' : match[2];

                let settings = {
                    'data': {
                        'attribute': last_attribute,
                        'value': last_value,
                    },
                    'async': false,
                    'success': function (data) {
                        data.autocomplete.forEach(function (attr_value) {
                            choices.push({
                                'label': `AttrVal: ${attr_value}`,
                                'value': _build_value(request.term, cur_term, last_attribute, attr_value),
                            });
                        });
                    }
                };
                $.ajax(url, settings);

                // Add filter to autocomplete ...
                // @TODO: Add autocomplete for nested filter values
                let filters;
                if (last_value) {
                    filters = servershell.filters.filter(filter => filter[0].startsWith(last_value));
                } else {
                    filters = servershell.filters;
                }
                filters.forEach(function (filter) {
                    choices.push({
                        'label': `Filter: ${filter[0]}`,
                        'value': _build_value(request.term, cur_term, last_attribute, filter[0]) + '(',
                    });
                });
            }

            // Attributes available
            let attributes = servershell.attributes.filter(
                attr => attr.attribute_id.startsWith(cur_term) && attr.type !== 'reverse'
            );
            attributes.slice(0, limit).forEach(function (attribute) {
                choices.push({
                    'label': `Attr: ${attribute.attribute_id}`,
                    'value': _build_value(request.term, cur_term, attribute.attribute_id) + '='
                })
            });

            // Autocomplete hostnames for plain server search without
            // key=value filters.
            // This is the exception where we don't want to show autocomplete
            // if nothing has been entered.
            if (
                request.term.length &&
                request.term.split(' ').length === 1 &&
                request.term.indexOf('=') === -1
            ) {
                // Servershell Host results from backend
                let settings = {
                    'data': {'hostname': cur_term},
                    'async': false,
                    'success': function (data) {
                        data.autocomplete.forEach(function (host) {
                            choices.push({
                                'label': `Host: ${host}`,
                                'value': host,
                            });
                        });
                    },
                };
                $.ajax(url, settings);
            }

            spinner.disable();

            response(choices);
        },
    });

    $('#term').on('autocompleteselect', function(event, ui) {
        if (ui.item.value.endsWith('=')) {
            let ac = function() {
                $('#term').autocomplete('search')
            };
            // When triggering autocomplete right away nothing happens, with
            // a small delay it works fine.
            setTimeout(ac, 50);
        }
    });

    $('#disable-autocompletion').on('click', function() {
        if (this.checked)
            $('#term').autocomplete('disable');
        else
            $('#term').autocomplete('enable');
    });

    $('#term').on('autocompleteclose', function () {
        $('#term').focus();
    });
});

