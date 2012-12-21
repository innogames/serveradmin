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
            'legend': {'position': 'nw', 'backgroundOpacity': 0.2},
            'series': {'shadowSize': 0}
        }
    },
    'usage': {
        'name': 'usage',
        'container': '#livegraph_usage',
        'data': [
            {'label': 'user', '_data_source': 'usage_user'},
            {'label': 'system', '_data_source': 'usage_system'},
            {'label': 'nice', '_data_source': 'usage_nice'}
        ],
        'options': {
            'xaxis': {'mode': 'time'},
            'yaxis': {'min': 0, 'max': 100},
            'legend': {'position': 'nw', 'backgroundOpacity': 0.2},
            'series': {'shadowSize': 0}
        }
    },
    'io': {
        'name': 'io',
        'container': '#livegraph_io',
        'data': [
            {'label': 'write', '_data_source': 'io_w_per'},
            {'label': 'read', '_data_source': 'io_r_per'},
        ],
        'options': {
            'xaxis': {'mode': 'time'},
            'yaxis': {'min': 0, 'max': 100},
            'legend': {'position': 'nw', 'backgroundOpacity': 0.2},
            'series': {
                'stack': true,
                'lines': {'fill': true},
                'shadowSize': 0
            },
        }
    }
};

(function() {
    var polls = {};
    function get_new_data() {
        for (hostname in polls) {
            if (!polls[hostname].length) {
                continue;
            }
            
            var request_started = (new Date()).getTime();
            $.get(livegraph_url + '?hostname=' + hostname, function(data) {
                for (var i = 0; i < polls[hostname].length; ++i) {
                    polls[hostname][i](data);
                }
                if (polls[hostname].length) {
                    var time_taken = (new Date()).getTime() - request_started;
                    var timeout = Math.max(0, 1000 - time_taken);
                    setTimeout(get_new_data, timeout);
                }
            });
        }
    }

    window.livegraph_poller = {
        'register': function(hostname, callback)
        {
            var start_polling = false;
            if (typeof(polls[hostname]) == 'undefined' || !polls[hostname].length) {
                polls[hostname] = [];
                start_polling = true;
            }
            var poll = polls[hostname];
            poll.push(callback);
            if (start_polling) {
                get_new_data();
            }
        },
        'unregister': function(hostname, callback)
        {
            var registered_cbs = polls[hostname];
            var new_registered_cbs = [];
            for (var i = 0; i < registered_cbs.length; ++i) {
                if (callback != registered_cbs[i]) {
                    new_registered_cbs.push(registered_cbs[i]);
                }
            }
            polls[hostname] = new_registered_cbs;
        }
    };
})();

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
    
    this._update_data = this._update_data.bind(this);
    
    livegraph_poller.register(this.hostname, this._update_data);
}

LiveGraph.prototype.stop = function()
{
    livegraph_poller.unregister(this.hostname, this._update_data);
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
