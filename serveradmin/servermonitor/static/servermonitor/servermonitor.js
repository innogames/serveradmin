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

function open_graph_popup()
{
    var handle = $(this);
    var params = {
        'hostname': handle.attr('data-hostname'),
        'graph': handle.attr('data-graph')
    }
    var title = params['graph'] + ' on ' + params['hostname'];
    var query_str = '?' + $.param(params);
    $.get(monitor_graph_popup_url + query_str, function(data) {
        var image = $(data).find('.graph');
        image.on('load', function() {
            image.off('load');
            reload_graph(params['hostname'], params['graph'], image, true);
        });
        $('<div title="' + title + '"></div>').append(data).dialog({
            'width': 550
        });
        attach_graph_reload();
    });
}


function attach_show_graph_description() {
    $('img.graph_desc_icon').off('click').click(function(){
        var img = $(this);
        var graph_name = img.attr('data-graphname');
        $('#graph_desc_' + graph_name).dialog({
            'width': '30em',
            'graph_name': graph_name
        });
    });
}

$(attach_show_graph_description);
