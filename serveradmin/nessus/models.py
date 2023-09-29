"""Serveradmin - Nessus Integration

Copyright (c) 2023 InnoGames GmbH
"""

import json
import logging
import re
import time
import requests
from ipaddress import (
    IPv4Address,
    IPv4Network,
    ip_address,
    ip_network,
    AddressValueError,
)


class NessusAPI:
    """
    Class that communicates with Nessus API.
    """

    SESSION = "/session"
    FOLDERS = "/folders"
    SCANS = "/scans"
    SCAN_ID = SCANS + "/{scan_id}"
    HOST_VULN = SCAN_ID + "/hosts/{host_id}"
    PLUGINS = HOST_VULN + "/plugins/{plugin_id}"
    EXPORT = SCAN_ID + "/export"
    EXPORT_STATUS = EXPORT + "/{file_id}/status"
    EXPORT_HISTORY = EXPORT + "?history_id={history_id}"

    def __init__(
        self,
        username: str,
        password: str,
        url: str,
    ):
        """Initiates class instance.
        Establishes connection to nessus server.
        """
        self.api_keys = False
        self.user = username
        self.password = password
        self.base = url
        self.logger = logging.getLogger(__package__)

        self.api_token = ""

        self.session = requests.Session()
        self.session.verify = False
        self.session.stream = True
        self.session.headers = {
            "Origin": self.base,
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.8",
            "User-Agent": "Nessus-Helper",
            "Content-Type": "application/json",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": self.base,
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive",
            "X-Api-Token": "",
        }

        self.sess_token = self.login()

        self.session.headers["X-Cookie"] = "token=" + self.sess_token

    def login(self):
        """
        Log user into nessus.

        return string auth token that needs to be send with every later request in a cookie X-Cookie: token=<token>.
        """
        data = {"username": self.user, "password": self.password}
        response = self.request("/session", method="POST", data=json.dumps(data))
        if "Invalid Credentials" in response.text:
            self.logger.error(
                "Invalid credentials provided! Cannot authenticate to Nessus."
            )
            raise Exception(
                "[FAIL] Invalid credentials provided! Cannot authenticate to Nessus."
            )
        if response.status_code != 200:
            self.logger.error(
                "Couldn't authenticate! Error returned by Nessus: %s"
                % (json.loads(response.text)["error"])
            )
            raise Exception(
                "[FAIL] Couldn't authenticate! Error returned by Nessus: %s"
                % (json.loads(response.text)["error"])
            )
        self.logger.info(
            "Logged in to Nessus using password authentication and X-Api-Token - %s"
            % (self.api_token)
        )
        return json.loads(response.text)["token"]

    def get_api_token(self) -> None:
        """Refresh X-Api-Token value."""
        response = self.request("/nessus6.js?v=1642551183681", method="GET")
        offset = response.text.index('return g(a,[{key:"getApiToken",value:function(){')
        try:
            self.api_token = re.findall(
                r'return"(.*?)"\}\}', response.text[offset : offset + 100]
            )[0]
        except IndexError as e:
            logging.error(f"Failed to get X-Api-Token. Error: {e}")
        self.session.headers["X-Api-Token"] = self.api_token
        self.logger.info("Got new X-Api-Token from Nessus - %s" % (self.api_token))

    def request(self, url, data=None, method="POST", json_output=False):
        """
        Send request to nessus.

        :data: request body to send.
        :method: request method GET, POST, PUT, DELETE.
        :json_output: True / False.

        return dict
        """
        timeout = 0
        success = False
        method = method.lower()
        url = self.base + url
        self.logger.info("Requesting to url %s" % (url))

        while (timeout <= 30) and (not success):
            while 1:
                try:
                    response = getattr(self.session, method)(url, data=data)
                    break
                except requests.RequestException as e:
                    self.logger.error(
                        "[!] [CONNECTION ERROR] - Run into connection issue: %s" % (e)
                    )
                    self.logger.error("[!] Retrying in 10 seconds")
                    time.sleep(10)
                    pass
            if response.status_code == 412:
                self.get_api_token()
            elif response.status_code == 401:
                if url == self.base + self.SESSION:
                    break
                try:
                    timeout += 1
                    if self.api_keys:
                        continue
                    self.login()
                    self.logger.info("Session token refreshed")
                except requests.RequestException as e:
                    self.logger.error(
                        "Could not refresh session token. Reason: %s" % (str(e))
                    )
                    exit()
            else:
                success = True

        if json_output and len(response.text) > 0:
            return response.json()
        return response

    def create_scan(self, uuid, scan_name, folder_id, policy_id, target, receiver):
        """
        Create a scan.

        :uuid: user uid.
        :scan_name: name of the scan.
        :folder_id: ID of the folder where scan will be placed.
        :policy_id: policy uid string.
        :target: string of targets.
        :receiver: user email string.

        return dict.
        """
        target = ", ".join([str(element) for element in target])
        data = {
            "uuid": uuid,
            "settings": {
                "emails": receiver,
                "attach_report": True,
                "filter_type": "and",
                "filters": [],
                "launch_now": True,
                "enabled": True,
                "live_results": False,
                "name": scan_name,
                "description": "SCAN STARTED BY SERVERADMIN",
                "folder_id": folder_id,
                "scanner_id": "1",
                "policy_id": policy_id,
                "text_targets": target,
                "file_targets": "",
            },
        }
        return self.request(
            "/scans/", json_output=True, method="POST", data=json.dumps(data)
        )

    def get_scan_targets(self, scan_id):
        """
        Get the list of scan targets for a scan id.

        :scan_id: ID of scan.

        return list of strings.
        """
        req = self.request(
            method="GET", url="/scans/%s" % (str(scan_id)), json_output=True
        )["info"]
        if "targets" not in req.keys():
            self.launch_scan(scan_id)
            time.sleep(2)
            self.stop_scan(scan_id)
            return self.get_scan_targets(scan_id)
        return req["targets"]

    def check_if_running(self, new_targets):
        """
        Check if scan is in progress.

        :new_targets: list of targets to find a scan on and check if running.

        return list of strings.
        """
        running_scans = self.request(
            "/scanners/1/scans", json_output=True, method="GET"
        )
        scan_ids = set()
        if not running_scans["scans"]:
            return []
        for scan in running_scans["scans"]:
            existing_targets = self.get_scan_targets(scan["scan_id"]).split(",")
            existing_targets = [element.strip() for element in existing_targets]
            for existing_target in existing_targets:
                ip = None
                network = None
                for new_target in new_targets:
                    try:
                        ip = IPv4Address(existing_target)
                    except AddressValueError:
                        network = IPv4Network(existing_target)

                    if ip and ip_address(new_target) and ip == new_target:
                        scan_ids.add(str(scan["scan_id"]))
                    elif network and ip_address(new_target) and new_target in network:
                        scan_ids.add(str(scan["scan_id"]))
                    else:
                        try:
                            if (
                                network
                                and ip_network(new_target)
                                and network.overlaps(new_target)
                            ):
                                scan_ids.add(str(scan["scan_id"]))
                        except TypeError:
                            continue
        scan_ids = list(scan_ids)
        return scan_ids

    def stop_scan(self, scan_id):
        """
        Stop scan.

        :scan_id: ID of scan.

        :dict.
        """
        return self.request(
            "/scans/{}/stop".format(scan_id), method="POST", json_output=True
        )

    def launch_scan(self, scan_id):
        """
        Launch a scan.

        :scan_id: ID of scan.

        return dict.
        """
        return self.request("/scans/{}/launch".format(scan_id), method="POST")
