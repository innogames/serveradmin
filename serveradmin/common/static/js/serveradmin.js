$(document).ready(function() {
    // Mark the current page as active in navigation
    let current = $('nav .nav-link[href="' + window.location.pathname + '"]');
    if (current.length)
        current[0].classList.add('active');

    // This is our progress spinner we can call e.g. spinner.enable() from
    // everywhere when ever we need it for example when doing long running
    // ajax requests for the servershell search.
    spinner = {
        enable: function () {
            $('#spinner').show();
            $('#spinner-counter').show();

            let update_spinner = function() {
                let element = $('#spinner-counter-time');
                element.html(Number.parseInt(element.html()) + 1);
                setTimeout(update_spinner, 1);
            };
            setTimeout(update_spinner, 1);
        },
        disable: function () {
            $('#spinner').hide();
            $('#spinner-counter').hide();
            $('#spinner-counter-time').html(0);
            $('#spinner-counter-unit').html('ms');
        },
    }
});