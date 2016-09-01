function choose_ip_addr(input_field, network) {
    var url = servershell_choose_ip_addr_url;
    if (network)
        url += '?network=' + network;

    $.get(url, function(xhtml) {
        var dialog = $('<div title="Choose IP Address"></div>').html(xhtml);
        dialog.scrollTop(0);
        dialog.find('.network_select').click(function(ev) {
            choose_ip_addr(input_field, $(this).text());
            dialog.dialog('close');
        });
        dialog.find('.ip_addr_select').click(function(ev) {
            var ip_addr = $(this).text();
            input_field.val(ip_addr);
            dialog.dialog('close');
        });
        dialog.dialog({
            'width': '400',
            'height': '500'
        });
    });
}
