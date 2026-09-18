import argparse
import sys
from pathlib import Path

from src.excel_exporter import (
    ExcelReportError,
    run_report_pipeline,
    save_final_report,
)


SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Clean retail transaction data and create "
            "a formatted Excel analytics report."
        )
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        default="data/sample/sample_transactions.xlsx",
        help=(
            "Path to the input CSV or Excel file. "
            "Default: data/sample/sample_transactions.xlsx"
        ),
    )

    parser.add_argument(
        "-o",
        "--output",
        default="output/retail_automation_report.xlsx",
        help=(
            "Path for the generated Excel report. "
            "Default: output/retail_automation_report.xlsx"
        ),
    )

    return parser


def validate_input_file(file_path: Path) -> None:
    if not file_path.exists():
        raise FileNotFoundError(
            f"Input file was not found: {file_path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"Input path is not a file: {file_path}"
        )

    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(
            sorted(SUPPORTED_EXTENSIONS)
        )

        raise ValueError(
            f"Unsupported input format '{extension}'. "
            f"Supported formats: {supported}"
        )


def validate_output_file(file_path: Path) -> None:
    if file_path.suffix.lower() != ".xlsx":
        raise ValueError(
            "The output file must use the .xlsx extension."
        )

    if file_path.exists() and file_path.is_dir():
        raise ValueError(
            f"Output path points to a directory: {file_path}"
        )


def main() -> int:
    parser = create_argument_parser()
    arguments = parser.parse_args()

    input_file = Path(
        arguments.input_file
    ).expanduser()

    output_file = Path(
        arguments.output
    ).expanduser()

    try:
        validate_input_file(input_file)
        validate_output_file(output_file)

        print("=" * 60)
        print("RETAIL DATA AUTOMATION")
        print("=" * 60)
        print(f"Input file:  {input_file.resolve()}")
        print(f"Output file: {output_file.resolve()}")
        print()

        print("[1/2] Processing retail data...")

        report = run_report_pipeline(
            input_file
        )

        print("[2/2] Creating Excel report...")

        save_final_report(
            report,
            output_file,
        )

        kpi_values = (
            report.analytics.kpis
            .set_index("metric")["value"]
            .to_dict()
        )

        print()
        print("=" * 60)
        print("PROCESSING COMPLETED")
        print("=" * 60)
        print(
            f"Rows loaded: "
            f"{len(report.raw_data):,}"
        )
        print(
            f"Clean sales: "
            f"{len(report.cleaning.clean_sales):,}"
        )
        print(
            f"Cancellations: "
            f"{len(report.cleaning.cancellations):,}"
        )
        print(
            f"Adjustments: "
            f"{len(report.cleaning.adjustments):,}"
        )
        print(
            f"Duplicates removed: "
            f"{len(report.cleaning.duplicates):,}"
        )
        print(
            f"Total revenue: "
            f"£{kpi_values['Total revenue']:,.2f}"
        )
        print()
        print(
            f"Report created: "
            f"{output_file.resolve()}"
        )

        return 0

    except (
        FileNotFoundError,
        ValueError,
        ExcelReportError,
    ) as error:
        print(
            f"\nERROR: {error}",
            file=sys.stderr,
        )

        return 1

    except PermissionError:
        print(
            "\nERROR: The output Excel file is open. "
            "Close it and run the program again.",
            file=sys.stderr,
        )

        return 1

    except KeyboardInterrupt:
        print(
            "\nProcessing cancelled by the user.",
            file=sys.stderr,
        )

        return 130


if __name__ == "__main__":
    raise SystemExit(main())