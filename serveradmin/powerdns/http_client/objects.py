import json
from enum import Enum
from typing import List

# todo maintain in single place
RecordType = Enum('record_type', ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'PTR', 'SOA', 'SRV', 'TXT'])
Changetype = Enum('changetype', ['REPLACE', 'DELETE'])


class RecordContent:
    content: str

    def __init__(self, content: str):
        self.content = content


class RRSet:
    """Represents a PowerDNS "Resource Record Set" which is a collection of records with the same name and type"""
    name: str
    type: RecordType
    ttl: int
    changetype: Changetype
    records: List[RecordContent]

    def __init__(self):
        self.changetype = 'REPLACE'


class RRSetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value  # Convert enums to their values
        elif isinstance(obj, RecordContent) or isinstance(obj, RRSet):
            return obj.__dict__  # Convert Record objects to their dictionaries
        else:
            return super().default(obj)


def get_ttl():
    """todo: somehow configurable via RecordsSettings?"""
    return 300
