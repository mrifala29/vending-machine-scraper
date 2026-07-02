"""
Pydantic data models for Sales Statistic data.
Define data schemas for validation and serialization.
"""
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SalesRecord(BaseModel):
    """
    Individual sales record with all columns from the scraped table.
    data: dict maps column_name -> cell_value for every column in the row.
    """

    scrape_date: date = Field(
        ..., description="Date of the scraped data (from the date range being scraped, not current time)"
    )
    scrape_timestamp: datetime = Field(
        default_factory=_utcnow, description="When this record was scraped"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="All column values keyed by column header"
    )


class SalesStatisticData(BaseModel):
    """
    Complete Sales Statistic data model (per scrape).
    """

    scrape_date: date = Field(
        ..., description="Date of the scraped data (from the date range being scraped)"
    )
    scrape_timestamp: datetime = Field(
        default_factory=_utcnow, description="When data was scraped"
    )
    submenu: str = Field(..., description="Which submenu this data is from")
    records: List[SalesRecord] = Field(
        default_factory=list, description="List of sales records"
    )
    record_count: int = Field(default=0, description="Total number of records")
    errors: List[str] = Field(default_factory=list, description="Any parsing errors")

    @model_validator(mode="after")
    def set_record_count(self) -> "SalesStatisticData":
        self.record_count = len(self.records)
        return self

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "scrape_timestamp": "2026-05-04T08:30:00",
                "submenu": "Sales Overview",
                "records": [],
                "record_count": 0,
                "errors": [],
            }
        }


class ScrapingReport(BaseModel):
    """
    Complete scraping report for a full run.
    """

    run_timestamp: datetime = Field(
        default_factory=_utcnow, description="When scraping run started"
    )
    status: str = Field(..., description="Status: success, partial, failed")
    total_records_scraped: int = Field(0, description="Total records from all menus")
    data_by_submenu: dict = Field(
        default_factory=dict, description="Scraped data grouped by submenu"
    )
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    execution_time_seconds: float = Field(0.0, description="Total execution time")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "run_timestamp": "2026-05-04T08:30:00",
                "status": "success",
                "total_records_scraped": 100,
                "data_by_submenu": {},
                "errors": [],
                "execution_time_seconds": 45.5,
            }
        }
