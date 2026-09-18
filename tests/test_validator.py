import pandas as pd
import pytest

from src.validator import validate_dataframe


def issue_codes(report):
    return {issue.code for issue in report.issues}


def test_valid_schema_passes_validation(retail_dataframe):
    report = validate_dataframe(retail_dataframe)

    assert report.is_valid
    assert "cancellation_count" in issue_codes(report)


def test_missing_required_column_is_error(retail_dataframe):
    report = validate_dataframe(retail_dataframe.drop(columns=["UnitPrice"]))

    assert not report.is_valid
    assert "missing_columns" in issue_codes(report)


def test_invalid_numeric_value_is_error(retail_dataframe):
    dataframe = retail_dataframe.copy()
    dataframe["Quantity"] = dataframe["Quantity"].astype("object")
    dataframe.loc[0, "Quantity"] = "invalid"

    report = validate_dataframe(dataframe)

    assert not report.is_valid
    assert "invalid_quantity" in issue_codes(report)


def test_empty_dataframe_is_error():
    report = validate_dataframe(pd.DataFrame())

    assert not report.is_valid
    assert "empty_dataframe" in issue_codes(report)


def test_non_dataframe_is_rejected():
    with pytest.raises(TypeError, match="Expected a pandas DataFrame"):
        validate_dataframe([])
