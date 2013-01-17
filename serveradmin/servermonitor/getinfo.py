from operator import itemgetter

from serveradmin.servermonitor.models import GraphValue, ServerData

def get_information(hostnames, hardware=None, disabled_features=None):
    if hardware is None:
        hardware = {}
        for hostname in hostnames:
            hardware[hostname] = {
                'hostname': hostname,
                'cpu': {},
                'io': {}
            }
    if disabled_features is None:
        disabled_features = set()

    fields = ['hostname', 'mem_free_dom0', 'mem_installed_dom0',
              'disk_free_dom0']
    if 'vserver' not in disabled_features:
        fields.append('running_vserver')
    
    server_data = ServerData.objects.filter(hostname__in=hostnames).only(
            *fields).values()
    graph_values = (GraphValue.objects.filter(hostname__in=hostnames,
            graph_name__in=['cpu_dom0_value_max_95', 'io2_dom0_value_max_95'])
            .values())
    periods = ('hourly', 'daily', 'yesterday')

    
    # Annotate hardware with data from server data table
    mem_free_sum = 0
    mem_free_count = 0
    mem_total_sum = 0
    mem_total_count = 0
    disk_free_sum = 0
    disk_free_count = 0
    
    cpu_aggregate = {}
    io_aggregate = {}
    for period in periods:
        cpu_aggregate[period] = {'sum': 0, 'count': 0}
        io_aggregate[period] = {'sum': 0, 'count': 0}
    
    to_bytes = 1024 * 1024
    for host_info in server_data:
        if host_info['mem_installed_dom0']:
            mem_total = host_info['mem_installed_dom0'] * to_bytes
        else:
            mem_total = None

        hardware[host_info['hostname']].update({
            'mem_free': host_info['mem_free_dom0']* to_bytes,
            'mem_total': mem_total,
            'disk_free': host_info['disk_free_dom0']* to_bytes
        })
        
        if 'vserver' not in disabled_features:
            hardware[host_info['hostname']]['guests'] = \
                    host_info['running_vserver'].split()
        
        if host_info['mem_free_dom0']:
            mem_free_sum += host_info['mem_free_dom0']
            mem_free_count += 1
        if host_info['mem_installed_dom0']:
            mem_total_sum += host_info['mem_installed_dom0']
            mem_total_count += 1
        if host_info['disk_free_dom0']:
            disk_free_sum += host_info['disk_free_dom0']
            disk_free_count += 1
    
    # Annotate hardware with the values for cpu/io
    for graph_value in graph_values:
        if graph_value['graph_name'] == 'cpu_dom0_value_max_95':
            hardware[graph_value['hostname']]['cpu'][graph_value['period']] = \
                    int(round(graph_value['value']))
            cpu_aggregate[graph_value['period']]['sum'] += graph_value['value']
            cpu_aggregate[graph_value['period']]['count'] += 1
        elif graph_value['graph_name'] == 'io2_dom0_value_max_95':
            hardware[graph_value['hostname']]['io'][graph_value['period']] = \
                    int(round(graph_value['value']))
            io_aggregate[graph_value['period']]['sum'] += graph_value['value']
            io_aggregate[graph_value['period']]['count'] += 1

    hardware = hardware.values()
    hardware.sort(key=itemgetter('hostname'))

    mem_free_sum *= to_bytes
    mem_total_sum *= to_bytes
    disk_free_sum *= to_bytes
    
    for period in periods:
        cpu_count = cpu_aggregate[period]['count']
        cpu_count = cpu_count if cpu_count else 1
        cpu_aggregate[period]['avg'] = round(cpu_aggregate[period]['sum'] /
                cpu_count, 2)

        io_count = io_aggregate[period]['count']
        io_count = io_count if io_count else 1
        io_aggregate[period]['avg'] = round(io_aggregate[period]['sum'] /
                io_count, 2)
    
    mem_free_count = mem_free_count if mem_free_count else 1
    mem_total_count = mem_total_count if mem_total_count else 1
    disk_free_count = disk_free_count if disk_free_count else 1
    
    return {
        'hosts': hardware,
        'mem_free_sum': mem_free_sum,
        'mem_free_avg': mem_free_sum / mem_free_count,
        'mem_total_sum': mem_total_sum,
        'mem_total_avg': mem_total_sum / mem_total_count,
        'disk_free_sum': disk_free_sum,
        'disk_free_avg': disk_free_sum / disk_free_count,
        'cpu_aggregate': cpu_aggregate,
        'io_aggregate': io_aggregate,
    }
