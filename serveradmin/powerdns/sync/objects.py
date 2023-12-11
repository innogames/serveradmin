import json
from enum import Enum
from typing import List

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


class RRSet:
    """Represents a PowerDNS "Resource Record Set" which is a collection of records with the same name and type"""
    name: str
    type: RecordType
    ttl: int
    changetype: Changetype
    records: List[RecordContent]

    def __init__(self):
        self.changetype = 'REPLACE'

    def __eq__(self, other):
        if self.name != other.name:
            return False
        if self.type != other.type:
            return False
        if self.ttl != other.ttl:
            return False
        if sorted(self.records) != sorted(other.records):
            return False
        return True

    def __str__(self):
        return f"{self.name} {self.type} {self.ttl} {self.records}"

    def __repr__(self):
        return str(self)


class RRSetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value  # Convert enums to their values
        elif isinstance(obj, RecordContent) or isinstance(obj, RRSet):
            return obj.__dict__  # Convert Record objects to their dictionaries
        else:
            return super().default(obj)

