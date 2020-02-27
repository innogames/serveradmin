$(document).ready(function() {
   $('#commandd').autocomplete({
       delay: 100,
       minLength: 0,
       source: function(request, response) {
           let choices = [];

           spinner.enable();

           $('#help_command tr td:first-of-type').each(function() {
               choices.push({
                   'label': this.innerText,
                   'value': this.innerText,
               });
           });

           spinner.disable();

           response(choices);
       }
   })
});