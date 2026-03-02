"""Database management for TDB2 operations."""

from pathlib import Path
from typing import List
import subprocess
import re
import platform


class DatabaseManager:
    """Manages TDB2 database operations."""

    def __init__(self, jena_home: Path, ekg_folder: Path):
        """
        Initialize DatabaseManager.

        Args:
            jena_home: Path to Jena installation directory
            ekg_folder: Path to EKG folder containing .nt files
        """
        self.jena_home = jena_home
        self.ekg_folder = ekg_folder
        self.db_path = ekg_folder / "databases" / "eventkg-db"

    def database_exists(self) -> bool:
        """
        Check if TDB2 database already exists.

        Returns:
            True if database directory exists and contains database files, False otherwise
        """
        if not self.db_path.exists():
            return False

        # Check if the database directory contains TDB2 files
        # TDB2 databases typically have Data-*.dat files
        db_files = list(self.db_path.glob("Data-*.dat"))
        return len(db_files) > 0

    def load_database(self, nt_files: List[Path]) -> int:
        """
        Load .nt files into TDB2 database using tdb2.tdbloader.

        Args:
            nt_files: List of paths to .nt files to load

        Returns:
            Number of triples loaded

        Raises:
            RuntimeError: If tdb2.tdbloader command fails
            FileNotFoundError: If tdb2.tdbloader executable not found
            OSError: If database directory cannot be created or accessed
        """
        # Create database directory if it doesn't exist
        try:
            self.db_path.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise OSError(
                f"Permission denied: Cannot create database directory at {self.db_path}.\n"
                f"Please check file permissions or choose a different location."
            ) from e
        except OSError as e:
            raise OSError(
                f"Failed to create database directory at {self.db_path}.\n"
                f"Error: {str(e)}"
            ) from e

        # Determine the correct tdbloader command based on OS
        if platform.system() == "Windows":
            tdbloader_cmd = self.jena_home / "bat" / "tdb2.tdbloader.bat"
        else:
            tdbloader_cmd = self.jena_home / "bin" / "tdb2.tdbloader"

        # Check if tdbloader exists
        if not tdbloader_cmd.exists():
            raise FileNotFoundError(
                f"tdb2.tdbloader not found at {tdbloader_cmd}.\n"
                f"Please ensure Jena is properly installed at {self.jena_home}."
            )

        # Check if tdbloader is executable (Unix-like systems)
        if platform.system() != "Windows" and not tdbloader_cmd.stat().st_mode & 0o111:
            raise RuntimeError(
                f"tdb2.tdbloader is not executable: {tdbloader_cmd}.\n"
                f"Try running: chmod +x {tdbloader_cmd}"
            )

        # Build command: tdb2.tdbloader --loc <db_path> <nt_files...>
        cmd = [str(tdbloader_cmd), "--loc", str(self.db_path)]
        cmd.extend([str(f) for f in nt_files])

        try:
            # Run tdb2.tdbloader and capture output
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # Parse output to extract number of triples loaded
            # TDB2 loader typically outputs something like:
            # "-- Finished: 1,234 tuples in 1.23s (Rate: 1,000 per second)"
            triples_loaded = self._parse_triples_count(result.stdout + result.stderr)
            return triples_loaded

        except subprocess.CalledProcessError as e:
            # If the command fails, raise with error details
            error_output = e.stderr if e.stderr else e.stdout
            
            # Check for common error patterns
            if "No space left on device" in error_output or "disk full" in error_output.lower():
                raise OSError(
                    f"Insufficient disk space to load database.\n"
                    f"Database location: {self.db_path}\n"
                    f"Please free up disk space or choose a different location."
                ) from e
            elif "Permission denied" in error_output or "Access is denied" in error_output:
                raise OSError(
                    f"Permission denied while loading database.\n"
                    f"Database location: {self.db_path}\n"
                    f"Please check file permissions."
                ) from e
            else:
                error_msg = (
                    f"tdb2.tdbloader failed with exit code {e.returncode}.\n"
                    f"Command: {' '.join(cmd)}\n"
                    f"Error output:\n{error_output}"
                )
                raise RuntimeError(error_msg) from e
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Failed to execute tdb2.tdbloader command.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Error: {str(e)}"
            ) from e

    def _parse_triples_count(self, output: str) -> int:
        """
        Parse the number of triples from tdb2.tdbloader output.

        Args:
            output: Combined stdout and stderr from tdb2.tdbloader

        Returns:
            Number of triples loaded, or 0 if count cannot be parsed
        """
        # Look for patterns like:
        # "1,234 tuples" or "1234 tuples" or "Finished: 1,234 tuples"
        # TDB2 uses "tuples" to refer to triples
        patterns = [
            r'(\d+(?:,\d+)*)\s+tuples',  # Matches "1,234 tuples"
            r'(\d+)\s+tuples',            # Matches "1234 tuples"
            r'Finished:\s+(\d+(?:,\d+)*)', # Matches "Finished: 1,234"
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                # Remove commas and convert to int
                count_str = match.group(1).replace(',', '')
                return int(count_str)

        # If no pattern matches, return 0
        return 0
