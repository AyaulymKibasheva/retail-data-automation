from src.cleaner import clean_dataframe
from src.transformer import transform_cleaning_result


def test_transformer_calculates_revenue_and_business_features(retail_dataframe):
    cleaning = clean_dataframe(retail_dataframe)
    result = transform_cleaning_result(cleaning)

    assert result.sales["revenue"].sum() == 40.0
    assert set(result.sales["year_month"]) == {"2011-01", "2011-02"}
    assert set(result.sales["market_type"]) == {"domestic", "international"}
    assert set(result.sales["customer_type"]) == {"registered", "anonymous"}


def test_transformer_makes_cancellation_value_positive(retail_dataframe):
    cleaning = clean_dataframe(retail_dataframe)
    result = transform_cleaning_result(cleaning)

    assert result.cancellations.iloc[0]["line_value"] == -7.0
    assert result.cancellations.iloc[0]["cancellation_value"] == 7.0


def test_transformer_preserves_rejected_rows_and_duplicates(retail_dataframe):
    cleaning = clean_dataframe(retail_dataframe)
    result = transform_cleaning_result(cleaning)

    assert len(result.rejected_rows) == 1
    assert len(result.duplicates) == 1
