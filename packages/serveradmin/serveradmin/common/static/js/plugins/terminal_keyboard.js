/*
 * Terminal Keyboard navigation, Copyright (c) 2020 InnoGames GmbH
 *
 * Include this Javascript to your page to enable terminal like keyboard
 * navigation on input fields. You can for example use CTRL + ARROW and
 * CTRL + BACKSPACE to jump and delete whole words.
 */
$(document).ready(function() {
    $(document).keydown(function (event) {
        // This is cheap so it comes first
        if (event.altKey) {
            let element = event.target;
            if (element.type !== 'text' && element !== 'textarea')
                return;

            // ALT + BACKSPACE
            if (event.which === 8) {
                let text = element.value;
                let cursor = element.selectionEnd;
                let matches = text.match(/\w+/g);
                let new_position = cursor;

                if (matches)
                    new_position = text.indexOf(matches[matches.length - 1]);

                element.value = text.substring(0, new_position);
                element.selectionStart = text.length;
                element.selectionEnd = text.length;
            }
        }
    });
});