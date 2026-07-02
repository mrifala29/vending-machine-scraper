"""
JSON storage handler for scraped data.
Manages data persistence with timestamps and backup.
"""
import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List
from config.config import Config
from utils.logging_setup import logger
from utils.exceptions import StorageError


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects."""
    
    def default(self, obj):
        """Convert datetime to ISO format string."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):  # ← TAMBAH: handle date type
            return obj.isoformat()
        return super().default(obj)


class JSONStorage:
    """Handle JSON file storage for scraped data."""

    def __init__(self, folder: str = None):
        """
        Initialize JSON storage.

        Args:
            folder: Output folder path (defaults to Config.DATA_FOLDER)
        """
        self.folder = folder or Config.DATA_FOLDER
        self._ensure_folder()

    def _ensure_folder(self) -> None:
        """Create data folder if it doesn't exist."""
        Path(self.folder).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured data folder exists: {self.folder}")

    def save_data(
        self, data: Dict[str, Any], filename: str = None, start_date=None, end_date=None
    ) -> str:
        """
        Save data to JSON file with timestamp or date range.

        Args:
            data: Data dictionary to save
            filename: Custom filename (optional)
            start_date: Optional start date (datetime) for date range in filename
            end_date: Optional end date (datetime) for date range in filename

        Returns:
            Path to saved file

        Raises:
            StorageError: If save operation fails
        """
        try:
            if filename is None:
                if start_date and end_date:
                    start_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, 'strftime') else str(start_date)[:10]
                    end_str = end_date.strftime("%Y-%m-%d") if hasattr(end_date, 'strftime') else str(end_date)[:10]
                    filename = f"scraping_report_{start_str}_to_{end_str}.json"
                else:
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    filename = f"scraping_report_{timestamp}.json"

            filepath = os.path.join(self.folder, filename)

            # Add metadata
            output_data = {
                "metadata": {
                    "saved_at": datetime.now().isoformat(),
                    "filename": filename,
                },
                "data": data,
            }

            # Write JSON
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False, cls=DateTimeEncoder)

            logger.info(f"Data saved successfully: {filepath}")
            return filepath

        except Exception as e:
            error_msg = f"Failed to save JSON data: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)

    def load_data(self, filename: str) -> Dict[str, Any]:
        """
        Load data from JSON file.

        Args:
            filename: Filename to load

        Returns:
            Data dictionary

        Raises:
            StorageError: If load operation fails
        """
        try:
            filepath = os.path.join(self.folder, filename)

            if not os.path.exists(filepath):
                raise FileNotFoundError(f"File not found: {filepath}")

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            logger.info(f"Data loaded successfully: {filepath}")
            return data

        except Exception as e:
            error_msg = f"Failed to load JSON data: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)

    def list_files(self, pattern: str = "*.json") -> list:
        """
        List all JSON files in data folder.

        Args:
            pattern: File pattern to match

        Returns:
            List of filenames
        """
        try:
            files = sorted(Path(self.folder).glob(pattern))
            filenames = [f.name for f in files]
            logger.debug(f"Found {len(filenames)} JSON files")
            return filenames
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            return []

    def save_per_target(
        self,
        all_data: List[Any],
        start_date=None,
        end_date=None,
    ) -> List[str]:
        """
        Save each SalesStatisticData item as its own JSON file.
        Filename format: {submenu}_{start_date}_to_{end_date}.json

        Args:
            all_data: List of SalesStatisticData objects
            start_date: datetime for date range label
            end_date: datetime for date range label

        Returns:
            List of saved file paths
        """
        saved_paths: List[str] = []

        start_str = start_date.strftime("%Y-%m-%d") if start_date and hasattr(start_date, "strftime") else "unknown"
        end_str = end_date.strftime("%Y-%m-%d") if end_date and hasattr(end_date, "strftime") else "unknown"

        for page_data in all_data:
            try:
                submenu = getattr(page_data, "submenu", "unknown")
                filename = f"{submenu}_{start_str}_to_{end_str}.json"
                filepath = os.path.join(self.folder, filename)

                output = {
                    "metadata": {
                        "submenu": submenu,
                        "start_date": start_str,
                        "end_date": end_str,
                        "saved_at": datetime.now().isoformat(),
                        "record_count": getattr(page_data, "record_count", 0),
                    },
                    "records": [
                        {
                            "scrape_timestamp": r.scrape_timestamp.isoformat(),
                            **r.data,
                        }
                        for r in getattr(page_data, "records", [])
                    ],
                    "errors": getattr(page_data, "errors", []),
                }

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(output, f, indent=2, ensure_ascii=False, cls=DateTimeEncoder)

                logger.info(f"Saved {len(output['records'])} records → {filename}")
                saved_paths.append(filepath)

            except Exception as e:
                logger.error(f"Failed to save {getattr(page_data, 'submenu', '?')}: {e}")

        return saved_paths

    def cleanup_old_files(self, keep_count: int = None) -> None:
        """
        Delete old files, keeping only recent ones.

        Args:
            keep_count: Number of recent files to keep (defaults to Config.KEEP_BACKUPS)
        """
        try:
            if keep_count is None:
                keep_count = Config.KEEP_BACKUPS

            files = sorted(Path(self.folder).glob("sales_data_*.json"))

            if len(files) > keep_count:
                files_to_delete = files[:-keep_count]
                for file in files_to_delete:
                    file.unlink()
                    logger.info(f"Deleted old file: {file.name}")

        except Exception as e:
            logger.error(f"Error cleaning up old files: {str(e)}")
