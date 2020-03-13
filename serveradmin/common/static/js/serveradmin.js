$(document).ready(function() {
    // Mark the current page as active in navigation
    let current = $('nav .nav-link[href="' + window.location.pathname + '"]');
    if (current.length)
        current[0].classList.add('active');

    // This is our progress spinner we can call e.g. spinner.enable() from
    // everywhere when ever we need it for example when doing long running
    // ajax requests for the servershell search.
    window.spinner = {
        _id: null,
        _running: 0,
        _spinner: $('#spinner'),
        _counter: $('#spinner-counter'),
        _value: $('#spinner-counter-value'),
        _toggle_css: function() {
            if (this._spinner.hasClass('text-success')) {
                this._spinner.removeClass('text-success');
                this._spinner.addClass('text-secondary');

                this._counter.removeClass('text-success');
                this._counter.addClass('text-secondary');

                this._spinner.css('animation-play-state', 'paused');
            }
            else {
                this._spinner.removeClass('text-secondary');
                this._spinner.addClass('text-success');

                this._counter.removeClass('text-secondary');
                this._counter.addClass('text-success');

                this._spinner.css('animation-play-state', 'running');
            }
        },
        enable: function () {
            this._running++;
            if (this._running > 1) {
                return;
            }

            this._value.html(0);
            this._toggle_css();

            this._id = setInterval(function () {
                spinner._value.html(Number.parseInt(spinner._value.html()) + 1);
            }, 1);
        },
        disable: function () {
            this._running--;

            if (this._running === 0) {
                this._toggle_css();
                clearInterval(this._id);
            }
        },

    }
});