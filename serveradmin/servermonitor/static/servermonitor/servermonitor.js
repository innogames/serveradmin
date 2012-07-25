function reload_graph(hostname, graph, image_element)
{
    show_spinner();
    var reload_data = {'hostname': hostname, 'graph': graph};
    $.post(monitor_reload_url, reload_data, function(result) {
        image_element.attr('src', image_element.attr('src') + '?' + Math.random());
        hide_spinner();
    });
}
