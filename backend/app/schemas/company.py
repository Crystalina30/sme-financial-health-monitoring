"""Request and response schemas for companies and reporting periods."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompanyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    registration_number: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=120)
    currency_code: str = Field(default="MYR", min_length=3, max_length=3)


class CompanyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    registration_number: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=120)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    registration_number: str | None
    industry: str | None
    currency_code: str
    created_at: datetime


class ReportingPeriodCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=50, description="For example 'FY2025'.")
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def check_period_order(self) -> "ReportingPeriodCreateRequest":
        if self.period_end <= self.period_start:
            raise ValueError("period_end must fall after period_start.")
        return self


class ReportingPeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    label: str
    period_start: date
    period_end: date
    created_at: datetime
