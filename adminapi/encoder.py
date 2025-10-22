import json

from adminapi.dataset import MultiAttr


class ServeradminJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, MultiAttr):
            return list(obj)

        return json.JSONEncoder.default(self, obj)


