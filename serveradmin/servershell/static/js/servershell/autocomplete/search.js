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

    let _is_attribute_value = function(to_complete) {
        /**
         * Check if attribute value
         *
         * Check if to_complete is attribute value like for example a=b and
         * if yes return attribute and value otherwise false.
         *
         * @type {Array|Boolean}
         */
        let match = to_complete.match(/([a-z_]+)=([\S]+)?/);

        if (match) {
            let attribute = match[1];
            let value = match[2] === undefined ? '' : match[2];

            return [attribute, value];
        }

        return false;
    };

    let _complete_filter = function(to_complete) {
        let filters = [];
        if (to_complete) {
            return servershell.filters.filter(filter => filter[0].startsWith(to_complete));
        } else {
            return servershell.filters;
        }
    };

    let autocomplete_search_input = $('#term');
    let autocomplete_search_url = autocomplete_search_input.data('servershell-autocomplete-url');
    autocomplete_search_input.autocomplete({
        delay: 250, // Wait n ms before starting to auto complete to avoid needles requests to backend
        autoFocus: true,
        source: function (request, response) {
            spinner.enable();

            let limit = 20;
            let choices = [];

            // Example input: "project=foo fun". Always focus on the last part
            // of the term.
            let to_complete = request.term.split(' ').pop();

            let attribute_value = _is_attribute_value(to_complete);
            if (attribute_value !== false) {
                let attribute = attribute_value[0];
                let value = attribute_value[1];

                // Add filter functions matching
                _complete_filter(value).forEach(function (filter) {
                    let filter_name = filter[0];
                    let new_term = _build_value(request.term, to_complete, attribute, filter_name);

                    choices.push({
                        'label': `Filter: ${filter[0]}`,
                        'value': new_term + '(',
                    });
                });

                // Autocomplete attribute value if wanted
                // @TODO support nested values e.g. "project=Any(Reg("
                if (servershell.search_settings.autocomplete_values) {
                    // Add attribute values matching
                    let settings = {
                        'async': false,
                        'data': {
                            'attribute': attribute,
                            'value': value,
                        },
                        'success': function (data) {
                            data.autocomplete.forEach(function(match) {
                                choices.push({
                                    'label': `AttrVal: ${match}`,
                                    'value': _build_value(request.term, to_complete, attribute, match),
                                });
                            });
                        }
                    };
                    $.ajax(autocomplete_search_url, settings);
                }
            }

            // Autocomplete attributes
            let attributes = servershell.attributes.filter(
                a => a.attribute_id.startsWith(to_complete) && a.type !== 'reverse'
            );
            attributes.slice(0, limit).forEach(function(a) {
                choices.push({
                    'label': `Attr: ${a.attribute_id}`,
                    'value': _build_value(request.term, to_complete, a.attribute_id) + '='
                })
            });

            // Suggest hostnames if only a part of a hostname has been entered
            if (
                request.term.length &&
                request.term.split(' ').length === 1 &&
                request.term.indexOf('=') === -1
            ) {
                let settings = {
                    'async': false,
                    'data': {'hostname': to_complete},
                    'success': function (data) {
                        data.autocomplete.forEach(function (host) {
                            choices.push({
                                'label': `Host: ${host}`,
                                'value': host,
                            });
                        });
                    },
                };
                $.ajax(autocomplete_search_url, settings);
            }

            spinner.disable();

            // Don't auto complete if the user has already entered everything
            if (choices.length === 1 && choices[0]['value'] === request.term) {
                response([]);
                return;
            }

            response(choices);
        },
    });

    autocomplete_search_input.autocomplete($('#autocomplete')[0].checked ? 'enable' : 'disable');
    autocomplete_search_input.autocomplete('option', 'autoFocus', $('#autoselect')[0].checked);
});
