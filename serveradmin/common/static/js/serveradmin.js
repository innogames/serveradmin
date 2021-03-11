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
        _startedAt: 0,
        _spinner: $('#spinner'),
        enable: function () {
            console.debug('spinner enabled');
            this._startedAt = Date.now();

            this._spinner.removeClass('text-secondary');
            this._spinner.addClass('text-success');
            this._spinner.css('animation-play-state', 'running');
        },
        disable: function () {
            console.debug('spinner disabled');

            let elapsed = Date.now() - this._startedAt;
            if (elapsed > 1000) {
                $('#spinner-timer-value').html(`${elapsed / 1000} s`);
            }
            else {
                $('#spinner-timer-value').html(`${elapsed} ms`);
            }

            this._spinner.css('animation-play-state', 'paused');
            this._spinner.removeClass('text-success');
            this._spinner.addClass('text-secondary');
        },

    }
});