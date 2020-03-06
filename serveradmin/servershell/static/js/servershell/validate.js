/*
 * Live input validation, Copyright (c) 2020 InnoGames GmbH
 *
 * Register live input validation as to all text and textarea elements on
 * the page as long as they have data-pattern attribute set to a regex.
 */
$(document).ready(function() {
    $(document).keyup(function(event) {
        let input = $(event.target);

        if (input.data('pattern')) {
            let values = [];

            if (input[0].type === 'text')
                values = [input[0].value];
            if (input[0].type === 'textarea')
                values = input[0].value.split('\n');

            values.forEach(function(value) {
                // We are graceful and make empty valid too ...
                if (value !== '' && !value.match(input.data('pattern')))
                    input.css('background-color', 'rgba(255, 0, 0, 0.21);');
                else
                    input.css('background-color', '');
            });
        }
    })
});