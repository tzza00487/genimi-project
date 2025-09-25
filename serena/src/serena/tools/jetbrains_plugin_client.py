"""
Client for the Serena JetBrains Plugin
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional, Self, TypeVar

import requests
from sensai.util.string import ToStringMixin

from serena.project import Project

T = TypeVar("T")
log = logging.getLogger(__name__)


class SerenaClientError(Exception):
    """Base exception for Serena client errors."""


class ConnectionError(SerenaClientError):
    """Raised when connection to the service fails."""


class APIError(SerenaClientError):
    """Raised when the API returns an error response."""


class ServerNotFoundError(Exception):
    """Raised when the plugin's service is not found."""


class JetBrainsPluginClient(ToStringMixin):
    """
    Python client for the Serena Backend Service.

    Provides simple methods to interact with all available endpoints.
    """

    BASE_PORT = 0x5EA2
    last_port: int | None = None

    def __init__(self, port: int, timeout: int = 30):
        self.base_url = f"http://127.0.0.1:{port}"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    def _tostring_includes(self) -> list[str]:
        return ["base_url", "timeout"]

    @classmethod
    def from_project(cls, project: Project) -> Self:
        resolved_path = Path(project.project_root).resolve()

        if cls.last_port is not None:
            client = JetBrainsPluginClient(cls.last_port)
            if client.matches(resolved_path):
                return client

        for port in range(cls.BASE_PORT, cls.BASE_PORT + 20):
            client = JetBrainsPluginClient(port)
            if client.matches(resolved_path):
                log.info("Found JetBrains IDE service at port %d for project %s", port, resolved_path)
                cls.last_port = port
                return client

        raise ServerNotFoundError("Found no Serena service in a JetBrains IDE instance for the project at " + str(resolved_path))

    def matches(self, resolved_path: Path) -> bool:
        try:
            return Path(self.project_root()).resolve() == resolved_path
        except ConnectionError:
            return False

    def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"

        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=self.timeout)
            elif method.upper() == "POST":
                json_data = json.dumps(data) if data else None
                response = self.session.post(url, data=json_data, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()

            # Try to parse JSON response
            try:
                return self._pythonify_response(response.json())
            except json.JSONDecodeError:
                # If response is not JSON, return raw text
                return {"response": response.text}

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Serena service at {url}: {e}")
        except requests.exceptions.Timeout as e:
            raise ConnectionError(f"Request to {url} timed out: {e}")
        except requests.exceptions.HTTPError:
            raise APIError(f"API request failed with status {response.status_code}: {response.text}")
        except requests.exceptions.RequestException as e:
            raise SerenaClientError(f"Request failed: {e}")

    @staticmethod
    def _pythonify_response(response: T) -> T:
        """
        Converts dictionary keys from camelCase to snake_case recursively.

        :response: the response in which to convert keys (dictionary or list)
        """
        to_snake_case = lambda s: "".join(["_" + c.lower() if c.isupper() else c for c in s])

        def convert(x):  # type: ignore
            if isinstance(x, dict):
                return {to_snake_case(k): convert(v) for k, v in x.items()}
            elif isinstance(x, list):
                return [convert(item) for item in x]
            else:
                return x

        return convert(response)

    def project_root(self) -> str:
        response = self._make_request("GET", "/status")
        return response["project_root"]

    def find_symbol(
        self, name_path: str, relative_path: str | None = None, include_body: bool = False, depth: int = 0, include_location: bool = False
    ) -> dict[str, Any]:
        """
        Find symbols by name.

        :param name_path: the name path to match
        :param relative_path: the relative path to which to restrict the search
        :param include_body: whether to include symbol body content
        :param depth: depth of children to include (0 = no children)

        :return: Dictionary containing 'symbols' list with matching symbols
        """
        request_data = {
            "namePath": name_path,
            "relativePath": relative_path,
            "includeBody": include_body,
            "depth": depth,
            "includeLocation": include_location,
        }
        return self._make_request("POST", "/findSymbol", request_data)

    def find_references(self, name_path: str, relative_path: str) -> dict[str, Any]:
        """
        Find references to a symbol.

        :param name_path: the name path of the symbol
        :param relative_path: the relative path
        :return: dictionary containing 'symbols' list with symbol references
        """
        request_data = {"namePath": name_path, "relativePath": relative_path}
        return self._make_request("POST", "/findReferences", request_data)

    def get_symbols_overview(self, relative_path: str) -> dict[str, Any]:
        """
        :param relative_path: the relative path to a source file
        """
        request_data = {"relativePath": relative_path}
        return self._make_request("POST", "/getSymbolsOverview", request_data)

    def is_service_available(self) -> bool:
        try:
            response = self.heartbeat()
            return response.get("status") == "OK"
        except (ConnectionError, APIError):
            return False

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        self.close()
