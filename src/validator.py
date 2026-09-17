from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

from .loader import load_file


REQUIRED_COLUMNS = (
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
)

IssueLevel = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class ValidationIssue:
    level: IssueLevel
    code: str
    message: str
    count: int | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(
        self,
        level: IssueLevel,
        code: str,
        message: str,
        count: int | None = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                level=level,
                code=code,
                message=message,
                count=count,
            )
        )

    @property
    def errors(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.level == "error"
        ]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.level == "warning"
        ]

    @property
    def information(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.level == "info"
        ]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "level": issue.level,
                    "code": issue.code,
                    "message": issue.message,
                    "count": issue.count,
                }
                for issue in self.issues
            ]
        )


def count_invalid_numeric_values(
    series: pd.Series,
) -> int:
    converted = pd.to_numeric(
        series,
        errors="coerce",
    )

    invalid_mask = series.notna() & converted.isna()

    return int(invalid_mask.sum())


def count_invalid_dates(
    series: pd.Series,
) -> int:
    converted = pd.to_datetime(
        series,
        errors="coerce",
    )

    invalid_mask = series.notna() & converted.isna()

    return int(invalid_mask.sum())


def validate_dataframe(
    dataframe: pd.DataFrame,
) -> ValidationReport:
    report = ValidationReport()

    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame.")

    report.add(
        level="info",
        code="row_count",
        message=f"Rows received: {len(dataframe):,}",
        count=len(dataframe),
    )

    report.add(
        level="info",
        code="column_count",
        message=f"Columns received: {dataframe.shape[1]}",
        count=dataframe.shape[1],
    )

    if dataframe.empty:
        report.add(
            level="error",
            code="empty_dataframe",
            message="The dataset contains no rows.",
            count=0,
        )

        return report

    duplicated_columns = (
        dataframe.columns[
            dataframe.columns.duplicated()
        ]
        .astype(str)
        .tolist()
    )

    if duplicated_columns:
        report.add(
            level="error",
            code="duplicated_columns",
            message=(
                "Duplicated column names: "
                + ", ".join(duplicated_columns)
            ),
            count=len(duplicated_columns),
        )

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        report.add(
            level="error",
            code="missing_columns",
            message=(
                "Required columns are missing: "
                + ", ".join(missing_columns)
            ),
            count=len(missing_columns),
        )

        return report

    for column in ("Quantity", "UnitPrice"):
        invalid_count = count_invalid_numeric_values(
            dataframe[column]
        )

        if invalid_count:
            report.add(
                level="error",
                code=f"invalid_{column.lower()}",
                message=(
                    f"Column '{column}' contains "
                    f"{invalid_count:,} non-numeric values."
                ),
                count=invalid_count,
            )

    invalid_date_count = count_invalid_dates(
        dataframe["InvoiceDate"]
    )

    if invalid_date_count:
        report.add(
            level="error",
            code="invalid_invoice_date",
            message=(
                "Column 'InvoiceDate' contains "
                f"{invalid_date_count:,} invalid dates."
            ),
            count=invalid_date_count,
        )

    duplicate_count = int(
        dataframe[
            list(REQUIRED_COLUMNS)
        ].duplicated().sum()
    )

    if duplicate_count:
        report.add(
            level="warning",
            code="duplicate_rows",
            message=(
                f"Found {duplicate_count:,} exact duplicate rows."
            ),
            count=duplicate_count,
        )

    missing_description_count = int(
        dataframe["Description"].isna().sum()
    )

    if missing_description_count:
        report.add(
            level="warning",
            code="missing_description",
            message=(
                f"Found {missing_description_count:,} rows "
                "without a product description."
            ),
            count=missing_description_count,
        )

    missing_customer_count = int(
        dataframe["CustomerID"].isna().sum()
    )

    if missing_customer_count:
        report.add(
            level="warning",
            code="missing_customer",
            message=(
                f"Found {missing_customer_count:,} rows "
                "without a customer identifier."
            ),
            count=missing_customer_count,
        )

    for column in (
        "InvoiceNo",
        "StockCode",
        "InvoiceDate",
        "Quantity",
        "UnitPrice",
        "Country",
    ):
        missing_count = int(
            dataframe[column].isna().sum()
        )

        if missing_count:
            report.add(
                level="warning",
                code=f"missing_{column.lower()}",
                message=(
                    f"Column '{column}' contains "
                    f"{missing_count:,} missing values."
                ),
                count=missing_count,
            )

    quantity = pd.to_numeric(
        dataframe["Quantity"],
        errors="coerce",
    )

    unit_price = pd.to_numeric(
        dataframe["UnitPrice"],
        errors="coerce",
    )

    negative_quantity_count = int(
        (quantity < 0).sum()
    )

    zero_quantity_count = int(
        (quantity == 0).sum()
    )

    negative_price_count = int(
        (unit_price < 0).sum()
    )

    zero_price_count = int(
        (unit_price == 0).sum()
    )

    if negative_quantity_count:
        report.add(
            level="warning",
            code="negative_quantity",
            message=(
                f"Found {negative_quantity_count:,} rows "
                "with a negative quantity."
            ),
            count=negative_quantity_count,
        )

    if zero_quantity_count:
        report.add(
            level="warning",
            code="zero_quantity",
            message=(
                f"Found {zero_quantity_count:,} rows "
                "with a zero quantity."
            ),
            count=zero_quantity_count,
        )

    if negative_price_count:
        report.add(
            level="warning",
            code="negative_unit_price",
            message=(
                f"Found {negative_price_count:,} rows "
                "with a negative unit price."
            ),
            count=negative_price_count,
        )

    if zero_price_count:
        report.add(
            level="warning",
            code="zero_unit_price",
            message=(
                f"Found {zero_price_count:,} rows "
                "with a zero unit price."
            ),
            count=zero_price_count,
        )

    invoice_numbers = dataframe[
        "InvoiceNo"
    ].astype("string")

    cancellation_mask = (
        invoice_numbers
        .str.upper()
        .str.startswith("C", na=False)
    )

    cancellation_count = int(
        cancellation_mask.sum()
    )

    report.add(
        level="info",
        code="cancellation_count",
        message=(
            f"Cancellation rows: {cancellation_count:,}"
        ),
        count=cancellation_count,
    )

    return report


def print_validation_report(
    report: ValidationReport,
) -> None:
    print("\nVALIDATION RESULT")
    print(f"Valid: {report.is_valid}")
    print(f"Errors: {len(report.errors)}")
    print(f"Warnings: {len(report.warnings)}")
    print(f"Information messages: {len(report.information)}")

    print("\nVALIDATION DETAILS")

    for issue in report.issues:
        level = issue.level.upper()
        print(f"[{level}] {issue.code}: {issue.message}")


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    sample_file = (
        project_root
        / "data"
        / "sample"
        / "sample_transactions.xlsx"
    )

    print("Loading sample dataset...")

    dataframe = load_file(sample_file)
    report = validate_dataframe(dataframe)

    print_validation_report(report)

    print("\nINVALID SCHEMA TEST")

    invalid_dataframe = dataframe.drop(
        columns=["UnitPrice"]
    )

    invalid_report = validate_dataframe(
        invalid_dataframe
    )

    print_validation_report(invalid_report)


if __name__ == "__main__":
    main()