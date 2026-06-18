/*
 * Dismiss by ESC keyboard shortcut, Copyright (c) 2021 InnoGames GmbH
 *
 * Allows to dismiss (delete) HTML elements that have the class dismissible
 * by pressing escape.
 */
$(document).ready(function() {
    $(document).keydown(function (event) {
        // ESC
        if (event.key === "Escape") {
            let dismissible = $('.dismissible');

            if (dismissible.length < 1) {
                return;
            }

            // Pressing ESC on elements such as inputs makes them loose focus.
            // To avoid this we remember the focused element to restore it.
            let input = document.activeElement;

            dismissible.remove();

            if (input) {
                input.focus();
            }

            event.preventDefault();
            event.stopPropagation();
        }
    });
});