"""
ClickHouse formatter for converting scraping data to appropriate format.
"""
import json
from datetime import datetime
from typing import List, Dict, Any
from models.sales_data import SalesStatisticData
from utils.logging_setup import logger


class ClickHouseFormatter:
    """Format data for ClickHouse insertion."""

    @staticmethod
    def to_jsonl(data_list: List[SalesStatisticData]) -> str:
        """
        Convert SalesStatisticData list to JSONL format (one JSON per line).
        Suitable for ClickHouse HTTP API or INSERT ... FORMAT JSONEachRow.

        Args:
            data_list: List of SalesStatisticData objects

        Returns:
            JSONL string (newline-separated JSON objects)

        Example:
            jsonl_output = ClickHouseFormatter.to_jsonl(data_list)
            # Output:
            # {"submenu": "paydetail", "record_id": "001", "timestamp": "2026-01-01T00:00:00Z", ...}
            # {"submenu": "paydetail", "record_id": "002", "timestamp": "2026-01-02T00:00:00Z", ...}
        """
        lines = []

        for data in data_list:
            for record in data.records:
                # Flatten the nested structure
                flattened = {
                    "scrape_timestamp": data.scrape_timestamp.isoformat(),
                    "submenu": data.submenu,
                    "record_id": record.id,
                    "record_timestamp": record.timestamp.isoformat(),
                    # Add any other fields from record here
                }
                lines.append(json.dumps(flattened, ensure_ascii=False))

            # Also log errors if any
            if data.errors:
                for error in data.errors:
                    error_record = {
                        "scrape_timestamp": data.scrape_timestamp.isoformat(),
                        "submenu": data.submenu,
                        "error": error,
                        "record_id": None,
                    }
                    lines.append(json.dumps(error_record, ensure_ascii=False))

        return "\n".join(lines)

    @staticmethod
    def to_clickhouse_schema() -> Dict[str, str]:
        """
        Return ClickHouse table schema for storing scraping data.

        Returns:
            Dictionary with column_name: column_type

        Example ClickHouse CREATE TABLE:
            ```sql
            CREATE TABLE scraping_data (
                scrape_timestamp DateTime,
                submenu String,
                record_id String,
                record_timestamp DateTime,
                created_at DateTime DEFAULT now()
            ) ENGINE = MergeTree()
            ORDER BY (submenu, scrape_timestamp)
            ```
        """
        return {
            "scrape_timestamp": "DateTime",
            "submenu": "String",
            "record_id": "String",
            "record_timestamp": "DateTime",
            "created_at": "DateTime DEFAULT now()",
        }

    @staticmethod
    def to_insert_sql(data_list: List[SalesStatisticData], table_name: str = "scraping_data") -> str:
        """
        Generate ClickHouse INSERT SQL statement for data insertion.

        Args:
            data_list: List of SalesStatisticData objects
            table_name: ClickHouse table name

        Returns:
            SQL INSERT statement with FORMAT JSONEachRow

        Example:
            sql = ClickHouseFormatter.to_insert_sql(data_list)
            # Execute: curl -X POST 'http://localhost:8123/' --data-binary "@/dev/stdin" <<< sql
        """
        jsonl_data = ClickHouseFormatter.to_jsonl(data_list)
        
        # ClickHouse HTTP API format
        sql = f"INSERT INTO {table_name} FORMAT JSONEachRow\n{jsonl_data}"
        return sql

    @staticmethod
    def to_csv_lines(data_list: List[SalesStatisticData]) -> List[str]:
        """
        Convert data to CSV format (header + data rows).

        Args:
            data_list: List of SalesStatisticData objects

        Returns:
            List of CSV lines (first line is header)

        Example:
            csv_lines = ClickHouseFormatter.to_csv_lines(data_list)
            csv_content = "\\n".join(csv_lines)
        """
        lines = [
            "scrape_timestamp,submenu,record_id,record_timestamp"
        ]

        for data in data_list:
            for record in data.records:
                csv_line = (
                    f'"{data.scrape_timestamp.isoformat()}",'
                    f'"{data.submenu}",'
                    f'"{record.id}",'
                    f'"{record.timestamp.isoformat()}"'
                )
                lines.append(csv_line)

        return lines
