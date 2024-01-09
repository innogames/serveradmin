import json
from enum import Enum
from typing import Set

from serveradmin.powerdns.sync.utils import ensure_canonical

"""
The following classes are used to represent the data that is sent to the PowerDNS API.
The API expects JSON and the classes are used to convert the data to JSON.
"""

RecordType = Enum('record_type', [
    'A',
    'AAAA',
    'CNAME',
    'MX',
    'NS',
    'PTR',
    'SSHFP',
    'SOA',
    'SRV',
    'TXT',
])
Changetype = Enum('changetype', [
    'REPLACE',
    'DELETE',
])


class RecordContent:
    content: str

    def __init__(self, content: str):
        self.content = content

    def __str__(self):
        return self.content

    def __repr__(self):
        return self.content

    def __eq__(self, other):
        return self.content == other.content

    def __lt__(self, other):
        return self.content < other.content

    def __hash__(self):
        return hash(self.content)


class RRSet:
    """Represents a PowerDNS "Resource Record Set" which is a collection of records with the same name and type"""
    name: str
    type: RecordType
    ttl: int
    changetype: Changetype
    records: Set[RecordContent]

    def __init__(self, name: str, record_type: RecordType, ttl: int = 3600):
        self.changetype = 'REPLACE'
        self.ttl = ttl
        self.records = set()
        self.name = ensure_canonical(name)
        self.type = record_type

    def __eq__(self, other):
        if self.name != other.name:
            return False
        if self.type != other.type:
            return False
        if self.ttl != other.ttl:
            return False
        if sorted(self.records) != sorted(other.records):
            if self.type == 'SOA':
                # todo check serial in the SOA record
                return True
            return False
        return True

    def __str__(self):
        return f"{self.name} {self.type} {self.ttl} {self.records}"

    def __repr__(self):
        return str(self)


class RRSetEncoder(json.JSONEncoder):
    """Special JSON encoder that can convert our custom powerdns structure to JSON"""
    def default(self, obj):
        if isinstance(obj, Enum):
            # Convert enums to their values
            return obj.value
        elif isinstance(obj, RecordContent) or isinstance(obj, RRSet):
            # Convert Record objects to their dictionaries
            return obj.__dict__
        elif isinstance(obj, set):
            # Convert set to list because JSON supports list
            return list(obj)
        else:
            return super().default(obj)
