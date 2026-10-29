"""Polite OneMap requests with optional, in-memory authentication."""

import os
import threading
import time

import httpx
from dotenv import load_dotenv

from ask_hdb.geo.route import RouteError, parse_route

SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
TOKEN_URL = "https://www.onemap.gov.sg/api/auth/post/getToken"
ROUTE_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"


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
        self.expires = 0.0
        self.lock = threading.Lock()  # one token refresh at a time

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

    def _route_token(self, stale=None, timeout=8.0):
        """A token for page requests: one attempt, no sleep, one refresh at a time (sync routes run in threads)."""
        with self.lock:
            if self.token and self.token != stale and time.time() < self.expires - 60:
                return self.token  # another thread already refreshed it
            try:
                response = self.client.request("POST", TOKEN_URL, json=self.credentials, timeout=timeout,
                                            headers={"User-Agent": "ask-hdb/0.1"})
                body = response.json() if response.status_code == 200 else None
            except (httpx.RequestError, ValueError):
                raise RouteError("unavailable") from None
            if response.status_code in (401, 403):
                raise RouteError("no_credentials")  # OneMap rejected the email and password
            token = body.get("access_token") if isinstance(body, dict) else None
            if not isinstance(token, str) or not token:
                raise RouteError("unavailable")
            try:
                self.expires = float(body["expiry_timestamp"])
            except (KeyError, TypeError, ValueError):
                self.expires = time.time() + 3600  # unknown expiry: refresh after an hour
            self.token = token
            return token

    def route(self, start, end, attempts=1, timeout=8.0, pause=0.0):
        """Walking route between (lat, lng) pairs. Page requests use one attempt, a short timeout and no sleep."""
        if not self.credentials:
            raise RouteError("no_credentials")
        params = {"start": f"{start[0]},{start[1]}", "end": f"{end[0]},{end[1]}", "routeType": "walk"}
        stale = None
        for refresh in range(2):
            token = self._route_token(stale, timeout)
            response = None
            for attempt in range(attempts):
                if pause:
                    self.sleep(pause)
                try:
                    response = self.client.request("GET", ROUTE_URL, params=params, timeout=timeout,
                                               headers={"Authorization": token, "User-Agent": "ask-hdb/0.1"})
                except httpx.RequestError:
                    response = None
                    continue
                if response.status_code < 500:
                    break
            if response is None or response.status_code >= 500:
                raise RouteError("unavailable")
            if response.status_code == 401 and refresh == 0:
                stale = token
                continue  # the token may have expired early: refresh once
            break
        code = {200: None, 404: "no_route", 429: "quota"}.get(response.status_code, "unavailable")
        if code:
            raise RouteError(code)
        try:
            return parse_route(response.json())
        except ValueError:
            raise RouteError("unavailable") from None

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
