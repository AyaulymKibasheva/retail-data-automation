import argparse
import sys
from pathlib import Path

from src.batch_loader import BatchLoadError
from src.excel_exporter import ExcelReportError, run_report_pipeline, save_final_report


SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Clean and merge retail CSV/Excel files, then create "
            "a formatted Excel analytics report."
        )
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default="data/sample/sample_transactions.xlsx",
        help=(
            "Path to one CSV/XLSX file or a directory containing files. "
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


def validate_input_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Input path was not found: {path}")

    if path.is_file() and path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"Unsupported input format '{path.suffix.lower()}'. "
            f"Supported formats: {supported}"
        )

    if not path.is_file() and not path.is_dir():
        raise ValueError(f"Input path is neither a file nor a directory: {path}")


def validate_output_file(path: Path) -> None:
    if path.suffix.lower() != ".xlsx":
        raise ValueError("The output file must use the .xlsx extension.")
    if path.exists() and path.is_dir():
        raise ValueError(f"Output path points to a directory: {path}")


def main() -> int:
    parser = create_argument_parser()
    arguments = parser.parse_args()
    input_path = Path(arguments.input_path).expanduser()
    output_file = Path(arguments.output).expanduser()

    try:
        validate_input_path(input_path)
        validate_output_file(output_file)

        print("=" * 60)
        print("RETAIL DATA AUTOMATION")
        print("=" * 60)
        print(f"Input path:  {input_path.resolve()}")
        print(f"Output file: {output_file.resolve()}")
        print()
        print("[1/2] Loading, merging and processing retail data...")
        report = run_report_pipeline(input_path)
        print("[2/2] Creating Excel report...")
        save_final_report(report, output_file)

        kpi_values = report.analytics.kpis.set_index("metric")["value"].to_dict()
        source_file_count = report.raw_data["_source_file"].nunique()

        print()
        print("=" * 60)
        print("PROCESSING COMPLETED")
        print("=" * 60)
        print(f"Source files: {source_file_count:,}")
        print(f"Rows loaded: {len(report.raw_data):,}")
        print(f"Clean sales: {len(report.cleaning.clean_sales):,}")
        print(f"Cancellations: {len(report.cleaning.cancellations):,}")
        print(f"Adjustments: {len(report.cleaning.adjustments):,}")
        print(f"Duplicates removed: {len(report.cleaning.duplicates):,}")
        print(f"Total revenue: £{kpi_values['Total revenue']:,.2f}")
        print()
        print(f"Report created: {output_file.resolve()}")
        return 0

    except (
        FileNotFoundError,
        ValueError,
        BatchLoadError,
        ExcelReportError,
    ) as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        return 1
    except PermissionError:
        print(
            "\nERROR: The output Excel file is open. "
            "Close it and run the program again.",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("\nProcessing cancelled by the user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
