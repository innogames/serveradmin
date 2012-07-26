function reload_graph(hostname, graph, image_element)
{
    show_spinner();
    var reload_data = {'hostname': hostname, 'graph': graph};
    $.post(monitor_reload_url, reload_data, function(result) {
        console.log(reload_data);
        image_element.attr('src', image_element.attr('src') + '?' + Math.random());
        hide_spinner();
    });
}

function attach_graph_reload()
{
    $('img.cmp-graph').off('click').click(function() {
        var img = $(this);
        reload_graph(img.attr('data-hostname'), img.attr('data-graph'), img);
    });
}
