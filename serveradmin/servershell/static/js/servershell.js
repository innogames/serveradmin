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
 *
 * Convention:
 *
 * Use methods attached to servershell object within other scripts or pages
 * but not the normal the other ones. They are supposed to represent internal
 * functions and may change their behaviour.
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
    _config: {
        // Key is the name of the property. Value is null for primitive data
        // types and can be an array of method names for non primitive ones
        // such as array. When ever a certain method is used a event will be
        // triggered. The standard events set and get will always be triggered.
        term: null,
        command: null,
        understood: null,
        retries: null,
        shown_attributes: ['push', 'splice'],
    },
    _trigger_events: function(action, property, property_of) {
        if (Object.keys(this._config).includes(property)) {
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

        if (
            Object.keys(this._config).includes(property_of) &&
            this._config[property_of] &&
            this._config[property_of].includes(property)
        ) {
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
        // Observer configured properties
        if (Object.keys(this._config).includes(property) &&  object[property] && typeof object[property] === 'object') {
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

/**
 * Show message using bootstrap alerts
 *
 * This is for javascript showing errors such as invalid commands where we
 * don't have the backend. If the error is coming from the backend please
 * using Django messages mechanism. It will generate bootstrap alert as well.
 *
 * @param text message to show
 * @param level either primary,secondary,success,danger,warning,info,light,dark
 * @param auto_dismiss seconds to wait before disappear (0 never)
 */
servershell.alert = function(text, level, auto_dismiss=5) {
    let levels = [
        'primary',
        'secondary',
        'success',
        'danger',
        'warning',
        'info',
        'light',
        'dark'
    ];

    if (!levels.includes(level)) {
        return;
    }

    let template = $('.alert').first();

    let new_alert = template.clone();
    new_alert.addClass(`alert-${level}`);
    new_alert.children('.alert-text').text(text);
    template.after(new_alert);
    new_alert.toggle();

    if (auto_dismiss > 0) {
        setTimeout(function() {
            $(new_alert).remove();
        }, auto_dismiss * 1000);
    }
};

/**
 * Get server object
 *
 * Get server object by object_id if in server list.
 *
 * @param object_id
 */
servershell.get_object = function(object_id) {
   return servershell.servers.find(server => server.object_id === object_id);
};

/**
 * Get attribute object
 *
 * Get attribute object by attribute_id if in attribute list.
 *
 * @param attribute_id
 * @returns {*}
 */
servershell.get_attribute = function(attribute_id) {
    return servershell.attributes.find(
        attribute => attribute.attribute_id === attribute_id);
};