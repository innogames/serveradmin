var LIVEGRAPH_TEMPLATES = {
    'load': {
        'name': 'load',
        'container': '#livegraph_load',
        'data': [
            {'label': 'load1', '_data_source': 'load1'},
            {'label': 'load5', '_data_source': 'load5'},
            {'label': 'load15', '_data_source': 'load15'}
        ],
        'options': {
            'xaxis': {'mode': 'time'},
            'legend': {'position': 'nw', 'backgroundOpacity': 0.2}
        }
    },
    'usage': {
        'name': 'usage',
        'container': '#livegraph_usage',
        'data': [
            {'label': 'user', '_data_source': 'usage_user'},
            {'label': 'system', '_data_source': 'usage_system'},
            {'label': 'nice', '_data_source': 'usage_nice'}
        ]
    }
};

function LiveGraph(template, hostname)
{
    this.template = template;
    this.hostname = hostname;
    this._num_points = 100;
    this._sources = {};
    this._data = {};
    this._plot = null;
    this._timeout = null;
    
    // Initialize sources 
    for (var i = 0; i < this.template['data'].length; ++i) {
        var source_name = this.template['data'][i]['_data_source'];
        this._sources[source_name] = true;
        this._data[source_name] = [];
    }
    
    // Create plot
    this._plot = $.plot(
            this.template.container,
            this._prepare_plot_data(this.template['data']),
            this.template['options']);
    
    // Start polling for data
    var that = this;
    function get_new_data() {
        $.get(livegraph_url + '?hostname=' + that.hostname, function(data) {
            that._update_data(data);
            if (that._timeout !== false) {
                that._timeout = setTimeout(get_new_data, 1000);
            }
        });
    }
    
    get_new_data();
}

LiveGraph.prototype.stop = function()
{
    this._timeout = false;
}

LiveGraph.prototype._update_data = function(data)
{
    for (var source in this._sources) {
        var graph_data = this._data[source];
        var num_data_points = graph_data.length;
        var data_value = data['data'][source];

        if (typeof(data_value) == 'undefined') {
            continue;
        }
        
        var data_point = [data['time'], data_value];
        // We have enough data points, so we shift every point
        // to have a slot for the new datapoint
        if (num_data_points >= this._num_points) {
            for (var j = 1; j < num_data_points; ++j) {
                graph_data[j - 1] = graph_data[j]; 
            }
        // We don't have enough points, fill data array with NaN
        } else {
            for(var j = this._num_points; j > 0; --j) {
                graph_data.push([data['time'] - j * 1000, NaN]);
            }
        }
        graph_data[this._num_points - 1] = data_point;

    }
    
    this._plot.setData(this._prepare_plot_data(this.template['data']));
    this._plot.setupGrid();
    this._plot.draw();
}

LiveGraph.prototype._prepare_plot_data = function(plot_data)
{
    for (var i = 0; i < plot_data.length; i++) {
        var entry = plot_data[i];
        entry['data'] = this._data[entry['_data_source']];
    }
    return plot_data;
}

var _livegraphs = {};
function start_livegraph(hostname, server_id)
{
    var graphs = [];

    for (var name in LIVEGRAPH_TEMPLATES) {
        var tpl = {};
        for (var key in LIVEGRAPH_TEMPLATES[name]) {
            tpl[key] = LIVEGRAPH_TEMPLATES[name][key];
        }
        tpl['container'] = tpl['container'] + '_' + server_id;
        graphs.push(new LiveGraph(tpl, hostname));
    }
    _livegraphs[hostname] = graphs;
}

function stop_livegraph(hostname)
{
    var graphs = _livegraphs[hostname];
    for (var i = 0; i < graphs.length; i++) {
        graphs[i].stop();
    }
}
