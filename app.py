from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import uuid4
from hashlib import sha256

import pandas as pd
import streamlit as st

from src.analytics import create_analytics
from src.batch_loader import (
    BatchLoadError,
    business_columns,
    calculate_combined_sha256,
)
from src.cleaner import clean_dataframe
from src.excel_exporter import (
    ExcelReportError,
    ReportData,
    save_final_report,
)
from src.loader import DataLoadError, load_file
from src.transformer import transform_cleaning_result
from src.validator import ValidationReport, validate_dataframe


SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}


@dataclass
class UploadedInput:
    paths: list[Path]
    selected_sheets: dict[str, list[str]]


def configure_page() -> None:
    st.set_page_config(
        page_title="Retail Data Automation",
        page_icon="📊",
        layout="wide",
    )

    st.title("Retail Data Automation")
    st.caption(
        "Upload retail CSV or Excel files, validate their structure, "
        "clean the transactions and download a formatted Excel report."
    )


def clear_previous_result() -> None:
    for key in (
        "result_signature",
        "report_bytes",
        "report_name",
        "preview",
        "validation",
        "kpis",
        "monthly_summary",
        "country_summary",
        "product_summary",
        "processing_summary",
    ):
        st.session_state.pop(key, None)


def save_uploaded_files(uploaded_files, directory: Path) -> list[Path]:
    paths: list[Path] = []
    used_names: set[str] = set()

    for uploaded_file in uploaded_files:
        safe_name = Path(uploaded_file.name).name
        extension = Path(safe_name).suffix.lower()

        if extension not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise ValueError(
                f"Unsupported file '{safe_name}'. Supported formats: {supported}"
            )

        normalized_name = safe_name.lower()
        if normalized_name in used_names:
            raise ValueError(
                f"Two uploaded files use the same name: {safe_name}"
            )

        used_names.add(normalized_name)
        destination = directory / safe_name
        destination.write_bytes(uploaded_file.getbuffer())
        paths.append(destination)

    return paths


def choose_excel_sheets(paths: list[Path]) -> dict[str, list[str]]:
    selected_sheets: dict[str, list[str]] = {}

    st.subheader("Input files")
    for path in paths:
        size_mb = path.stat().st_size / 1024 / 1024

        if path.suffix.lower() == ".xlsx":
            with pd.ExcelFile(path, engine="openpyxl") as excel_file:
                available_sheets = list(excel_file.sheet_names)
            selected = st.multiselect(
                f"Sheets from {path.name}",
                options=available_sheets,
                default=available_sheets,
                key=f"sheets::{path.name}::{path.stat().st_size}",
            )
            selected_sheets[path.name] = selected
            st.caption(
                f"{size_mb:.2f} MB · {len(available_sheets)} Excel sheet(s)"
            )
        else:
            selected_sheets[path.name] = []
            st.write(f"**{path.name}**")
            st.caption(f"{size_mb:.2f} MB · CSV file")

    return selected_sheets


def load_selected_files(uploaded_input: UploadedInput) -> pd.DataFrame:
    dataframes: list[pd.DataFrame] = []
    expected_columns: set[str] | None = None
    expected_file: str | None = None

    for path in uploaded_input.paths:
        sheet_names = uploaded_input.selected_sheets[path.name]

        if path.suffix.lower() == ".xlsx" and not sheet_names:
            raise DataLoadError(
                f"Select at least one sheet from '{path.name}'."
            )

        dataframe = load_file(
            path,
            sheet_names=sheet_names if sheet_names else None,
        )

        if dataframe.empty:
            raise BatchLoadError(f"Input file is empty: {path.name}")

        current_columns = business_columns(dataframe)
        if expected_columns is None:
            expected_columns = current_columns
            expected_file = path.name
        elif current_columns != expected_columns:
            missing = sorted(expected_columns - current_columns)
            additional = sorted(current_columns - expected_columns)
            details: list[str] = []

            if missing:
                details.append("missing: " + ", ".join(missing))
            if additional:
                details.append("additional: " + ", ".join(additional))

            raise BatchLoadError(
                f"Schema mismatch in '{path.name}' compared with "
                f"'{expected_file}': " + "; ".join(details)
            )

        dataframes.append(dataframe)

    if not dataframes:
        raise BatchLoadError("No input data was loaded.")

    return pd.concat(dataframes, ignore_index=True, sort=False)


def measure_stage(records: list[dict], stage_name: str, function):
    started_at = perf_counter()
    result = function()
    records.append(
        {
            "stage": stage_name,
            "duration_seconds": round(perf_counter() - started_at, 4),
        }
    )
    return result


def create_uploaded_report(uploaded_input: UploadedInput) -> ReportData:
    run_started_at = datetime.now()
    total_started_at = perf_counter()
    stage_records: list[dict] = []

    raw_data = measure_stage(
        stage_records,
        "Load selected files and sheets",
        lambda: load_selected_files(uploaded_input),
    )
    validation = measure_stage(
        stage_records,
        "Validate data",
        lambda: validate_dataframe(raw_data),
    )

    if not validation.is_valid:
        messages = [issue.message for issue in validation.errors]
        raise ExcelReportError("Validation failed: " + " | ".join(messages))

    cleaning = measure_stage(
        stage_records,
        "Clean and classify data",
        lambda: clean_dataframe(raw_data),
    )
    transformation = measure_stage(
        stage_records,
        "Add business features",
        lambda: transform_cleaning_result(cleaning),
    )
    analytics = measure_stage(
        stage_records,
        "Calculate analytics",
        lambda: create_analytics(transformation),
    )

    total_duration = perf_counter() - total_started_at
    run_finished_at = datetime.now()
    classified_rows = (
        len(cleaning.clean_sales)
        + len(cleaning.cancellations)
        + len(cleaning.adjustments)
        + len(cleaning.rejected_rows)
        + len(cleaning.duplicates)
    )
    input_size_mb = round(
        sum(path.stat().st_size for path in uploaded_input.paths)
        / 1024
        / 1024,
        2,
    )
    input_names = ", ".join(path.name for path in uploaded_input.paths)

    run_summary = pd.DataFrame(
        [
            {
                "property": "Run ID",
                "value": (
                    run_started_at.strftime("%Y%m%d-%H%M%S")
                    + "-"
                    + uuid4().hex[:8]
                ),
            },
            {"property": "Status", "value": "SUCCESS"},
            {"property": "Started at", "value": run_started_at},
            {"property": "Finished at", "value": run_finished_at},
            {
                "property": "Pipeline duration seconds",
                "value": round(total_duration, 4),
            },
            {"property": "Input path", "value": input_names},
            {"property": "Input files", "value": len(uploaded_input.paths)},
            {"property": "Input size MB", "value": input_size_mb},
            {
                "property": "Combined input SHA256",
                "value": calculate_combined_sha256(uploaded_input.paths),
            },
            {"property": "Rows loaded", "value": len(raw_data)},
            {"property": "Columns loaded", "value": raw_data.shape[1]},
            {
                "property": "Validation errors",
                "value": len(validation.errors),
            },
            {
                "property": "Validation warnings",
                "value": len(validation.warnings),
            },
            {"property": "Clean sales", "value": len(cleaning.clean_sales)},
            {
                "property": "Cancellations",
                "value": len(cleaning.cancellations),
            },
            {"property": "Adjustments", "value": len(cleaning.adjustments)},
            {
                "property": "Rejected rows",
                "value": len(cleaning.rejected_rows),
            },
            {
                "property": "Removed duplicates",
                "value": len(cleaning.duplicates),
            },
            {"property": "Classified rows", "value": classified_rows},
            {
                "property": "Row reconciliation",
                "value": classified_rows == len(raw_data),
            },
        ]
    )
    stage_records.append(
        {
            "stage": "Total pipeline",
            "duration_seconds": round(total_duration, 4),
        }
    )

    return ReportData(
        raw_data=raw_data,
        validation=validation,
        cleaning=cleaning,
        transformation=transformation,
        analytics=analytics,
        run_summary=run_summary,
        stage_timings=pd.DataFrame(stage_records),
    )


def display_validation(report: ValidationReport) -> None:
    validation_frame = report.to_dataframe()
    error_count = len(report.errors)
    warning_count = len(report.warnings)

    first, second, third = st.columns(3)
    first.metric("Validation status", "Valid" if report.is_valid else "Invalid")
    second.metric("Errors", error_count)
    third.metric("Warnings", warning_count)

    st.dataframe(validation_frame, width="stretch", hide_index=True)


def kpi_value(kpis: pd.DataFrame, metric: str) -> float:
    values = kpis.loc[kpis["metric"].eq(metric), "value"]
    if values.empty:
        return 0.0
    return float(values.iloc[0])


def display_results() -> None:
    if "report_bytes" not in st.session_state:
        return

    st.success("Processing completed successfully.")

    kpis = st.session_state["kpis"]
    first_row = st.columns(4)
    first_row[0].metric(
        "Total revenue",
        f"£{kpi_value(kpis, 'Total revenue'):,.2f}",
    )
    first_row[1].metric(
        "Sales orders",
        f"{kpi_value(kpis, 'Sales orders'):,.0f}",
    )
    first_row[2].metric(
        "Units sold",
        f"{kpi_value(kpis, 'Units sold'):,.0f}",
    )
    first_row[3].metric(
        "Average order value",
        f"£{kpi_value(kpis, 'Average order value'):,.2f}",
    )

    second_row = st.columns(4)
    second_row[0].metric(
        "Registered customers",
        f"{kpi_value(kpis, 'Unique registered customers'):,.0f}",
    )
    second_row[1].metric(
        "Cancellation rate",
        f"{kpi_value(kpis, 'Cancellation rate'):.2%}",
    )
    second_row[2].metric(
        "Cancellation value",
        f"£{kpi_value(kpis, 'Cancellation value'):,.2f}",
    )
    second_row[3].metric(
        "Countries",
        f"{kpi_value(kpis, 'Countries'):,.0f}",
    )

    overview_tab, monthly_tab, countries_tab, products_tab, quality_tab = st.tabs(
        [
            "Overview",
            "Monthly",
            "Countries",
            "Products",
            "Data quality",
        ]
    )

    with overview_tab:
        st.subheader("Input preview")
        st.dataframe(
            st.session_state["preview"],
            width="stretch",
            hide_index=True,
        )
        st.subheader("Processing summary")

        processing_preview = (
            st.session_state["processing_summary"].copy()
        )
        processing_preview["value"] = (
            processing_preview["value"]
            .astype("string")
            .fillna("")
        )

        st.dataframe(
            processing_preview,
            width="stretch",
            hide_index=True,
        )

    with monthly_tab:
        monthly = st.session_state["monthly_summary"]
        st.line_chart(
            monthly.set_index("year_month")["revenue"],
            x_label="Month",
            y_label="Revenue (GBP)",
        )
        st.dataframe(monthly, width="stretch", hide_index=True)

    with countries_tab:
        countries = st.session_state["country_summary"]
        top_countries = countries.head(10)
        st.bar_chart(
            top_countries.set_index("country")["revenue"],
            x_label="Country",
            y_label="Revenue (GBP)",
        )
        st.dataframe(countries, width="stretch", hide_index=True)

    with products_tab:
        products = st.session_state["product_summary"]
        st.dataframe(products.head(100), width="stretch", hide_index=True)
        st.caption("Showing the first 100 products ranked by revenue.")

    with quality_tab:
        validation_frame = st.session_state["validation"]
        st.dataframe(validation_frame, width="stretch", hide_index=True)

    st.download_button(
        "Download Excel report",
        data=st.session_state["report_bytes"],
        file_name=st.session_state["report_name"],
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        type="primary",
    )


def main() -> None:
    configure_page()

    with st.sidebar:
        st.header("How to use")
        st.markdown(
            "1. Upload one or more CSV/XLSX files.\n"
            "2. Select Excel sheets.\n"
            "3. Click **Process Data**.\n"
            "4. Review the results and download the report."
        )
        st.info(
            "Files must use the Online Retail column structure. "
            "Uploaded data is processed only for the current session."
        )

    uploaded_files = st.file_uploader(
        "Upload retail data",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
        help="You can upload one file or several files with matching columns.",
    )

    if not uploaded_files:
        st.info("Upload at least one CSV or Excel file to begin.")
        clear_previous_result()
        return

    try:
        with TemporaryDirectory(prefix="retail_streamlit_") as temporary_name:
            temporary_directory = Path(temporary_name)
            paths = save_uploaded_files(uploaded_files, temporary_directory)
            selected_sheets = choose_excel_sheets(paths)

            signature = tuple(
                (
                    path.name,
                    path.stat().st_size,
                    sha256(path.read_bytes()).hexdigest(),
                    tuple(selected_sheets[path.name]),
                )
                for path in paths
            )

            if st.session_state.get("result_signature") != signature:
                clear_previous_result()

            missing_selection = any(
                path.suffix.lower() == ".xlsx"
                and not selected_sheets[path.name]
                for path in paths
            )

            process = st.button(
                "Process Data",
                type="primary",
                disabled=missing_selection,
            )

            if missing_selection:
                st.warning("Select at least one sheet from every Excel file.")

            if process:
                uploaded_input = UploadedInput(
                    paths=paths,
                    selected_sheets=selected_sheets,
                )

                with st.spinner("Validating and processing data..."):
                    report = create_uploaded_report(uploaded_input)

                display_validation(report.validation)

                output_file = temporary_directory / "retail_automation_report.xlsx"
                with st.spinner("Creating Excel report..."):
                    save_final_report(report, output_file)

                st.session_state["result_signature"] = signature
                st.session_state["report_bytes"] = output_file.read_bytes()
                st.session_state["report_name"] = output_file.name
                st.session_state["preview"] = report.raw_data.head(20)
                st.session_state["validation"] = report.validation.to_dataframe()
                st.session_state["kpis"] = report.analytics.kpis
                st.session_state["monthly_summary"] = (
                    report.analytics.monthly_summary
                )
                st.session_state["country_summary"] = (
                    report.analytics.country_summary
                )
                st.session_state["product_summary"] = (
                    report.analytics.product_summary
                )
                st.session_state["processing_summary"] = report.run_summary

            display_results()

    except (
        FileNotFoundError,
        ValueError,
        DataLoadError,
        BatchLoadError,
        ExcelReportError,
    ) as error:
        clear_previous_result()
        st.error(str(error))
    except Exception as error:
        clear_previous_result()
        st.error(f"Unexpected processing error: {error}")


if __name__ == "__main__":
    main()
