/* Servershell 2.x - Copyright (c) 2020 InnoGames GmbH
 *
 * The Servershell consists of three major (HTML) components:
 *   1. The Servershell Search (search, command and understood inputs)
 *   2. The Servershell Attributes Selection (right collapsible sidebar)
 *   3. The Servershell Results (table to display, select and edit results)
 *
 * 1. The Servershell Search:
 *
 * The search input allows to enter Serveradmin text queries and submit them
 * by hitting enter. The command input allows to apply actions to the result
 * table like e.g. goto next page, set value for attribute etc. The understood
 * input shows the last submitted text query as understood by the backend.
 *
 * 2. The Servershell Attributes Selection:
 *
 * The attributes selection gives a overview about currently selected and
 * available attributes. Additionally it shows the type of the attribute and
 * a help text if available.
 *
 * 3. The Servershell Results
 *
 * Contains the results for the last submitted search. Allows to select and
 * edit attributes which then can be used or committed with the commands of the
 * Servershell Search.
 *
 * ----------------------------------------------------------------------------
 *
 * TLDR:
 *
 * We use the servershell object as the model holding all relevant data to the
 * servershell such as servers, visible attribute etc. and use the observer
 * pattern to react on changes.
 * Since the JS Array and Object observe method are deprecated and proxies
 * are suggested to use we implement a custom proxy to trigger events.
 *
 * That's all you need to know to understand how it works without greater
 * detail.
 */

/**
 * Property Proxy Handler
 *
 * To allow decoupling the 3 Servershell components and possible extensions
 * we fire events when ever a servershell property is accessed or changed.
 * Components can listen to these events and then react accordingly like for
 * example submit the search and reload the result when the selected attributes
 * have changed.
 *
 * Access to properties will trigger events before the values are returning
 * and change (set and methods calls) will trigger events after the methods
 * have been executed.
 *
 * We fire events for a general access or change to a property
 * (useful for e.g. data binding):
 *
 *  - [EVENT NAME]              -> [EXAMPLE TRIGGER]
 *  - servershell.property.set  -> servershell.attributes = ['servertype=vm']
 *  - servershell.property.get  -> console.log(servershell.attributes);
 *  - servershell.property.push -> servershell.attributes.push('hostname');
 *
 * And (additionally) two events which identify the property:
 *
 *  - [EVENT NAME]                         -> [EXAMPLE TRIGGER]
 *  - servershell.property.attributes.set  -> servershell.attributes = ['servertype=vm']
 *  - servershell.property.attributes.get  -> console.log(servershell.attributes);
 *  - servershell.property.attributes.push -> servershell.attributes.push('hostname');
 *
 * NOTE: Change the down under configuration for firing events with care as
 *       this can trigger for example reloading the page unnecessary.
 */
const property_handler = {
    // Extend or adjust the configuration of observed properties according to
    // your needs ...
    _config: [
        // Key is the name of the property. Value is null for primitive data
        // types and can be an array of method names for non primitive ones
        // such as array. When ever a certain method is used a event will be
        // triggered. The standard events set and get will always be triggered.
        //
        // @TODO check what events we really need
        {'term': null},
        {'command': null},
        {'understood': null},
        {'shown_attributes': ['push', 'splice']},
        {'attributes': ['push']},
        {'offset': null},
        {'limit': null},
        {'per_page': null},
        {'order_by': null},
        {'servers': null},
    ],
    _trigger_events: function(action, property, property_of) {
        let set_or_get = this._config.filter(function(value) {
            return value.hasOwnProperty(property);
        });
        if (set_or_get.length) {
            let data = {
                'property': property
            };

            // Generic event
            console.debug(`Triggering servershell_property_${action}`);
            $(document).trigger(`servershell_property_${action}`, data);

            // Specific event
            console.debug(`Triggering servershell_property_${action}_${property}`);
            $(document).trigger(`servershell_property_${action}_${property}`, data);

            return;
        }

        let other_method = this._config.filter(function(value) {
            return value.hasOwnProperty(property_of) && value[property_of] && value[property_of].indexOf(property) > -1;
        });
        if (other_method.length) {
            let data = {
                'property': property_of,
                'method': property,
            };

            // Generic event for method
            console.debug(`Triggering servershell_property_${property}`);
            $(document).trigger(`servershell_property_${property}`, data);

            // Specific event for method
            console.debug(`Triggering servershell_property_${property}_${property_of}`);
            $(document).trigger(`servershell_property_${property}_${property_of}`, data);
        }
    },
    set: function(object, property, new_value) {
        object[property] = new_value;

        // Trigger events AFTER the new value has been set
        this._trigger_events('set', property, this._property_of);

        return true;
    },
    get: function(object, property) {
        // typeof null is object so we have to check if it is not null ...
        if (object[property] && typeof object[property] === 'object') {
            object[property]._property_of = property;
            return new Proxy(object[property], property_handler);
        }
        if (typeof object[property] === 'function') {
            let _this = this;
            return function(...args) {
                let result = object[property].apply(this, args);
                // But trigger events AFTER functions such as push have
                // been executed
                _this._trigger_events(null, property, object._property_of);
                return result;
            }
        }

        // Trigger events BEFORE the value has been returned
        this._trigger_events('get', property);

        return object[property];
    },
};

// This initializes the servershell object which we will use to held properties
// such as the search term etc.
const servershell = new Proxy({}, property_handler);

/**
 * Get current page
 *
 * Calculates the current selected page of the result table base on the
 * current offset.
 *
 * @returns {number}
 */
servershell.page = function() {
    return servershell.offset / servershell.limit + 1;
};

/**
 * Get number of pages available
 *
 * Calculates the number of pages available for the result table based on
 * the configured limit.
 *
 * @returns {number}
 */
servershell.pages = function() {
    return Math.ceil(servershell.num_servers / servershell.limit);
};