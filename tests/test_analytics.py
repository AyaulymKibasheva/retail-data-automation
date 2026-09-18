import pytest

from src.analytics import create_analytics, safe_divide
from src.cleaner import clean_dataframe
from src.transformer import transform_cleaning_result


def kpi_values(analytics):
    return analytics.kpis.set_index("metric")["value"].to_dict()


def test_kpis_are_calculated_from_transformed_data(retail_dataframe):
    transformed = transform_cleaning_result(clean_dataframe(retail_dataframe))
    analytics = create_analytics(transformed)
    values = kpi_values(analytics)

    assert values["Total revenue"] == 40.0
    assert values["Sales orders"] == 2
    assert values["Units sold"] == 6
    assert values["Average order value"] == 20.0
    assert values["Unique registered customers"] == 1
    assert values["Cancellation orders"] == 1
    assert values["Cancellation value"] == 7.0
    assert values["Cancellation rate"] == pytest.approx(1 / 3, abs=0.0001)


def test_summary_revenue_reconciles_with_kpi(retail_dataframe):
    transformed = transform_cleaning_result(clean_dataframe(retail_dataframe))
    analytics = create_analytics(transformed)
    total_revenue = kpi_values(analytics)["Total revenue"]

    assert analytics.monthly_summary["revenue"].sum() == total_revenue
    assert analytics.country_summary["revenue"].sum() == total_revenue
    assert analytics.product_summary["revenue"].sum() == total_revenue


def test_monthly_summary_has_two_months(retail_dataframe):
    transformed = transform_cleaning_result(clean_dataframe(retail_dataframe))
    analytics = create_analytics(transformed)

    assert analytics.monthly_summary["year_month"].tolist() == [
        "2011-01",
        "2011-02",
    ]


def test_safe_divide_returns_zero_for_zero_denominator():
    assert safe_divide(10, 0) == 0.0
