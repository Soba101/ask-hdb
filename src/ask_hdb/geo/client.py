"""Polite OneMap requests with optional, in-memory authentication."""

import os
import time

import httpx
from dotenv import load_dotenv

SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
TOKEN_URL = "https://www.onemap.gov.sg/api/auth/post/getToken"


class StopGeocoding(Exception):
    """Authentication failed; continuing would repeat rejected requests."""


class GeocodeError(Exception):
    """A block can be retried on a later run."""


class OneMap:
    def __init__(self, client, credentials=None, sleep=time.sleep):
        self.client = client
        self.credentials = credentials
        self.sleep = sleep
        self.token = None

    def _request(self, method, url, **kwargs):
        # Pause before every request, including retries and token requests.
        headers = {"User-Agent": "ask-hdb/0.1", **kwargs.pop("headers", {})}
        for attempt in range(5):
            self.sleep(0.5)
            try:
                response = self.client.request(
                    method, url, headers=headers,
                    timeout=15, **kwargs,
                )
            except httpx.RequestError:
                response = None
            if response is not None:
                if response.status_code == 403:
                    raise StopGeocoding("OneMap returned HTTP 403; stopped.")
                if response.status_code != 429 and response.status_code < 500:
                    return response
            if attempt < 4:
                self.sleep(2 ** attempt)
        raise GeocodeError("OneMap request failed after retries")

    def _refresh_token(self):
        response = self._request("POST", TOKEN_URL, json=self.credentials)
        if response.status_code == 401:
            raise StopGeocoding("OneMap token request returned HTTP 401; stopped.")
        if response.status_code != 200:
            raise GeocodeError("OneMap token request failed")
        try:
            self.token = response.json()["access_token"]
            if not isinstance(self.token, str) or not self.token:
                raise ValueError
        except (KeyError, ValueError, TypeError):
            raise GeocodeError("OneMap token response was invalid") from None

    def search(self, query: str) -> dict:
        if self.credentials and self.token is None:
            self._refresh_token()
        params = {"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}
        for refresh in range(2):
            headers = {"Authorization": self.token} if self.token else {}
            response = self._request("GET", SEARCH_URL, params=params, headers=headers)
            if response.status_code == 401:
                if self.credentials and refresh == 0:
                    self._refresh_token()
                    continue
                raise StopGeocoding("OneMap returned HTTP 401; stopped.")
            if response.status_code != 200:
                raise GeocodeError("OneMap search failed")
            try:
                body = response.json()
                # Some successful searches also carry a missing-token message.
                if not isinstance(body, dict) or not isinstance(body.get("results"), list):
                    raise TypeError
                if body.get("error") and not body["results"]:
                    raise ValueError
                if not all(isinstance(row, dict) for row in body["results"]):
                    raise ValueError
                return body
            except (ValueError, TypeError):
                raise GeocodeError("OneMap search response was invalid") from None
        raise GeocodeError("OneMap search failed")


def load_credentials():
    load_dotenv()
    email, password = os.getenv("ONEMAP_EMAIL"), os.getenv("ONEMAP_PASSWORD")
    return {"email": email, "password": password} if email and password else None
