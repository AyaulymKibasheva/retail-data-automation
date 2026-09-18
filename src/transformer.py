from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .cleaner import CleaningResult, clean_dataframe
from .loader import load_file


class DataTransformationError(Exception):
    """Raised when cleaned data cannot be transformed safely."""


@dataclass
class TransformationResult:
    sales: pd.DataFrame
    cancellations: pd.DataFrame
    adjustments: pd.DataFrame
    rejected_rows: pd.DataFrame
    duplicates: pd.DataFrame

    def summary(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "dataset": "Sales",
                    "rows": len(self.sales),
                },
                {
                    "dataset": "Cancellations",
                    "rows": len(self.cancellations),
                },
                {
                    "dataset": "Adjustments",
                    "rows": len(self.adjustments),
                },
                {
                    "dataset": "Rejected rows",
                    "rows": len(self.rejected_rows),
                },
                {
                    "dataset": "Duplicates",
                    "rows": len(self.duplicates),
                },
            ]
        )


def add_common_features(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    result = dataframe.copy()

    result["line_value"] = (
        result["quantity"] * result["unit_price"]
    ).round(2)

    result["order_date"] = (
        result["invoice_date"].dt.normalize()
    )

    result["order_year"] = (
        result["invoice_date"]
        .dt.year
        .astype("Int64")
    )

    result["order_quarter"] = (
        "Q"
        + result["invoice_date"]
        .dt.quarter
        .astype("Int64")
        .astype("string")
    )

    result["order_month"] = (
        result["invoice_date"]
        .dt.month
        .astype("Int64")
    )

    result["month_name"] = (
        result["invoice_date"].dt.month_name()
    )

    result["year_month"] = (
        result["invoice_date"]
        .dt.to_period("M")
        .astype("string")
    )

    result["order_week"] = (
        result["invoice_date"]
        .dt.isocalendar()
        .week
        .astype("Int64")
    )

    result["weekday_number"] = (
        result["invoice_date"]
        .dt.dayofweek
        .astype("Int64")
    )

    result["weekday_name"] = (
        result["invoice_date"].dt.day_name()
    )

    result["order_hour"] = (
        result["invoice_date"]
        .dt.hour
        .astype("Int64")
    )

    result["is_weekend"] = (
        result["invoice_date"].dt.dayofweek >= 5
    )

    result["has_customer_id"] = (
        result["customer_id"].notna()
    )

    result["customer_type"] = np.where(
        result["customer_id"].notna(),
        "registered",
        "anonymous",
    )

    result["market_type"] = np.where(
        result["country"].eq("United Kingdom"),
        "domestic",
        "international",
    )

    return result


def transform_cleaning_result(
    cleaning_result: CleaningResult,
) -> TransformationResult:
    sales = add_common_features(
        cleaning_result.clean_sales
    )

    cancellations = add_common_features(
        cleaning_result.cancellations
    )

    adjustments = add_common_features(
        cleaning_result.adjustments
    )

    sales["revenue"] = sales["line_value"]

    cancellations["cancellation_value"] = (
        cancellations["line_value"].abs()
    )

    adjustments["adjustment_value"] = (
        adjustments["line_value"]
    )

    if sales["revenue"].lt(0).any():
        raise DataTransformationError(
            "Negative revenue was found in clean sales."
        )

    if cancellations[
        "cancellation_value"
    ].lt(0).any():
        raise DataTransformationError(
            "Negative cancellation value was produced."
        )

    sales = sales.sort_values(
        [
            "invoice_date",
            "invoice_no",
            "stock_code",
        ]
    ).reset_index(drop=True)

    cancellations = cancellations.sort_values(
        [
            "invoice_date",
            "invoice_no",
            "stock_code",
        ]
    ).reset_index(drop=True)

    adjustments = adjustments.sort_values(
        [
            "invoice_date",
            "invoice_no",
            "stock_code",
        ]
    ).reset_index(drop=True)

    return TransformationResult(
        sales=sales,
        cancellations=cancellations,
        adjustments=adjustments,
        rejected_rows=(
            cleaning_result.rejected_rows.copy()
        ),
        duplicates=(
            cleaning_result.duplicates.copy()
        ),
    )


def save_transformation_result(
    result: TransformationResult,
    output_directory: str | Path,
) -> None:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)

    output_path = (
        directory
        / "sample_transformation_result.xlsx"
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

            result.sales.to_excel(
                writer,
                sheet_name="Sales Enriched",
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
        raise DataTransformationError(
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

    print("Cleaning dataset...")

    cleaning_result = clean_dataframe(
        dataframe
    )

    print("Adding business features...")

    result = transform_cleaning_result(
        cleaning_result
    )

    print("\nTRANSFORMATION SUMMARY")
    print(result.summary().to_string(index=False))

    print("\nFINANCIAL CHECK")
    print(
        "Sales revenue: "
        f"{result.sales['revenue'].sum():,.2f}"
    )
    print(
        "Cancellation value: "
        f"{result.cancellations['cancellation_value'].sum():,.2f}"
    )
    print(
        "Adjustment value: "
        f"{result.adjustments['adjustment_value'].sum():,.2f}"
    )

    print("\nNEW SALES COLUMNS")

    new_columns = [
        "line_value",
        "order_date",
        "order_year",
        "order_quarter",
        "order_month",
        "month_name",
        "year_month",
        "order_week",
        "weekday_number",
        "weekday_name",
        "order_hour",
        "is_weekend",
        "has_customer_id",
        "customer_type",
        "market_type",
        "revenue",
    ]

    for column in new_columns:
        print(f"- {column}")

    print("\nFIRST 5 TRANSFORMED SALES")

    preview_columns = [
        "invoice_no",
        "stock_code",
        "quantity",
        "unit_price",
        "revenue",
        "year_month",
        "weekday_name",
        "order_hour",
        "customer_type",
        "market_type",
    ]

    print(
        result.sales[
            preview_columns
        ].head().to_string(index=False)
    )

    save_transformation_result(
        result,
        output_directory,
    )

    output_file = (
        output_directory
        / "sample_transformation_result.xlsx"
    )

    print(f"\nWorkbook saved to: {output_file}")
    print("Transformation completed successfully.")


if __name__ == "__main__":
    main()