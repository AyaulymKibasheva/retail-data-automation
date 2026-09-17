from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FILE_PATH = PROJECT_ROOT / "data" / "raw" / "online_retail.xlsx"


def inspect_dataset(file_path: Path) -> None:
    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset was not found: {file_path}"
        )

    print(f"File: {file_path.name}")
    print(f"File size: {file_path.stat().st_size / 1024 / 1024:.2f} MB")

    excel_file = pd.ExcelFile(file_path, engine="openpyxl")

    print(f"Sheets: {excel_file.sheet_names}")
    print("\nLoading dataset...")

    dataframe = pd.read_excel(
        excel_file,
        sheet_name=excel_file.sheet_names[0],
    )

    print("\nDATASET SHAPE")
    print(f"Rows: {dataframe.shape[0]:,}")
    print(f"Columns: {dataframe.shape[1]}")

    print("\nCOLUMN NAMES")
    for column in dataframe.columns:
        print(f"- {column}")

    print("\nDATA TYPES")
    print(dataframe.dtypes)

    print("\nFIRST 5 ROWS")
    print(dataframe.head().to_string())

    print("\nMISSING VALUES")
    missing_values = dataframe.isna().sum()
    missing_percent = (
        missing_values / len(dataframe) * 100
    ).round(2)

    missing_report = pd.DataFrame(
        {
            "missing_count": missing_values,
            "missing_percent": missing_percent,
        }
    )

    print(missing_report.to_string())

    print("\nDUPLICATES")
    duplicate_count = dataframe.duplicated().sum()
    duplicate_percent = duplicate_count / len(dataframe) * 100

    print(f"Duplicate rows: {duplicate_count:,}")
    print(f"Duplicate percentage: {duplicate_percent:.2f}%")

    print("\nNUMERIC SUMMARY")
    print(dataframe[["Quantity", "UnitPrice"]].describe().to_string())

    print("\nCANCELLATIONS")
    invoice_numbers = dataframe["InvoiceNo"].astype("string")
    cancellation_count = invoice_numbers.str.startswith(
        "C", na=False
    ).sum()

    print(f"Cancellation rows: {cancellation_count:,}")

    print("\nCOUNTRIES")
    print(f"Unique countries: {dataframe['Country'].nunique()}")
    print(dataframe["Country"].value_counts().head(10).to_string())

    print("\nMEMORY USAGE")
    memory_mb = dataframe.memory_usage(deep=True).sum() / 1024 / 1024
    print(f"DataFrame memory usage: {memory_mb:.2f} MB")

    print("\nInspection completed successfully.")


if __name__ == "__main__":
    inspect_dataset(FILE_PATH)