from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .loader import load_file
from .validator import validate_dataframe


COLUMN_MAPPING = {
    "InvoiceNo": "invoice_no",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "UnitPrice": "unit_price",
    "CustomerID": "customer_id",
    "Country": "country",
}

BUSINESS_COLUMNS = tuple(COLUMN_MAPPING.values())


class DataCleaningError(Exception):
    """Raised when a dataset cannot be cleaned safely."""


@dataclass
class CleaningResult:
    clean_sales: pd.DataFrame
    cancellations: pd.DataFrame
    adjustments: pd.DataFrame
    rejected_rows: pd.DataFrame
    duplicates: pd.DataFrame
    input_row_count: int

    def summary(self) -> pd.DataFrame:
        records = [
            {
                "category": "Input rows",
                "row_count": self.input_row_count,
            },
            {
                "category": "Clean sales",
                "row_count": len(self.clean_sales),
            },
            {
                "category": "Cancellations",
                "row_count": len(self.cancellations),
            },
            {
                "category": "Adjustments",
                "row_count": len(self.adjustments),
            },
            {
                "category": "Rejected rows",
                "row_count": len(self.rejected_rows),
            },
            {
                "category": "Removed duplicates",
                "row_count": len(self.duplicates),
            },
        ]

        return pd.DataFrame(records)


def normalize_text(
    series: pd.Series,
    uppercase: bool = False,
) -> pd.Series:
    result = (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .replace("", pd.NA)
    )

    if uppercase:
        result = result.str.upper()

    return result


def add_reason(
    reasons: pd.Series,
    mask: pd.Series,
    reason: str,
) -> None:
    existing = reasons.loc[mask]

    reasons.loc[mask] = np.where(
        existing.eq(""),
        reason,
        existing + "; " + reason,
    )


def add_source_row_number(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    result = dataframe.copy()

    source_columns = [
        column
        for column in ("_source_file", "_source_sheet")
        if column in result.columns
    ]

    if source_columns:
        result["_source_row"] = (
            result.groupby(
                source_columns,
                dropna=False,
            ).cumcount()
            + 2
        )
    else:
        result["_source_row"] = pd.RangeIndex(
            start=2,
            stop=len(result) + 2,
        )

    return result


def standardize_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    result = dataframe.copy()
    result = add_source_row_number(result)
    result = result.rename(columns=COLUMN_MAPPING)

    result["invoice_no"] = normalize_text(
        result["invoice_no"],
        uppercase=True,
    )

    result["stock_code"] = normalize_text(
        result["stock_code"],
        uppercase=True,
    )

    result["description"] = normalize_text(
        result["description"]
    )

    result["country"] = normalize_text(
        result["country"]
    )

    result["customer_id"] = (
        normalize_text(result["customer_id"])
        .str.replace(r"\.0$", "", regex=True)
    )

    result["quantity"] = pd.to_numeric(
        result["quantity"],
        errors="coerce",
    )

    result["unit_price"] = pd.to_numeric(
        result["unit_price"],
        errors="coerce",
    )

    result["invoice_date"] = pd.to_datetime(
        result["invoice_date"],
        errors="coerce",
    )

    missing_description = result[
        "description"
    ].isna()

    missing_customer = result[
        "customer_id"
    ].isna()

    result["data_quality_status"] = np.select(
        [
            missing_description & missing_customer,
            missing_description,
            missing_customer,
        ],
        [
            "missing_description_and_customer",
            "missing_description",
            "missing_customer",
        ],
        default="complete",
    )

    return result


def create_rejection_reasons(
    dataframe: pd.DataFrame,
) -> pd.Series:
    reasons = pd.Series(
        "",
        index=dataframe.index,
        dtype="string",
    )

    critical_columns = {
        "invoice_no": "missing_invoice_number",
        "stock_code": "missing_stock_code",
        "invoice_date": "missing_or_invalid_invoice_date",
        "quantity": "missing_or_invalid_quantity",
        "unit_price": "missing_or_invalid_unit_price",
        "country": "missing_country",
    }

    for column, reason in critical_columns.items():
        add_reason(
            reasons,
            dataframe[column].isna(),
            reason,
        )

    add_reason(
        reasons,
        dataframe["quantity"].eq(0),
        "zero_quantity",
    )

    return reasons


def create_adjustment_reasons(
    dataframe: pd.DataFrame,
) -> pd.Series:
    reasons = pd.Series(
        "",
        index=dataframe.index,
        dtype="string",
    )

    invoice_numbers = dataframe[
        "invoice_no"
    ].astype("string")

    add_reason(
        reasons,
        invoice_numbers.str.startswith(
            "A",
            na=False,
        ),
        "accounting_adjustment",
    )

    add_reason(
        reasons,
        dataframe["quantity"].lt(0),
        "negative_quantity_adjustment",
    )

    add_reason(
        reasons,
        dataframe["unit_price"].lt(0),
        "negative_price_adjustment",
    )

    add_reason(
        reasons,
        dataframe["unit_price"].eq(0),
        "zero_price_transaction",
    )

    return reasons


def clean_dataframe(
    dataframe: pd.DataFrame,
) -> CleaningResult:
    validation_report = validate_dataframe(
        dataframe
    )

    if not validation_report.is_valid:
        error_messages = [
            issue.message
            for issue in validation_report.errors
        ]

        raise DataCleaningError(
            "Dataset validation failed: "
            + " | ".join(error_messages)
        )

    input_row_count = len(dataframe)

    standardized = standardize_dataframe(
        dataframe
    )

    duplicate_mask = standardized.duplicated(
        subset=list(BUSINESS_COLUMNS),
        keep="first",
    )

    duplicates = standardized.loc[
        duplicate_mask
    ].copy()

    duplicates["record_type"] = "duplicate"

    working = standardized.loc[
        ~duplicate_mask
    ].copy()

    rejection_reasons = create_rejection_reasons(
        working
    )

    rejected_mask = rejection_reasons.ne("")

    working["rejection_reason"] = (
        rejection_reasons.replace("", pd.NA)
    )

    rejected_rows = working.loc[
        rejected_mask
    ].copy()

    rejected_rows["record_type"] = "rejected"

    candidates = working.loc[
        ~rejected_mask
    ].copy()

    invoice_numbers = candidates[
        "invoice_no"
    ].astype("string")

    cancellation_mask = (
        invoice_numbers
        .str.startswith("C", na=False)
    )

    adjustment_mask = (
        ~cancellation_mask
        & (
            candidates["quantity"].lt(0)
            | candidates["unit_price"].le(0)
            | invoice_numbers.str.startswith(
                "A",
                na=False,
            )
        )
    )

    sale_mask = (
        ~cancellation_mask
        & ~adjustment_mask
    )

    cancellations = candidates.loc[
        cancellation_mask
    ].copy()

    cancellations["record_type"] = "cancellation"

    adjustments = candidates.loc[
        adjustment_mask
    ].copy()

    adjustments["adjustment_reason"] = (
        create_adjustment_reasons(adjustments)
        .replace("", pd.NA)
    )

    adjustments["record_type"] = "adjustment"

    clean_sales = candidates.loc[
        sale_mask
    ].copy()

    clean_sales["record_type"] = "sale"

    classified_row_count = (
        len(clean_sales)
        + len(cancellations)
        + len(adjustments)
        + len(rejected_rows)
        + len(duplicates)
    )

    if classified_row_count != input_row_count:
        raise DataCleaningError(
            "Row reconciliation failed: "
            f"input={input_row_count:,}, "
            f"classified={classified_row_count:,}"
        )

    return CleaningResult(
        clean_sales=clean_sales.reset_index(drop=True),
        cancellations=cancellations.reset_index(drop=True),
        adjustments=adjustments.reset_index(drop=True),
        rejected_rows=rejected_rows.reset_index(drop=True),
        duplicates=duplicates.reset_index(drop=True),
        input_row_count=input_row_count,
    )


def save_cleaning_result(
    result: CleaningResult,
    output_directory: str | Path,
) -> None:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)

    output_path = (
        directory
        / "sample_cleaning_result.xlsx"
    )

    try:
        with pd.ExcelWriter(
            output_path,
            engine="openpyxl",
        ) as writer:
            result.summary().to_excel(
                writer,
                sheet_name="Summary",
                index=False,
            )

            result.clean_sales.to_excel(
                writer,
                sheet_name="Clean Sales",
                index=False,
            )

            result.cancellations.to_excel(
                writer,
                sheet_name="Cancellations",
                index=False,
            )

            result.adjustments.to_excel(
                writer,
                sheet_name="Adjustments",
                index=False,
            )

            result.rejected_rows.to_excel(
                writer,
                sheet_name="Rejected Rows",
                index=False,
            )

            result.duplicates.to_excel(
                writer,
                sheet_name="Duplicates",
                index=False,
            )

    except PermissionError as error:
        raise DataCleaningError(
            f"Cannot save '{output_path.name}'. "
            "Close the file in Excel and run the program again."
        ) from error


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    sample_file = (
        project_root
        / "data"
        / "sample"
        / "sample_transactions.xlsx"
    )

    output_directory = (
        project_root
        / "data"
        / "processed"
    )

    print("Loading sample dataset...")

    dataframe = load_file(sample_file)

    print("Cleaning and classifying rows...")

    result = clean_dataframe(dataframe)

    print("\nCLEANING SUMMARY")
    print(result.summary().to_string(index=False))

    reconciled_count = (
        len(result.clean_sales)
        + len(result.cancellations)
        + len(result.adjustments)
        + len(result.rejected_rows)
        + len(result.duplicates)
    )

    print("\nROW RECONCILIATION")
    print(
        f"Input rows: "
        f"{result.input_row_count:,}"
    )
    print(
        f"Classified rows: "
        f"{reconciled_count:,}"
    )
    print(
        "Balanced: "
        f"{reconciled_count == result.input_row_count}"
    )

    print("\nADJUSTMENT REASONS")
    print(
        result.adjustments[
            "adjustment_reason"
        ].value_counts().to_string()
    )

    print("\nDATA QUALITY STATUS IN CLEAN SALES")
    print(
        result.clean_sales[
            "data_quality_status"
        ].value_counts().to_string()
    )

    save_cleaning_result(
        result,
        output_directory,
    )

    output_file = (
        output_directory
        / "sample_cleaning_result.xlsx"
    )

    print(f"\nWorkbook saved to: {output_file}")
    print("Cleaning completed successfully.")


if __name__ == "__main__":
    main()