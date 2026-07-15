// Track last clicked row checkbox index for shift-click range selection
let _lastCheckedIndex = null;

/**
 * Generate HTML for result table
 *
 * Generates and updates the HTML for the result table based on the servershell
 * properties.
 */
servershell.update_result = function() {
    let table = $('#result_table');

    // Memorize currently selected objects to restore
    let selected = servershell.get_selected();

    // servershell is a Proxy (servershell.js): reading a configured property
    // fires jQuery events and allocates a wrapper on each access. Snapshot the
    // ones used per row into plain values so the render loop stays cheap.
    let shown_attributes = [...servershell.shown_attributes];
    let changes = servershell.to_commit.changes;
    let offset = servershell.offset;

    // Recreate table header
    let header = table.find('thead tr');
    header.empty();
    header.append(
        $('<th scope="col">').append(
            $('<input type="checkbox" id="select-all" tabindex="3" />')
        )
    );
    header.append('<th scope="col">#</th>');
    shown_attributes.forEach((attribute, index) => header.append(
        $('<th scope="col">').append(
            $('<span>').text(attribute),
            $(`<a href="#" class="attr-headericons" title="Order by ${attribute} attribute">`).append(
                $('<i class="fa-solid fa-arrow-down-a-z">')
            ).click(function(e) {
                e.preventDefault();
                servershell.commands.orderby(attribute);
            }),
            $(`<a href="#" class="attr-headericons" title="Remove ${attribute} column">`).append(
                $('<i class="fa-solid fa-xmark">')
            ).click(function(e) {
                e.preventDefault();
                servershell.commands.attr(attribute);
            }),
        )
    ));

    // O(1) lookups for the per-cell render loop below, built once. Keeps cell
    // rendering from scanning objects / the attribute catalog / pending changes
    // linearly for every cell (which makes a redraw quadratic in row count).
    let ctx = {
        deleted: new Set(servershell.to_commit.deleted),
        changed_ids: new Set(
            Object.keys(servershell.to_commit.changes).map(Number)),
        pinned: new Set(servershell.pinned ?? []),
        attribute_map: new Map(
            servershell.attributes.map(a => [a.attribute_id, a])),
        editable_sets: new Map(
            Object.entries(servershell.editable_attributes).map(
                ([servertype, attrs]) => [servertype, new Set(attrs)])),
        // Proxied properties snapshotted above.
        shown_attributes: shown_attributes,
        changes: changes,
        offset: offset,
    };

    // Build all rows as HTML strings and write the body with a single
    // innerHTML assignment. One parser for the whole body is cheaper than
    // per-element jQuery construction when there are many rows processed.
    let body = table.find('tbody');
    _lastCheckedIndex = null;
    let rows = servershell.servers.map((object, index) => get_row_html(object, index + 1, ctx));
    body[0].innerHTML = rows.join('');

    // Restore previous selected objects
    servershell.set_selected(selected);
    sync_select_all();

    // Update result information on top and bottom showing page etc.
    let info = `Results (${servershell.num_servers} servers, page ${servershell.page()}/${servershell.pages()}, ${servershell.limit} per page)`;
    $('span.result_info').text(info);

    // Select first element if there is only one.
    if (servershell.servers.length === 1) {
        $('#result_table input[name=server]').each((index, element) => element.checked = true);
    }
};

/**
 * Escape a value for safe interpolation into an HTML string.
 *
 * get_row_html builds rows as HTML strings, so every dynamic value (attribute
 * values, hostnames, ids) must be escaped through here before interpolation to
 * avoid XSS.
 *
 * @param value
 * @returns {string}
 */
escape_html = function(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
};

/**
 * Build the inner HTML for a relation/reverse attribute cell.
 *
 * Related objects are rendered as ctrl-clickable spans (a single delegated
 * click handler on the table, see $(document).ready, does the inspecting).
 * Returns an HTML string; hostnames are escaped.
 *
 * @param value hostname string (multi=false) or array of hostnames (multi=true)
 * @returns {string}
 */
relation_links_html = function(value) {
    if (value === null || value === undefined) {
        return '';
    }

    // Normalize single relations and multi relations to a sorted list so the
    // display matches get_string() ordering.
    let hostnames = Array.isArray(value) ? value.slice().sort() : [value];

    return hostnames.map(function(hostname) {
        let safe = escape_html(hostname);
        return `<span class="relation-link" title="Ctrl-click to inspect" data-hostname="${safe}">${safe}</span>`;
    }).join(', ');
};

/**
 * Get HTML for table row
 *
 * Returns the HTML string for a result table body row based on the object and
 * row number. Built as a string (not jQuery elements) so the whole body can be
 * assigned with a single innerHTML write in update_result.
 *
 * @param object
 * @param number
 * @param ctx precomputed lookups from update_result (see there)
 * @returns {string}
 */
get_row_html = function(object, number, ctx) {
    let classes = [];

    // Mark row as deleted. Make sure this wins over other colors
    // such as the state otherwise the user will not see objects marked for
    // deletion.
    if (ctx.deleted.has(object.object_id)) {
        classes.push('delete');
    }
    if (object.hasOwnProperty('state')) {
        classes.push(`state-${object.state}`);
    }
    if (ctx.changed_ids.has(object.object_id)) {
        classes.push('highlight');
    }
    if (ctx.pinned.has(object.object_id)) {
        classes.push('highlight');
    }

    let class_attr = classes.length ? ` class="${escape_html(classes.join(' '))}"` : '';
    // data-oid lets the delegated inline-edit handler recover the object id.
    let html = `<tr${class_attr} data-oid="${object.object_id}">`;

    // Standard columns which should always be present
    html += `<td><input tabindex="3" type="checkbox" name="server" value="${object.object_id}"/></td>`;
    html += `<td>${escape_html(number + ctx.offset)}</td>`;

    let changes = ctx.changes;
    ctx.shown_attributes.forEach(function(attribute_id) {
        // Looked up once from the precomputed map instead of scanning the
        // full attribute catalog per cell.
        let attribute = ctx.attribute_map.get(attribute_id);
        let editable = is_editable(object, attribute_id, ctx.editable_sets);

        // Changes in to_commit we have to display (only on editable cells)
        let change;
        if (editable && object.object_id in changes && attribute_id in changes[object.object_id]) {
            change = changes[object.object_id][attribute_id];
        }

        let inner;
        if (change) {
            if (attribute.multi) {
                let to_add = change.add.join(', ');
                let to_delete = change.remove;
                let value = object[attribute_id].filter(v => !to_delete.includes(v)).join(', ');

                inner = escape_html(value);
                if (value.length > 0) {
                    inner += ', ';
                }
                inner += `<del>${escape_html(to_delete.join(', '))}</del>`;
                inner += `<u>${escape_html(to_add)}</u>`;
            }
            else {
                let to_delete = change.old === null ? '' : change.old;
                let new_value = change.new === undefined ? '' : change.new;

                inner = `<del>${escape_html(to_delete)}</del><u>${escape_html(new_value)}</u>`;
            }
        }
        else if (attribute.type === 'relation' || attribute.type === 'reverse') {
            // Reverse attributes are readonly and land here too; both editable
            // and readonly relations render as ctrl-clickable inspect links.
            inner = relation_links_html(object[attribute_id]);
        }
        else {
            inner = escape_html(get_string(object, attribute_id, attribute));
        }

        if (editable) {
            // 'editable' class + data-aid let a single delegated dblclick
            // handler on the table target these cells (see $(document).ready).
            html += `<td class="editable" data-aid="${escape_html(attribute_id)}">${inner}</td>`;
        }
        else {
            html += `<td class="disabled">${inner}</td>`;
        }
    });

    html += '</tr>';
    return html;
};

/**
 * Get selected objects
 *
 * Get a list of selected object ids based on the HTML checkboxes.
 *
 * @returns Array
 */
servershell.get_selected = function() {
    return $.map($('#result_table input[name=server]:checked'), function(element) {
        return parseInt(element.value);
    });
};

/**
 * Set selected objects
 *
 * Tick the checkbox in the result table HTML for the given object ids.
 *
 * @param object_ids
 */
servershell.set_selected = function(object_ids) {
    // Single pass with Set membership, so restoring selection is O(rows) rather
    // than O(selected * rows). Runs right after a full body rebuild, so
    // unchecking the non-matches here is harmless.
    let wanted = new Set(object_ids);
    $('#result_table input[name=server]').each(function() {
        this.checked = wanted.has(parseInt(this.value));
    });
};

/**
 * Check if attribute is editable
 *
 * Takes the object directly (not the id) and a precomputed Map of
 * servertype -> Set(editable attribute ids) to avoid per-cell linear scans.
 *
 * @param object
 * @param attribute_id
 * @param editable_sets Map<servertype, Set<attribute_id>>
 * @returns boolean
 */
is_editable = function(object, attribute_id, editable_sets) {
    let set = editable_sets.get(object.servertype);
    return attribute_id in object && set !== undefined && set.has(attribute_id);
};

/**
 * Get attribute value as string
 *
 * Takes the object and its already-resolved attribute directly to avoid the
 * get_object / get_attribute linear scans on the hot render path.
 *
 * @param object
 * @param attribute_id
 * @param attribute resolved attribute object
 * @returns {*}
 */
get_string = function(object, attribute_id, attribute) {
    if (attribute_id in object && object[attribute_id] !== null) {
        if (attribute.multi) {
            return object[attribute_id].sort().join(', ');
        } else {
            return object[attribute_id].toString();
        }
    }

    return '';
};

/**
 * Make row editable by double click
 *
 * Inline edit handler, bound once via delegation on the result table (see
 * $(document).ready) so no per-cell handlers are registered. Reads the object
 * and attribute from the double-clicked cell/row.
 *
 * @param event dblclick event on a td.editable cell
 */
handle_inline_edit = function (event) {
    // Do not open another inline edit unless previous is finished
    let previous = $('#inline-edit-save');
    if (previous.length) {
        return;
    }

    let cell = $(event.target).closest('td');
    let row = cell.parent();
    let object_id = row.data('oid');
    let object = servershell.get_object(object_id);
    let attribute_id = cell.data('aid');
    let attribute = servershell.get_attribute(attribute_id);

    // Select row for convenience
    if (!servershell.get_selected().includes(object_id)) {
        row.children('td:first').children('input').click();
    }

    let current_value;
    let changes = servershell.to_commit.changes;
    if (object_id in changes && attribute_id in changes[object_id]) {
        if (attribute.multi) {
            current_value = object[attribute_id].filter(v => !changes[object_id][attribute_id].remove.includes(v));
            current_value = current_value.concat(changes[object_id][attribute_id].add);
        } else {
            if (changes[object_id][attribute_id].action === 'delete') {
                current_value = '';
            } else {
                current_value = changes[object_id][attribute_id].new;
            }
        }
    } else {
        current_value = servershell.get_object(object_id)[attribute_id];
    }

    let content;
    if (attribute.multi) {
        content = $('<textarea rows="5" cols="30">').text(current_value.join('\n'));
    } else {
        content = $('<input type="text" />').val(current_value === null ? '' : current_value);
    }

    // Provide on-the-fly validation
    if ('regex' in attribute && attribute.regex !== null) {
        content.data('pattern', attribute.regex);
    }

    content.attr('id', 'inline-edit');
    content.data('oid', object_id);
    content.data('aid', attribute_id);
    content.data('multi', attribute.multi);

    let button = $('<button id="inline-edit-save" class="btn btn-success btn-sm">save</button>');
    button.click(function (event) {
        let value;
        let edit = $(event.target).prev();
        let multi = edit.data('multi');

        if (multi) {
            value = edit.val().split('\n').map(v => v.trim()).filter(v => v !== '');
        } else {
            value = edit.val().trim();
        }

        let object_id = edit.data('oid');
        let attribute_id = edit.data('aid');
        let attribute = servershell.get_attribute(attribute_id);

        // When the user types 'false' use empty string so that it casts to false
        if (attribute.type === 'boolean' && (value === 'false' || value === '0')) {
            value = '';
        }

        if (value === '') {
            servershell.delete_attribute(object_id, attribute_id)
        }
        else {
            servershell.update_attribute(object_id, attribute_id, value);
        }

        servershell.update_result();
    });

    // Hit save button on enter or shift + enter if multi attribute
    $(document).keypress(function(event) {
        if (event.which === 13) {
            let save = $('#inline-edit-save');
            if (save.length) {
                let type = save.prev().get(0).type;
                if (type === 'textarea' && event.shiftKey || type === 'text') {
                    event.preventDefault();
                    save.click();
                }
            }
        }
    });

    cell.html(content);
    cell.append(button);
    cell.append($('<div>').append($('<b>').text(attribute.regex !== null ? attribute.regex : 'No Regexp')));

    // Focus element and place cursor at the end of the text
    content.focus();
    content.get(0).setSelectionRange(-1, -1);
};

/**
 * Sync the select-all header checkbox with the current row checkbox state.
 */
sync_select_all = function() {
    let all = $('#result_table input[name=server]');
    let checked = all.filter(':checked');
    let selectAll = $('#select-all')[0];
    if (selectAll) {
        selectAll.checked = all.length > 0 && checked.length === all.length;
        selectAll.indeterminate = checked.length > 0 && checked.length < all.length;
    }
};

$(document).ready(function() {
    // Update result table as soon as we have new data ...
    $(document).on('servershell_search_finished', servershell.update_result);

    // Delegated inline edit: one handler covers every editable cell.
    $('#result_table').on('dblclick', 'tbody td.editable', handle_inline_edit);

    // Delegated relation inspect: ctrl/cmd-click a relation link to open the
    // related object. One handler covers every rendered link.
    $('#result_table').on('click', '.relation-link', function(event) {
        if (!event.ctrlKey && !event.metaKey) {
            return;
        }
        event.preventDefault();
        let hostname = $(this).attr('data-hostname');
        window.open(
            `${servershell.urls.inspect}?hostname=${encodeURIComponent(hostname)}`,
            '_blank'
        );
    });

    // Toggle all row checkboxes when the select-all header checkbox is clicked
    $('#result_table').on('click', '#select-all', function() {
        let checked = this.checked;
        $('#result_table input[name=server]').prop('checked', checked);
    });

    // Sync header checkbox when individual row checkboxes change
    $('#result_table').on('change', 'tbody input[name=server]', sync_select_all);

    // Shift-click to select a range of checkboxes
    $('#result_table').on('click', 'tbody input[name=server]', function(e) {
        let checkboxes = $('#result_table input[name=server]');
        let currentIndex = checkboxes.index(this);

        if (e.shiftKey && _lastCheckedIndex !== null) {
            let start = Math.min(_lastCheckedIndex, currentIndex);
            let end = Math.max(_lastCheckedIndex, currentIndex);
            let state = this.checked;
            checkboxes.slice(start, end + 1).prop('checked', state);
            sync_select_all();
        }

        _lastCheckedIndex = currentIndex;
    });
});
