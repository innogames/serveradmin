function reload_graph(image)
{
    // We should remove __auth_token GET parameter from the URL, because
    // it is generated based on time.  Graphite would return an error,
    // if we wouldn't remove it.  We don't need it on the browser anyway,
    // after first successful authentication.
    var src_split = image.attr('src').split('?');
    var params = src_split[1].split('&').filter(function(param) {
        return param.split('=')[0] != '__auth_token';
    }).join('&');

    // We will also add a comment to the URL not to let browser show
    // the cached image.
    image.attr('src', src_split[0] + '?' + params + '#' + Math.random());
}

function attach_graph_reload()
{
    $('img.graph').off('click').click(function() {
        reload_graph($(this));
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
            reload_graph(image);
        });
        $('<div title="' + title + '"></div>').append(data).dialog({
            'width': 550
        });
        attach_graph_reload();
    });
}


function attach_show_graph_description() {
    $('img.graph_desc_icon').off('click').click(function(){
        var graph_name = $(this).attr('data-graphname');
        $('#graph_desc_' + graph_name).dialog({
            'width': '30em',
            'graph_name': graph_name
        });
    });
}

$(attach_graph_reload);
$(attach_show_graph_description);
