"""Path resolution for Jena and Fuseki installations."""

from pathlib import Path
from typing import Optional
import glob


class PathResolver:
    """Locates Jena and Fuseki installations."""

    def find_jena(self, custom_path: Optional[str] = None) -> Path:
        """
        Find Jena installation.
        Priority: custom_path > current_dir/apache-jena-* > error

        Args:
            custom_path: Optional custom path to Jena installation

        Returns:
            Path object pointing to Jena installation

        Raises:
            FileNotFoundError: If Jena installation cannot be found
        """
        # If custom path provided, validate and return it
        if custom_path:
            jena_path = Path(custom_path)
            if not jena_path.exists():
                raise FileNotFoundError(
                    f"Custom Jena path does not exist: {custom_path}"
                )
            if not jena_path.is_dir():
                raise FileNotFoundError(
                    f"Custom Jena path is not a directory: {custom_path}"
                )
            return jena_path

        # Search current directory for apache-jena-* folders
        current_dir = Path.cwd()
        jena_pattern = "apache-jena-*"
        jena_matches = list(current_dir.glob(jena_pattern))

        # Filter to only directories (exclude .tar.gz files and fuseki directories)
        jena_dirs = [
            p for p in jena_matches 
            if p.is_dir() and 'fuseki' not in p.name.lower()
        ]

        if jena_dirs:
            # Return the first match (or could sort by version)
            return jena_dirs[0]

        # If not found, raise error with helpful message
        raise FileNotFoundError(
            f"Jena installation not found. Please ensure an 'apache-jena-*' "
            f"folder exists in the current directory ({current_dir}), "
            f"or provide a custom path using --jena-home option."
        )

    def find_fuseki(self, custom_path: Optional[str] = None) -> Path:
        """
        Find Fuseki installation.
        Priority: custom_path > current_dir/apache-jena-fuseki-* > error

        Args:
            custom_path: Optional custom path to Fuseki installation

        Returns:
            Path object pointing to Fuseki installation

        Raises:
            FileNotFoundError: If Fuseki installation cannot be found
        """
        # If custom path provided, validate and return it
        if custom_path:
            fuseki_path = Path(custom_path)
            if not fuseki_path.exists():
                raise FileNotFoundError(
                    f"Custom Fuseki path does not exist: {custom_path}"
                )
            if not fuseki_path.is_dir():
                raise FileNotFoundError(
                    f"Custom Fuseki path is not a directory: {custom_path}"
                )
            return fuseki_path

        # Search current directory for apache-jena-fuseki-* folders
        current_dir = Path.cwd()
        fuseki_pattern = "apache-jena-fuseki-*"
        fuseki_matches = list(current_dir.glob(fuseki_pattern))

        # Filter to only directories (exclude .tar.gz files)
        fuseki_dirs = [p for p in fuseki_matches if p.is_dir()]

        if fuseki_dirs:
            # Return the first match (or could sort by version)
            return fuseki_dirs[0]

        # If not found, raise error with helpful message
        raise FileNotFoundError(
            f"Fuseki installation not found. Please ensure an 'apache-jena-fuseki-*' "
            f"folder exists in the current directory ({current_dir}), "
            f"or provide a custom path using --fuseki-home option."
        )
