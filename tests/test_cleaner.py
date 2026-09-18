import pandas as pd

from src.cleaner import clean_dataframe


def test_cleaner_classifies_every_input_row(retail_dataframe):
    result = clean_dataframe(retail_dataframe)

    assert len(result.clean_sales) == 3
    assert len(result.cancellations) == 1
    assert len(result.adjustments) == 2
    assert len(result.rejected_rows) == 1
    assert len(result.duplicates) == 1
    assert (
        len(result.clean_sales)
        + len(result.cancellations)
        + len(result.adjustments)
        + len(result.rejected_rows)
        + len(result.duplicates)
        == result.input_row_count
    )


def test_exact_duplicate_is_saved_and_removed(retail_dataframe):
    result = clean_dataframe(retail_dataframe)

    assert result.duplicates.iloc[0]["invoice_no"] == "10001"
    assert result.duplicates.iloc[0]["record_type"] == "duplicate"
    assert len(result.clean_sales.query("invoice_no == '10001'")) == 2


def test_cancellation_is_identified_by_invoice_prefix(retail_dataframe):
    result = clean_dataframe(retail_dataframe)

    cancellation = result.cancellations.iloc[0]
    assert cancellation["invoice_no"] == "C10003"
    assert cancellation["record_type"] == "cancellation"


def test_negative_quantity_and_zero_price_are_adjustments(retail_dataframe):
    result = clean_dataframe(retail_dataframe)
    reasons = set(result.adjustments["adjustment_reason"])

    assert "negative_quantity_adjustment" in reasons
    assert "zero_price_transaction" in reasons


def test_missing_customer_is_retained_as_sale(retail_dataframe):
    result = clean_dataframe(retail_dataframe)
    anonymous_sale = result.clean_sales.query("invoice_no == '10002'").iloc[0]

    assert pd.isna(anonymous_sale["customer_id"])
    assert anonymous_sale["data_quality_status"] == "missing_customer"


def test_missing_invoice_is_rejected(retail_dataframe):
    result = clean_dataframe(retail_dataframe)

    assert len(result.rejected_rows) == 1
    assert "missing_invoice_number" in result.rejected_rows.iloc[0][
        "rejection_reason"
    ]


def test_zero_quantity_is_rejected(retail_dataframe):
    dataframe = retail_dataframe.iloc[:1].copy()
    dataframe.loc[dataframe.index[0], "Quantity"] = 0

    result = clean_dataframe(dataframe)

    assert result.clean_sales.empty
    assert result.rejected_rows.iloc[0]["rejection_reason"] == "zero_quantity"


def test_numeric_identifier_suffixes_do_not_hide_duplicates(retail_dataframe):
    dataframe = retail_dataframe.iloc[[0, -1]].copy()
    dataframe.loc[dataframe.index[0], "InvoiceNo"] = "10001"
    dataframe.loc[dataframe.index[1], "InvoiceNo"] = "10001.0"
    dataframe.loc[dataframe.index[0], "StockCode"] = "12345"
    dataframe.loc[dataframe.index[1], "StockCode"] = "12345.0"

    result = clean_dataframe(dataframe)

    assert len(result.clean_sales) == 1
    assert len(result.duplicates) == 1
    assert result.clean_sales.iloc[0]["invoice_no"] == "10001"
    assert result.clean_sales.iloc[0]["stock_code"] == "12345"
