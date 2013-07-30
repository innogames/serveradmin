function choose_ip(input_field)
{
    $.get(iprange_chooseip_url, function(xhtml) {
        var dialog = $('<div title="Choose IP"></div>').html(xhtml);
        dialog.find('.iprange_select').click(function(ev) {
            var range_id = $(this).text();
            $.get(iprange_chooseip_url + '?range_id=' + range_id, function(xhtml) {
                dialog.html(xhtml);
                dialog.scrollTop(0);
                dialog.find('.ip_select').click(function(ev) {
                    var ip_addr = $(this).text();
                    input_field.val(ip_addr);
                    dialog.dialog('close');
                });
            });
        });
        dialog.dialog({
            'width': '400',
            'height': '500'
        });
    });
}
