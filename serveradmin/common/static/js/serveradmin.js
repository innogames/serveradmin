$(document).ready(function() {
    // Mark the current page as active in navigation
    let current = $('nav .nav-link[href="' + window.location.pathname + '"]');
    if (current.length) {
        current[0].classList.add('active');
    }

    // This is our progress spinner we can call e.g. spinner.enable() from
    // everywhere when ever we need it for example when doing long running
    // ajax requests for the servershell search.
    window.spinner = {
        _timers: {},
        _spinner: $('#spinner'),
        enable: function (action) {
            console.debug('spinner enabled');
            this._timers[action] = Date.now()
            if($(`#spinner-timer-value-${action}`).length == 0) {
                $("#spinner-timer").append(`<span id="spinner-timer-value-${action}"></span>`);
            }
            this._spinner.removeClass('text-secondary');
            this._spinner.addClass('text-success');
            this._spinner.css('animation-play-state', 'running');
        },
        disable: function (action) {
            console.debug('spinner disabled');

            let elapsed = Date.now() - this._timers[action];
            if (elapsed > 1000) {
                $(`#spinner-timer-value-${action}`).text(`${action}: ${elapsed / 1000} s`);
            }
            else {
                $(`#spinner-timer-value-${action}`).text(`${action}: ${elapsed} ms`);
            }

            this._spinner.css('animation-play-state', 'paused');
            this._spinner.removeClass('text-success');
            this._spinner.addClass('text-secondary');
        },

    }
});