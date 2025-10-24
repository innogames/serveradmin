import json
import datetime
import ipaddress
import netaddr

from adminapi.dataset import MultiAttr


class ServeradminJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, MultiAttr):
            return list(obj)
        elif isinstance(obj, datetime.date):
            return obj.strftime('%Y-%m-%d')
        elif isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S%z')
        elif isinstance(obj, ipaddress.IPv4Address) or isinstance(obj, ipaddress.IPv6Address):
            return str(obj)
        elif isinstance(obj, netaddr.EUI):
            return str(obj)

        return json.JSONEncoder.default(self, obj)


