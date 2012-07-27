function reload_graph(hostname, graph, image_element, do_hide_spinner)
{
    if (!do_hide_spinner) {
        show_spinner();
    }
    var reload_data = {'hostname': hostname, 'graph': graph};
    $.post(monitor_reload_url, reload_data, function(result) {
        image_element.attr('src', image_element.attr('src') + '?' + Math.random());
        hide_spinner();
    });
}

function attach_graph_reload()
{
    $('img.graph').off('click').click(function() {
        var img = $(this);
        reload_graph(img.attr('data-hostname'), img.attr('data-graph'), img);
    });
}
