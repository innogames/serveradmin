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

    };

    // Find pagination controls with in forms and submit the form instead of
    // submitting the links.
    $('.pagination.form a').each(function(index, anchor) {
        anchor.onclick = function(event) {
            let form = this.closest('form');
            if (form) {
                event.preventDefault();

                let page = this.href.split('=').pop();
                let input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'page';
                input.value = page;
                form.append(input);
                form.submit();
            }
        };
    });
});
