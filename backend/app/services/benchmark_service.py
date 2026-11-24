"""Altman Z'' financial distress benchmark.

An established, published distress model shown *beside* the health score as
an independent point of comparison. It is never combined with the score: the
two answer different questions. The health score describes current condition
across four dimensions; Z'' is a discriminant score estimated to separate
firms that later became distressed from those that did not.

Model (Altman, 2002, pp. 17-18; the version for non-manufacturers and emerging
markets, using the book value of equity):

    Z'' = 6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 X4

    X1 = working capital / total assets
    X2 = retained earnings / total assets
    X3 = EBIT / total assets
    X4 = book value of equity / total liabilities

Altman states that "Z-Scores below 1.10 indicate a distressed condition". That
is the only cut-off used here. The commonly quoted upper ("safe zone") cut-off
could not be verified in the original text, so scores at or above 1.10 are
described only as "not below the distress cut-off".

Z'' was estimated on US firms. Its accuracy for Malaysian SMEs has not been
established, and Altman et al. (2017) found that re-estimating it for a
specific country improves accuracy.
"""

from dataclasses import dataclass, field

from app.schemas.financial_inputs import FinancialInputs

MODEL_NAME = "Altman Z''"
SOURCE = (
    "Altman, E. I. (2002). Corporate distress prediction models in a turbulent "
    "economic and Basel II environment. NYU Stern working paper, pp. 17-18."
)

COEFFICIENTS = {"x1": 6.56, "x2": 3.26, "x3": 6.72, "x4": 1.05}
DISTRESS_CUTOFF = 1.10

ZERO_TOLERANCE = 1e-9


@dataclass(frozen=True)
class BenchmarkResult:
    """The Z'' value, or the reason it could not be calculated."""

    available: bool
    value: float | None = None
    components: dict[str, float] = field(default_factory=dict)
    below_distress_cutoff: bool | None = None
    missing_inputs: list[str] = field(default_factory=list)
    reason: str | None = None


def calculate_altman_z_double_prime(data: FinancialInputs) -> BenchmarkResult:
    """Calculate Altman's Z'' from one set of financial inputs.

    Returns an unavailable result, with the reason, rather than a misleading
    number when an input is missing or a ratio is undefined. Retained earnings
    are never assumed to be zero.

    EBIT is taken as the recorded operating profit (revenue less cost of goods
    sold less operating expenses), since the simplified statement has no line
    for other operating or non-operating income.
    """
    missing = []
    if data.retained_earnings is None:
        missing.append("retained_earnings")
    if missing:
        return BenchmarkResult(
            available=False,
            missing_inputs=missing,
            reason="Retained earnings have not been entered for this period. Enter them "
            "on the financial data form to calculate the benchmark.",
        )

    if data.total_assets <= ZERO_TOLERANCE:
        return BenchmarkResult(
            available=False,
            reason="Total assets are zero, so X1, X2 and X3 are undefined.",
        )
    if data.total_liabilities <= ZERO_TOLERANCE:
        return BenchmarkResult(
            available=False,
            reason="Total liabilities are zero, so X4 (equity / liabilities) is undefined.",
        )

    components = {
        "x1": (data.current_assets - data.current_liabilities) / data.total_assets,
        "x2": data.retained_earnings / data.total_assets,
        "x3": data.operating_profit / data.total_assets,
        "x4": data.total_equity / data.total_liabilities,
    }
    # Compared after rounding, so the interpretation always matches the value
    # shown to the user.
    value = round(sum(COEFFICIENTS[name] * x for name, x in components.items()), 2)
    return BenchmarkResult(
        available=True,
        value=value,
        components={name: round(x, 4) for name, x in components.items()},
        below_distress_cutoff=value < DISTRESS_CUTOFF,
    )
