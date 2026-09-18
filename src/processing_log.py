from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from uuid import uuid4
import platform

import pandas as pd

from .analytics import create_analytics
from .cleaner import clean_dataframe
from .loader import load_file
from .transformer import transform_cleaning_result
from .validator import validate_dataframe


class ProcessingLogError(Exception):
    """Raised when a processing log cannot be created or saved."""


@dataclass
class ProcessingLogResult:
    run_summary: pd.DataFrame
    stage_timings: pd.DataFrame
    validation_issues: pd.DataFrame


def calculate_file_sha256(
    file_path: str | Path,
) -> str:
    path = Path(file_path)
    file_hash = sha256()

    with path.open("rb") as source_file:
        while True:
            chunk = source_file.read(1024 * 1024)

            if not chunk:
                break

            file_hash.update(chunk)

    return file_hash.hexdigest()


def add_stage_timing(
    records: list[dict],
    stage_name: str,
    started_at: float,
) -> None:
    duration = perf_counter() - started_at

    records.append(
        {
            "stage": stage_name,
            "duration_seconds": round(duration, 4),
        }
    )


def create_processing_log(
    input_file: str | Path,
) -> ProcessingLogResult:
    file_path = Path(input_file)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Input file was not found: {file_path}"
        )

    run_started_at = datetime.now()
    total_started_at = perf_counter()

    run_id = (
        run_started_at.strftime("%Y%m%d-%H%M%S")
        + "-"
        + uuid4().hex[:8]
    )

    stage_records: list[dict] = []

    stage_started_at = perf_counter()
    input_sha256 = calculate_file_sha256(
        file_path
    )
    add_stage_timing(
        stage_records,
        "Calculate input checksum",
        stage_started_at,
    )

    stage_started_at = perf_counter()
    dataframe = load_file(file_path)
    add_stage_timing(
        stage_records,
        "Load data",
        stage_started_at,
    )

    stage_started_at = perf_counter()
    validation_report = validate_dataframe(
        dataframe
    )
    add_stage_timing(
        stage_records,
        "Validate data",
        stage_started_at,
    )

    if not validation_report.is_valid:
        errors = [
            issue.message
            for issue in validation_report.errors
        ]

        raise ProcessingLogError(
            "Dataset validation failed: "
            + " | ".join(errors)
        )

    stage_started_at = perf_counter()
    cleaning_result = clean_dataframe(
        dataframe
    )
    add_stage_timing(
        stage_records,
        "Clean and classify data",
        stage_started_at,
    )

    stage_started_at = perf_counter()
    transformation_result = (
        transform_cleaning_result(
            cleaning_result
        )
    )
    add_stage_timing(
        stage_records,
        "Add business features",
        stage_started_at,
    )

    stage_started_at = perf_counter()
    analytics_result = create_analytics(
        transformation_result
    )
    add_stage_timing(
        stage_records,
        "Calculate analytics",
        stage_started_at,
    )

    run_finished_at = datetime.now()
    total_duration = (
        perf_counter() - total_started_at
    )

    classified_rows = (
        len(cleaning_result.clean_sales)
        + len(cleaning_result.cancellations)
        + len(cleaning_result.adjustments)
        + len(cleaning_result.rejected_rows)
        + len(cleaning_result.duplicates)
    )

    source_file_count = 0
    source_sheet_count = 0

    if "_source_file" in dataframe.columns:
        source_file_count = int(
            dataframe[
                "_source_file"
            ].nunique(dropna=True)
        )

    if "_source_sheet" in dataframe.columns:
        source_sheet_count = int(
            dataframe[
                "_source_sheet"
            ].nunique(dropna=True)
        )

    total_revenue = float(
        transformation_result.sales[
            "revenue"
        ].sum()
    )

    cancellation_value = float(
        transformation_result.cancellations[
            "cancellation_value"
        ].sum()
    )

    adjustment_value = float(
        transformation_result.adjustments[
            "adjustment_value"
        ].sum()
    )

    run_records = [
        {
            "property": "Run ID",
            "value": run_id,
        },
        {
            "property": "Status",
            "value": "SUCCESS",
        },
        {
            "property": "Started at",
            "value": run_started_at,
        },
        {
            "property": "Finished at",
            "value": run_finished_at,
        },
        {
            "property": "Total duration seconds",
            "value": round(total_duration, 4),
        },
        {
            "property": "Input file",
            "value": file_path.name,
        },
        {
            "property": "Input size MB",
            "value": round(
                file_path.stat().st_size
                / 1024
                / 1024,
                2,
            ),
        },
        {
            "property": "Input SHA256",
            "value": input_sha256,
        },
        {
            "property": "Source files",
            "value": source_file_count,
        },
        {
            "property": "Source sheets",
            "value": source_sheet_count,
        },
        {
            "property": "Rows loaded",
            "value": len(dataframe),
        },
        {
            "property": "Columns loaded",
            "value": dataframe.shape[1],
        },
        {
            "property": "Validation errors",
            "value": len(
                validation_report.errors
            ),
        },
        {
            "property": "Validation warnings",
            "value": len(
                validation_report.warnings
            ),
        },
        {
            "property": "Clean sales",
            "value": len(
                cleaning_result.clean_sales
            ),
        },
        {
            "property": "Cancellations",
            "value": len(
                cleaning_result.cancellations
            ),
        },
        {
            "property": "Adjustments",
            "value": len(
                cleaning_result.adjustments
            ),
        },
        {
            "property": "Rejected rows",
            "value": len(
                cleaning_result.rejected_rows
            ),
        },
        {
            "property": "Removed duplicates",
            "value": len(
                cleaning_result.duplicates
            ),
        },
        {
            "property": "Classified rows",
            "value": classified_rows,
        },
        {
            "property": "Row reconciliation",
            "value": (
                classified_rows
                == len(dataframe)
            ),
        },
        {
            "property": "Sales revenue GBP",
            "value": round(
                total_revenue,
                2,
            ),
        },
        {
            "property": "Cancellation value GBP",
            "value": round(
                cancellation_value,
                2,
            ),
        },
        {
            "property": "Adjustment value GBP",
            "value": round(
                adjustment_value,
                2,
            ),
        },
        {
            "property": "KPI records",
            "value": len(
                analytics_result.kpis
            ),
        },
        {
            "property": "Python version",
            "value": platform.python_version(),
        },
        {
            "property": "Pandas version",
            "value": pd.__version__,
        },
    ]

    stage_records.append(
        {
            "stage": "Total pipeline",
            "duration_seconds": round(
                total_duration,
                4,
            ),
        }
    )

    return ProcessingLogResult(
        run_summary=pd.DataFrame(
            run_records
        ),
        stage_timings=pd.DataFrame(
            stage_records
        ),
        validation_issues=(
            validation_report.to_dataframe()
        ),
    )


def save_processing_log(
    result: ProcessingLogResult,
    output_directory: str | Path,
) -> None:
    directory = Path(output_directory)
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        directory
        / "sample_processing_log.xlsx"
    )

    try:
        with pd.ExcelWriter(
            output_path,
            engine="openpyxl",
        ) as writer:
            result.run_summary.to_excel(
                writer,
                sheet_name="Run Summary",
                index=False,
            )

            result.stage_timings.to_excel(
                writer,
                sheet_name="Stage Timings",
                index=False,
            )

            result.validation_issues.to_excel(
                writer,
                sheet_name="Validation Issues",
                index=False,
            )

    except PermissionError as error:
        raise ProcessingLogError(
            f"Cannot save '{output_path.name}'. "
            "Close the file in Excel and run the program again."
        ) from error


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    input_file = (
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

    print("Running processing pipeline...")

    result = create_processing_log(
        input_file
    )

    print("\nRUN SUMMARY")
    print(
        result.run_summary.to_string(
            index=False
        )
    )

    print("\nSTAGE TIMINGS")
    print(
        result.stage_timings.to_string(
            index=False
        )
    )

    print("\nVALIDATION ISSUES")
    print(
        result.validation_issues.to_string(
            index=False
        )
    )

    save_processing_log(
        result,
        output_directory,
    )

    output_file = (
        output_directory
        / "sample_processing_log.xlsx"
    )

    print(f"\nWorkbook saved to: {output_file}")
    print("Processing log created successfully.")


if __name__ == "__main__":
    main()