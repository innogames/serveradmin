$(document).ready(function() {
    let get_attribute_ids = function(search_string, already_selected, exclude_multi=false, exclude_single=false) {
        let attribute_ids = servershell.attributes;

        if (search_string)
            attribute_ids = attribute_ids.filter(
                a => a.attribute_id.substring(0, a.attribute_id.length - 1).startsWith(search_string) && a.type !== 'reverse');

       if (already_selected)
           attribute_ids = attribute_ids.filter(a => !already_selected.includes(a.attribute_id));

       if (exclude_multi)
           attribute_ids = attribute_ids.filter(a => a.multi === false);

       if (exclude_single)
           attribute_ids = attribute_ids.filter(a => a.multi === true);

       return attribute_ids.map(a => a.attribute_id).sort();
    };

   $('#command').autocomplete({
       delay: 100,
       minLength: 0,
       autoFocus: true,
       source: function(request, response) {
           let choices = [];
           let arguments = request.term.split(' ', 2).map(v => v.trim());

           if (arguments.length === 1) {
               let command = arguments.pop();
               Object.keys(servershell.commands).forEach(function(name) {
                   if (name !== command && name.startsWith(command)) {
                       choices.push({
                           'label': name,
                           'value': `${name} `,
                       });
                   }
               });
           }
           else {
               let command = arguments[0].trim();
               let values = arguments[1].split(',').map(v => v.trim());

               if (command === 'goto') {
                   [...Array(servershell.pages()).keys()].forEach(function (p) {
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
                   let user_input = values.pop();
                   if (user_input === '') {
                       [5, 10, 15, 20, 25, 50, 100].forEach(function (perpage) {
                           choices.push({
                               'label': perpage,
                               'value': `${command} ${perpage}`,
                           })
                       });
                   }
               }
               if (command === 'attr' || command === 'export') {
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
               if (command === 'orderby' || command === 'delattr' || command === 'history') {
                   let search_string = values.shift();
                   let attribute_ids = get_attribute_ids(search_string);
                   attribute_ids.slice(0, 25).forEach(function(attribute_id) {
                        choices.push({
                            'label': `Attr: ${attribute_id}`,
                            'value': `${command} ${attribute_id}`,
                        });
                   });
               }
               if (command === 'setattr' || command === 'multiadd' || command === 'multidel') {
                   let search_string = values.shift();
                   if (!search_string.includes('=')) {
                        let attribute_ids = get_attribute_ids(
                            search_string, values,
                            command === 'setattr',
                            command === 'multiadd' || command === 'multidel');
                        attribute_ids.slice(0, 25).forEach(function(attribute_id) {
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
   })
});

$('#command').on('autocompleteselect', function(event, ui) {
    if (ui.item.value.endsWith(' ')) {
        let ac = function() {
            $('#command').autocomplete('search')
        };
        // When triggering autocomplete right away nothing happens, with
        // a small delay it works fine.
        setTimeout(ac, 50);
    }
});

$('#command').on('autocompleteclose', function () {
    $('#command').focus();
});