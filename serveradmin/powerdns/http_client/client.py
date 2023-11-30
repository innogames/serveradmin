import json
import logging
import requests

from django.conf import settings

from serveradmin.powerdns.http_client.utils import ensure_trailing_dot
from serveradmin.powerdns.http_client.objects import RRSet, RRSetEncoder, RecordContent

logger = logging.getLogger(__name__)


class PowerDNSApiClient:
    """Client for the PowerDNS API.
    See https://doc.powerdns.com/authoritative/http-api/zone.html
    """

    def __init__(self):
        self.endpoint = settings.POWERDNS_API_ENDPOINT
        self.api_key = settings.POWERDNS_API_SECRET_KEY
        self.server_id = settings.POWERDNS_API_SERVER_ID
        self.headers = {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }

    def get_zones(self):
        url = f"{self.endpoint}/api/v1/servers/{self.server_id}/zones"
        response = requests.get(url, headers=self.headers)
        self._handle_response_errors(response)

        return response.json()

    def get_zone(self, zone: str):
        zone = ensure_trailing_dot(zone)

        url = f"{self.endpoint}/api/v1/servers/{self.server_id}/zones/{zone}"
        response = requests.get(url, headers=self.headers)
        self._handle_response_errors(response)

        logger.warning("matze44", response.text)
        logger.warning("matze45", response.json())

        return response.json()

    def get_rrsets(self, zone: str, domain_name: str):
        zone = ensure_trailing_dot(zone)

        url = f"{self.endpoint}/api/v1/servers/{self.server_id}/zones/{zone}?rrset_name={domain_name}"
        response = requests.get(url, headers=self.headers)
        self._handle_response_errors(response)

        data = response.json()['rrsets']

        rrsets = []
        for raw in data:
            rrset = RRSet()
            rrset.name = raw['name']
            rrset.type = raw['type']
            rrset.ttl = raw['ttl']
            rrset.records = []
            for record in raw['records']:
                rrset.records.append(RecordContent(record['content']))
            rrsets.append(rrset)

        return rrsets

    def create_zone(self, zone: str, kind: str):
        zone = ensure_trailing_dot(zone)

        url = f"{self.endpoint}/api/v1/servers/{self.server_id}/zones"
        payload = {
            "name": zone,
            "kind": kind,
        }
        response = requests.post(url, headers=self.headers, json=payload)
        self._handle_response_errors(response)

        return response.json()

    def create_or_update_rrsets(self, zone: str, records: list[RRSet]):
        zone = ensure_trailing_dot(zone)

        url = f"{self.endpoint}/api/v1/servers/{self.server_id}/zones/{zone}"
        payload = json.dumps({"rrsets": records}, cls=RRSetEncoder)

        logger.warning(f"matze payload {payload}")

        response = requests.patch(url, headers=self.headers, data=payload)
        self._handle_response_errors(response)

    def delete_zone(self, zone: str):
        zone = ensure_trailing_dot(zone)

        url = f"{self.endpoint}/api/v1/servers/{self.server_id}/zones/{zone}."
        response = requests.delete(url, headers=self.headers)
        self._handle_response_errors(response)

        return response.json()

    def _handle_response_errors(self, response):
        if response.status_code >= 400:
            raise PowerDNSApiException(f"Error {response.status_code}: {response.text}")


class PowerDNSApiException(Exception):
    """Custom exception class for PowerDNS API errors."""
    pass
