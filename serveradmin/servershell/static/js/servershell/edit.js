$(document).ready(function() {
    $('.content .edit_value').each(function(index, element) {
        $(element).on('keyup', function() {
            let values;

            if (this.type === 'textarea') {
                values = this.value.split('\n');
            }
            else {
                values = [this.value];
            }

            let input = $(this);
            values.forEach(function(value) {
                if (!value.match(input.data('pattern')))
                    input.css('background-color', 'rgba(255, 0, 0, 0.21);');
                else
                    input.css('background-color', '');
            });
        });
    });
});