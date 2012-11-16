(function() {
    var NUM_POINTS = 50;
    var _sources = {};
    var _data = {};
    var _plots = {};

    function init()
    {
        for (var i = 0; i < LIVEGRAPH_PLOTS.length; ++i) {
            var plot_config = LIVEGRAPH_PLOTS[i];

            // Initialize sources
            for (var j = 0; j < plot_config['data'].length; ++j) {
                var source_name = plot_config['data'][j]['_data_source'];
                _sources[source_name] = true;
                _data[source_name] = [];
            }

            _plots[plot_config['name']] = $.plot(
                    plot_config['container'],
                    _prepare_plot_data(plot_config['data']),
                    plot_config['options']);
        }
        console.log(_sources);

        setInterval(function() {
            $.get(LIVEGRAPH_DATA_URL + '?hostname=' + LIVEGRAPH_HOSTNAME, update_data);
        }, 1000);
    }

    function update_data(data)
    {
        for (var source in _sources) {
            var graph_data = _data[source];
            var num_data_points = graph_data.length;
            var data_value = data['data'][source];
            if (typeof(data_value) == 'undefined') {
                continue;
            }
            var data_point = [data['time'], data_value];
            if (num_data_points >= NUM_POINTS) {
                for (var j = 1; j < num_data_points; ++j) {
                    graph_data[j - 1] = graph_data[j]; 
                }
            } else {
                for(var j = NUM_POINTS; j > 0; --j) {
                    graph_data.push([data['time'] - j * 1000, NaN]);
                }
            }
            graph_data[NUM_POINTS - 1] = data_point;
        }
        update_plots();
    }

    function update_plots()
    {
        for (var i = 0; i < LIVEGRAPH_PLOTS.length; ++i) {
            var plot = LIVEGRAPH_PLOTS[i];
            var plot_key = plot['name'];
            _plots[plot_key].setData(_prepare_plot_data(plot['data']));
            _plots[plot_key].setupGrid();
            _plots[plot_key].draw();

        }
    }

    function _prepare_plot_data(plot_data)
    {
        for (var i = 0; i < plot_data.length; i++) {
            var entry = plot_data[i];
            entry['data'] = _data[entry['_data_source']];
            //console.log(entry);
        }
        return plot_data;
    }


    init();
})();
