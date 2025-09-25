"""
Provides Clojure specific instantiation of the LanguageServer class. Contains various configurations and settings specific to Clojure.
"""

import logging
import os
import pathlib
import shutil
import subprocess
import threading

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

from .common import RuntimeDependency, RuntimeDependencyCollection


def run_command(cmd: list, capture_output: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, stdout=subprocess.PIPE if capture_output else None, stderr=subprocess.STDOUT if capture_output else None, text=True, check=True
    )


def verify_clojure_cli():
    install_msg = "Please install the official Clojure CLI from:\n  https://clojure.org/guides/getting_started"
    if shutil.which("clojure") is None:
        raise FileNotFoundError("`clojure` not found.\n" + install_msg)

    help_proc = run_command(["clojure", "--help"])
    if "-Aaliases" not in help_proc.stdout:
        raise RuntimeError("Detected a Clojure executable, but it does not support '-Aaliases'.\n" + install_msg)

    spath_proc = run_command(["clojure", "-Spath"], capture_output=False)
    if spath_proc.returncode != 0:
        raise RuntimeError("`clojure -Spath` failed; please upgrade to Clojure CLI ≥ 1.10.")


class ClojureLSP(SolidLanguageServer):
    """
    Provides a clojure-lsp specific instantiation of the LanguageServer class. Contains various configurations and settings specific to clojure.
    """

    clojure_lsp_releases = "https://github.com/clojure-lsp/clojure-lsp/releases/latest/download"
    runtime_dependencies = RuntimeDependencyCollection(
        [
            RuntimeDependency(
                id="clojure-lsp",
                url=f"{clojure_lsp_releases}/clojure-lsp-native-macos-aarch64.zip",
                platform_id="osx-arm64",
                archive_type="zip",
                binary_name="clojure-lsp",
            ),
            RuntimeDependency(
                id="clojure-lsp",
                url=f"{clojure_lsp_releases}/clojure-lsp-native-macos-amd64.zip",
                platform_id="osx-x64",
                archive_type="zip",
                binary_name="clojure-lsp",
            ),
            RuntimeDependency(
                id="clojure-lsp",
                url=f"{clojure_lsp_releases}/clojure-lsp-native-linux-aarch64.zip",
                platform_id="linux-arm64",
                archive_type="zip",
                binary_name="clojure-lsp",
            ),
            RuntimeDependency(
                id="clojure-lsp",
                url=f"{clojure_lsp_releases}/clojure-lsp-native-linux-amd64.zip",
                platform_id="linux-x64",
                archive_type="zip",
                binary_name="clojure-lsp",
            ),
            RuntimeDependency(
                id="clojure-lsp",
                url=f"{clojure_lsp_releases}/clojure-lsp-native-windows-amd64.zip",
                platform_id="win-x64",
                archive_type="zip",
                binary_name="clojure-lsp.exe",
            ),
        ]
    )

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        Creates a ClojureLSP instance. This class is not meant to be instantiated directly. Use LanguageServer.create() instead.
        """
        clojure_lsp_executable_path = self._setup_runtime_dependencies(logger, config, solidlsp_settings)
        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=clojure_lsp_executable_path, cwd=repository_root_path),
            "clojure",
            solidlsp_settings,
        )
        self.server_ready = threading.Event()
        self.initialize_searcher_command_available = threading.Event()
        self.resolve_main_method_available = threading.Event()
        self.service_ready_event = threading.Event()

    @classmethod
    def _setup_runtime_dependencies(
        cls, logger: LanguageServerLogger, config: LanguageServerConfig, solidlsp_settings: SolidLSPSettings
    ) -> str:
        """Setup runtime dependencies for clojure-lsp and return the command to start the server."""
        verify_clojure_cli()
        deps = ClojureLSP.runtime_dependencies
        dependency = deps.single_for_current_platform()

        clojurelsp_ls_dir = cls.ls_resources_dir(solidlsp_settings)
        clojurelsp_executable_path = deps.binary_path(clojurelsp_ls_dir)
        if not os.path.exists(clojurelsp_executable_path):
            logger.log(
                f"Downloading and extracting clojure-lsp from {dependency.url} to {clojurelsp_ls_dir}",
                logging.INFO,
            )
            deps.install(logger, clojurelsp_ls_dir)
        if not os.path.exists(clojurelsp_executable_path):
            raise FileNotFoundError(f"Download failed? Could not find clojure-lsp executable at {clojurelsp_executable_path}")
        os.chmod(clojurelsp_executable_path, 0o755)
        return clojurelsp_executable_path

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """Returns the init params for clojure-lsp."""
        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        return {  # type: ignore
            "processId": os.getpid(),
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
            "capabilities": {
                "workspace": {
                    "applyEdit": True,
                    "workspaceEdit": {"documentChanges": True},
                    "symbol": {"symbolKind": {"valueSet": list(range(1, 27))}},
                    "workspaceFolders": True,
                },
                "textDocument": {
                    "synchronization": {"didSave": True},
                    "publishDiagnostics": {"relatedInformation": True, "tagSupport": {"valueSet": [1, 2]}},
                    "definition": {"linkSupport": True},
                    "references": {},
                    "hover": {"contentFormat": ["markdown", "plaintext"]},
                    "documentSymbol": {
                        "hierarchicalDocumentSymbolSupport": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},  #
                    },
                },
                "general": {"positionEncodings": ["utf-16"]},
            },
            "initializationOptions": {"dependency-scheme": "jar", "text-document-sync-kind": "incremental"},
            "trace": "off",
            "workspaceFolders": [{"uri": root_uri, "name": os.path.basename(repository_absolute_path)}],
        }

    def _start_server(self):
        def register_capability_handler(params):
            assert "registrations" in params
            for registration in params["registrations"]:
                if registration["method"] == "workspace/executeCommand":
                    self.initialize_searcher_command_available.set()
                    self.resolve_main_method_available.set()
            return

        def lang_status_handler(params):
            # TODO: Should we wait for
            # server -> client: {'jsonrpc': '2.0', 'method': 'language/status', 'params': {'type': 'ProjectStatus', 'message': 'OK'}}
            # Before proceeding?
            if params["type"] == "ServiceReady" and params["message"] == "ServiceReady":
                self.service_ready_event.set()

        def execute_client_command_handler(params):
            return []

        def do_nothing(params):
            return

        def check_experimental_status(params):
            if params["quiescent"] == True:
                self.server_ready.set()

        def window_log_message(msg):
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        self.server.on_request("client/registerCapability", register_capability_handler)
        self.server.on_notification("language/status", lang_status_handler)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)
        self.server.on_notification("language/actionableNotification", do_nothing)
        self.server.on_notification("experimental/serverStatus", check_experimental_status)

        self.logger.log("Starting clojure-lsp server process", logging.INFO)
        self.server.start()

        initialize_params = self._get_initialize_params(self.repository_root_path)

        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)
        assert init_response["capabilities"]["textDocumentSync"]["change"] == 2
        assert "completionProvider" in init_response["capabilities"]
        # Clojure-lsp completion provider capabilities are more flexible than other servers'
        completion_provider = init_response["capabilities"]["completionProvider"]
        assert completion_provider["resolveProvider"] == True
        assert "triggerCharacters" in completion_provider
        self.server.notify.initialized({})
        # after initialize, Clojure-lsp is ready to serve
        self.server_ready.set()
        self.completions_available.set()
