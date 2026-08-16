"""Fuseki server management for SPARQL operations."""

from pathlib import Path
import subprocess
import time
import platform
import socket
import requests
from typing import Optional


class FusekiManager:
    """Manages Fuseki server lifecycle."""

    def __init__(self, fuseki_home: Path, db_path: Path, port: int = 3030):
        """
        Initialize FusekiManager.

        Args:
            fuseki_home: Path to Fuseki installation directory
            db_path: Path to TDB2 database directory
        """
        self.fuseki_home = fuseki_home
        self.db_path = db_path
        self.port = int(port)
        self.endpoint_url = f"http://localhost:{self.port}/eventkg"
        self._process: Optional[subprocess.Popen] = None
        self._stdout_handle = None
        self._stderr_handle = None

    def is_running(self) -> bool:
        """
        Check if Fuseki is already running on the port.

        Returns:
            True if Fuseki is running on port 3030, False otherwise
        """
        # Try to connect to the port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('localhost', self.port))
            sock.close()
            return result == 0
        except socket.error:
            return False

    def start_server(self) -> subprocess.Popen:
        """
        Start Fuseki server as subprocess.

        Returns:
            subprocess.Popen object for the running server

        Raises:
            FileNotFoundError: If fuseki-server executable not found
            RuntimeError: If server fails to start or port is in use
        """
        # Check if port is already in use
        if self.is_running():
            raise RuntimeError(
                f"Port {self.port} is already in use.\n"
                f"Either a Fuseki server is already running, or another process is using the port.\n"
                f"Please stop the existing process or use a different port."
            )

        # Determine the correct fuseki-server command based on OS
        if platform.system() == "Windows":
            fuseki_cmd = self.fuseki_home / "fuseki-server.bat"
        else:
            fuseki_cmd = self.fuseki_home / "fuseki-server"

        # Check if fuseki-server exists
        if not fuseki_cmd.exists():
            raise FileNotFoundError(
                f"fuseki-server not found at {fuseki_cmd}.\n"
                f"Please ensure Fuseki is properly installed at {self.fuseki_home}."
            )

        # Check if fuseki-server is executable (Unix-like systems)
        if platform.system() != "Windows" and not fuseki_cmd.stat().st_mode & 0o111:
            raise RuntimeError(
                f"fuseki-server is not executable: {fuseki_cmd}.\n"
                f"Try running: chmod +x {fuseki_cmd}"
            )

        # Build command: fuseki-server --loc <db_path> /eventkg
        # This creates a dataset named "eventkg" backed by the TDB2 database
        cmd = [
            str(fuseki_cmd),
            "--port", str(self.port),
            "--loc", str(self.db_path),
            "/eventkg"
        ]

        try:
            log_dir = self.db_path.parent / "fuseki_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            self._stdout_handle = open(log_dir / "fuseki_stdout.log", "a", encoding="utf-8")
            self._stderr_handle = open(log_dir / "fuseki_stderr.log", "a", encoding="utf-8")

            # Start Fuseki as a subprocess
            # We don't use check=True because we want the process to run in background
            process = subprocess.Popen(
                cmd,
                stdout=self._stdout_handle,
                stderr=self._stderr_handle,
                text=True,
                cwd=str(self.fuseki_home)
            )

            # Store the process reference
            self._process = process

            # Give it a moment to start
            time.sleep(1)

            # Check if process is still running (didn't crash immediately)
            if process.poll() is not None:
                # Process has terminated
                raise RuntimeError(
                    f"Fuseki server failed to start.\n"
                    f"Command: {' '.join(cmd)}\n"
                    f"Exit code: {process.returncode}\n"
                    f"See logs under: {log_dir}"
                )

            return process

        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Failed to execute fuseki-server command.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Error: {str(e)}"
            ) from e
        except Exception as e:
            error_msg = (
                f"Failed to start Fuseki server.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Error: {str(e)}"
            )
            raise RuntimeError(error_msg) from e

    def wait_for_ready(self, timeout: int = 30) -> bool:
        """
        Wait for Fuseki to be ready to accept queries.

        Args:
            timeout: Maximum time to wait in seconds (default: 30)

        Returns:
            True if Fuseki becomes ready within timeout, False otherwise
        """
        start_time = time.time()
        ping_url = f"http://localhost:{self.port}/$/ping"

        while time.time() - start_time < timeout:
            try:
                # Try to ping the Fuseki server
                response = requests.get(ping_url, timeout=2)
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                # Server not ready yet, continue waiting
                pass

            # Wait a bit before trying again
            time.sleep(1)

        # Timeout reached
        return False

    def stop_server(self, process: subprocess.Popen) -> None:
        """
        Gracefully stop Fuseki server.

        Args:
            process: The subprocess.Popen object for the running server
        """
        if process is None:
            return

        try:
            # Try graceful termination first
            if platform.system() == "Windows":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                process.terminate()

            # Wait up to 5 seconds for graceful shutdown
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # If graceful shutdown fails, force kill
                process.kill()
                process.wait()

        except Exception:
            # If anything goes wrong, try to kill the process
            try:
                process.kill()
            except Exception:
                # Process might already be dead
                pass

        for handle in (self._stdout_handle, self._stderr_handle):
            try:
                if handle is not None:
                    handle.close()
            except Exception:
                pass
        self._stdout_handle = None
        self._stderr_handle = None
