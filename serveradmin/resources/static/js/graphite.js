function reload_graph(image)
{
    // We should remove __auth_token GET parameter from the URL, because
    // it is generated based on time.  Graphite would return an error,
    // if we wouldn't remove it.  We don't need it on the browser anyway,
    // after first successful authentication.
    let src_split = image.attr('src').split('?');
    let params = src_split[1].split('&').filter(function (param) {
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

function attach_show_graph_description() {
    $('img.graph_desc_icon').off('click').click(function(){
        let graph_name = $(this).attr('data-graphname');
        $('#graph_desc_' + graph_name).dialog({
            'width': '30em',
            'graph_name': graph_name
        });
    });
}

$(attach_graph_reload);
$(attach_show_graph_description);
