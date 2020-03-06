$(document).ready(function() {
    /**
     * Get filtered list of attribute ids
     *
     * Takes a search value and some more configuration and returns filtered
     * list of attribute ids for the auto completion.
     *
     * @param search_for search string such as e.g. puppe
     * @param exclude list of attributes already used
     * @param exclude_multi exclude multi attributes
     * @param exclude_single exclude single attributes
     * @param exclude_reverse exclude reverse attributes
     * @returns alphabetically sorted list of attribute ids
     */
    let get_attribute_ids = function (
        search_for, exclude, exclude_multi = false,
        exclude_single = false, exclude_reverse = false
    ) {
        let attrs = servershell.attributes;

        // TODO: Iterate only once over attributes and evaluate all filter

        if (search_for)
            attrs = attrs.filter(a => a.attribute_id.startsWith(search_for));

        if (exclude_reverse)
            attrs = attrs.filter(a => a.type !== 'reverse');

       if (exclude)
           attrs = attrs.filter(a => !exclude.includes(a.attribute_id));

       if (exclude_multi)
           attrs = attrs.filter(a => a.multi === false);

       if (exclude_single)
           attrs = attrs.filter(a => a.multi === true);

       return attrs.map(a => a.attribute_id).sort();
    };

    let command_input = $('#command');

    command_input.autocomplete({
        delay: 100,
        minLength: 0,
        autoFocus: true,
        source: function(request, response) {
            let choices = [];
            let arguments = request.term.split(' ');

            // Auto complete for all available commands
            if (arguments.length <= 1) {
                let command = arguments.length === 1 ? arguments.pop() : '';
                let commands = servershell.commands;

                Object.keys(commands).sort().forEach(function(name) {
                    if (
                        command === '' ||
                        (name !== command && name.startsWith(command))
                    ) {
                        choices.push({
                            'label': name,
                            'value': `${name} `,
                        });
                    }
                });
            }
            else {
                // Auto complete for certain commands and its values
                let command = arguments.shift().trim();
                let values = arguments.join();

                if (command === 'goto') {
                    let pages = [...Array(servershell.pages()).keys()];
                    pages.forEach(function (p) {
                        let page = p + 1;
                        if (page !== servershell.page()) {
                            choices.push({
                                'label': page,
                                'value': `${command} ${page}`,
                            });
                        }
                    })
                }
                if (command === 'perpage') {
                    let page_size = values.trim();
                    if (page_size === '' || isNaN(page_size))
                        page_size = null;

                    let pages = [5, 10, 15, 20, 25, 50, 100];
                    pages.forEach(function (per_page) {
                        per_page = per_page.toString();
                        if (page_size === null || per_page.startsWith(page_size)) {
                            choices.push({
                                'label': per_page,
                                'value': `${command} ${per_page}`,
                            });
                        }
                    });
                }
                if (command === 'attr' || command === 'export') {
                    values = values.split(',').map(v => v.trim());
                    let search_string = values.pop();
                    let attribute_ids = get_attribute_ids(search_string, values);

                    attribute_ids.slice(0, 25).forEach(function (attribute_id) {
                        let values_string = values.length > 0 ? values.join(',') + ',' : '';
                        choices.push({
                            'label': `Attr: ${attribute_id}`,
                            'value': `${command} ${values_string}${attribute_id}`,
                        })
                    });
                }
                if (
                    command === 'orderby' ||
                    command === 'delattr' ||
                    command === 'history'
                ) {
                    let attribute_ids = get_attribute_ids(
                        values, [], false, false, command === 'delattr'
                    );
                    attribute_ids.slice(0, 25).forEach(function (attribute_id) {
                        choices.push({
                            'label': `Attr: ${attribute_id}`,
                            'value': `${command} ${attribute_id}`,
                        });
                    });
                }
                if (
                    command === 'setattr' ||
                    command === 'multiadd' ||
                    command === 'multidel'
                ) {
                    let search_string = values.split(' ').shift();
                    if (!search_string.includes('=')) {
                        let attribute_ids = get_attribute_ids(
                            search_string, values,
                            command === 'setattr',
                            command === 'multiadd' || command === 'multidel',
                            true,
                        );
                        attribute_ids.slice(0, 25).forEach(function (attribute_id) {
                            choices.push({
                                'label': `Attr: ${attribute_id}`,
                                'value': `${command} ${attribute_id}=`,
                            });
                        });
                    }
                }
            }

            response(choices);
        }
    });

    command_input.on('autocompleteselect', function(event, ui) {
        let value = ui.item.value;
        if (value === '' || value.endsWith(' ')) {
            let ac = function() {
                $('#command').autocomplete('search')
            };
            // When triggering autocomplete right away nothing happens, with
            // a small delay it works fine.
            setTimeout(ac, 50);
        }
    });

    command_input.on('autocompleteclose', function () {
        $('#command').focus();
    });
});