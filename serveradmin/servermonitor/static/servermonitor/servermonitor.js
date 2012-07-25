function reload_graph(hostname, graph, image_element)
{
    var container = $('<div style="position:relative;"></div>');
    var msg = $('<span>reloading ...</span>').css({
        'position': 'absolute',
        'top': 0,
        'left': 0,
        'color': '#fff',
        'background': '#000',
        'font-weight': 'bold',
        'padding': '5px',
    });
    container.append(msg);
    image_element.replaceWith(container);
    container.append(image_element);
    var reload_data = {'hostname': hostname, 'graph': graph};
    $.post(monitor_reload_url, reload_data, function(result) {
        image_element.attr('src', image_element.attr('src') + '?' + Math.random());
        image_element.remove();
        container.replaceWith(image_element);
    });
}
