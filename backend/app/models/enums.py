"""Enumerations shared by the models, schemas and services."""

from enum import Enum


class IndicatorCategory(str, Enum):
    """The four fixed indicator categories."""

    LIQUIDITY = "liquidity"
    PROFITABILITY = "profitability"
    SOLVENCY = "solvency"
    EFFICIENCY = "efficiency"


class IndicatorCode(str, Enum):
    """The ten fixed indicators. This set does not change at runtime."""

    CURRENT_RATIO = "current_ratio"
    QUICK_RATIO = "quick_ratio"
    GROSS_PROFIT_MARGIN = "gross_profit_margin"
    NET_PROFIT_MARGIN = "net_profit_margin"
    RETURN_ON_ASSETS = "return_on_assets"
    DEBT_TO_EQUITY = "debt_to_equity"
    DEBT_RATIO = "debt_ratio"
    INTEREST_COVERAGE = "interest_coverage"
    ASSET_TURNOVER = "asset_turnover"
    DAYS_SALES_OUTSTANDING = "days_sales_outstanding"


class ThresholdDirection(str, Enum):
    """Whether a higher or a lower value is the healthier direction."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class IndicatorStatus(str, Enum):
    """Status of an indicator relative to its configured thresholds."""

    SOUND = "sound"
    CONCERN = "concern"
    DISTRESS = "distress"
    NOT_APPLICABLE = "not_applicable"


class HealthClassification(str, Enum):
    """Overall financial health classification band."""

    SOUND = "sound"
    VULNERABLE = "vulnerable"
    DISTRESSED = "distressed"


class AttentionReason(str, Enum):
    """Why an indicator has been flagged as requiring attention."""

    DISTRESS_BREACH = "distress_breach"
    CONCERN_BREACH = "concern_breach"
    UNFAVOURABLE_MOVEMENT = "unfavourable_movement"


# Which category each indicator belongs to. Fixed framework.
INDICATOR_CATEGORIES: dict[IndicatorCode, IndicatorCategory] = {
    IndicatorCode.CURRENT_RATIO: IndicatorCategory.LIQUIDITY,
    IndicatorCode.QUICK_RATIO: IndicatorCategory.LIQUIDITY,
    IndicatorCode.GROSS_PROFIT_MARGIN: IndicatorCategory.PROFITABILITY,
    IndicatorCode.NET_PROFIT_MARGIN: IndicatorCategory.PROFITABILITY,
    IndicatorCode.RETURN_ON_ASSETS: IndicatorCategory.PROFITABILITY,
    IndicatorCode.DEBT_TO_EQUITY: IndicatorCategory.SOLVENCY,
    IndicatorCode.DEBT_RATIO: IndicatorCategory.SOLVENCY,
    IndicatorCode.INTEREST_COVERAGE: IndicatorCategory.SOLVENCY,
    IndicatorCode.ASSET_TURNOVER: IndicatorCategory.EFFICIENCY,
    IndicatorCode.DAYS_SALES_OUTSTANDING: IndicatorCategory.EFFICIENCY,
}

# Human-readable names, used by the API and the dashboard.
INDICATOR_DISPLAY_NAMES: dict[IndicatorCode, str] = {
    IndicatorCode.CURRENT_RATIO: "Current Ratio",
    IndicatorCode.QUICK_RATIO: "Quick Ratio",
    IndicatorCode.GROSS_PROFIT_MARGIN: "Gross Profit Margin",
    IndicatorCode.NET_PROFIT_MARGIN: "Net Profit Margin",
    IndicatorCode.RETURN_ON_ASSETS: "Return on Assets",
    IndicatorCode.DEBT_TO_EQUITY: "Debt-to-Equity Ratio",
    IndicatorCode.DEBT_RATIO: "Debt Ratio",
    IndicatorCode.INTEREST_COVERAGE: "Interest Coverage Ratio",
    IndicatorCode.ASSET_TURNOVER: "Asset Turnover",
    IndicatorCode.DAYS_SALES_OUTSTANDING: "Days Sales Outstanding",
}

# Unit of each indicator, so the frontend formats values correctly.
INDICATOR_UNITS: dict[IndicatorCode, str] = {
    IndicatorCode.CURRENT_RATIO: "ratio",
    IndicatorCode.QUICK_RATIO: "ratio",
    IndicatorCode.GROSS_PROFIT_MARGIN: "percent",
    IndicatorCode.NET_PROFIT_MARGIN: "percent",
    IndicatorCode.RETURN_ON_ASSETS: "percent",
    IndicatorCode.DEBT_TO_EQUITY: "ratio",
    IndicatorCode.DEBT_RATIO: "ratio",
    IndicatorCode.INTEREST_COVERAGE: "times",
    IndicatorCode.ASSET_TURNOVER: "times",
    IndicatorCode.DAYS_SALES_OUTSTANDING: "days",
}
