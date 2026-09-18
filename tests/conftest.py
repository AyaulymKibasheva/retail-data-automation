import pandas as pd
import pytest


@pytest.fixture
def retail_dataframe() -> pd.DataFrame:
    columns = [
        "InvoiceNo",
        "StockCode",
        "Description",
        "Quantity",
        "InvoiceDate",
        "UnitPrice",
        "CustomerID",
        "Country",
    ]

    rows = [
        ["10001", "A", "Product A", 2, "2011-01-03 09:00", 10.0, 111.0, "United Kingdom"],
        ["10001", "B", "Product B", 1, "2011-01-03 09:00", 5.0, 111.0, "United Kingdom"],
        ["10002", "C", "Product C", 3, "2011-02-04 10:00", 5.0, pd.NA, "France"],
        ["C10003", "D", "Product D", -1, "2011-02-05 11:00", 7.0, 222.0, "United Kingdom"],
        ["10004", "E", "Product E", -2, "2011-02-06 12:00", 4.0, 333.0, "United Kingdom"],
        ["10005", "F", "Product F", 1, "2011-02-07 13:00", 0.0, 444.0, "United Kingdom"],
        [pd.NA, "G", "Product G", 1, "2011-02-08 14:00", 1.0, 555.0, "United Kingdom"],
        ["10001", "A", "Product A", 2, "2011-01-03 09:00", 10.0, 111.0, "United Kingdom"],
    ]

    dataframe = pd.DataFrame(rows, columns=columns)
    dataframe["InvoiceDate"] = pd.to_datetime(dataframe["InvoiceDate"])
    dataframe["_source_file"] = "fixture.xlsx"
    dataframe["_source_sheet"] = "Transactions"
    return dataframe


@pytest.fixture
def simple_source_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "InvoiceNo": ["20001", "20002"],
            "StockCode": ["X", "Y"],
            "Description": ["Item X", "Item Y"],
            "Quantity": [1, 2],
            "InvoiceDate": pd.to_datetime(
                ["2011-03-01 09:00", "2011-03-02 10:00"]
            ),
            "UnitPrice": [2.5, 3.0],
            "CustomerID": [100.0, 200.0],
            "Country": ["United Kingdom", "France"],
        }
    )
