import json
import logging
import requests

from django.conf import settings

from serveradmin.powerdns.http_client.utils import ensure_canonical, divide_chunks
from serveradmin.powerdns.http_client.objects import RRSet, RRSetEncoder, RecordContent

logger = logging.getLogger(__package__)


class PowerDNSApiClient:
    """Client for the PowerDNS API.
    See https://doc.powerdns.com/authoritative/http-api/zone.html
    """

    CHUNK_SIZE = 500

    def __init__(self):
        self.api_url = f"{settings.POWERDNS_API_ENDPOINT}/api/v1/servers/{settings.POWERDNS_API_SERVER_ID}"
        self.headers = {
            'X-API-Key': settings.POWERDNS_API_SECRET_KEY,
            'Content-Type': 'application/json'
        }

    def get_zones(self):
        url = f"{self.api_url}/zones"
        response = requests.get(url, headers=self.headers)
        self._handle_response_errors(response)

        return response.json()

    def get_zone(self, zone: str):
        zone = ensure_canonical(zone)

        url = f"{self.api_url}/zones/{zone}"
        response = requests.get(url, headers=self.headers)
        self._handle_response_errors(response)

        return response.json()

    def get_rrsets(self, zone: str, domain_name: str) -> dict[str, RRSet]:
        """Get all RRSet objects for a given domain name, indexed by record type"""
        zone = ensure_canonical(zone)

        url = f"{self.api_url}/zones/{zone}?rrset_name={domain_name}"
        response = requests.get(url, headers=self.headers)
        self._handle_response_errors(response)

        data = response.json()['rrsets']

        rrsets = {}
        for raw in data:
            rrset = RRSet()
            rrset.name = raw['name']
            rrset.type = raw['type']
            rrset.ttl = raw['ttl']
            rrset.records = []
            for record in raw['records']:
                rrset.records.append(RecordContent(record['content']))
            rrsets[rrset.type] = rrset

        return rrsets

    def create_zone(self, zone: str, kind: str):
        zone = ensure_canonical(zone)

        url = f"{self.api_url}/zones"
        payload = {
            "name": zone,
            "kind": kind,
        }
        response = requests.post(url, headers=self.headers, json=payload)
        self._handle_response_errors(response)

        return response.json()

    def create_or_update_rrsets(self, zone: str, records: list[RRSet]):
        zone = ensure_canonical(zone)
        url = f"{self.api_url}/zones/{zone}"

        for chunk in divide_chunks(records, self.CHUNK_SIZE):
            payload = json.dumps({"rrsets": chunk}, cls=RRSetEncoder)

            logger.info(f"rrset update: {payload}")

            response = requests.patch(url, headers=self.headers, data=payload)
            self._handle_response_errors(response)

    # todo maybe remove again
    def delete_zone(self, zone: str):
        zone = ensure_canonical(zone)

        url = f"{self.api_url}/zones/{zone}."
        response = requests.delete(url, headers=self.headers)
        self._handle_response_errors(response)

        return response.json()

    @staticmethod
    def _handle_response_errors(response):
        if response.status_code >= 400:
            raise PowerDNSApiException(f"Error {response.status_code}: {response.text}")


class PowerDNSApiException(Exception):
    """Custom exception class for PowerDNS API errors."""
    pass
