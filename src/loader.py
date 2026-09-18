from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252")
IDENTIFIER_DTYPES = {name: "string" for name in ("InvoiceNo", "StockCode", "CustomerID")}


class DataLoadError(Exception):
    """Raised when a data file cannot be loaded."""


def validate_file_path(file_path: str | Path) -> Path:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File was not found: {path}")

    if not path.is_file():
        raise DataLoadError(f"Path is not a file: {path}")

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise DataLoadError(
            f"Unsupported file format '{extension}'. "
            f"Supported formats: {supported}"
        )

    return path


def load_csv(
    file_path: str | Path,
    separator: str = ",",
    encoding: str | None = None,
) -> pd.DataFrame:
    path = validate_file_path(file_path)

    encodings = (encoding,) if encoding else CSV_ENCODINGS
    last_error: Exception | None = None

    for current_encoding in encodings:
        try:
            dataframe = pd.read_csv(
                path,
                sep=separator,
                encoding=current_encoding,
                dtype=IDENTIFIER_DTYPES,
            )

            dataframe["_source_file"] = path.name
            dataframe["_source_sheet"] = pd.NA

            return dataframe

        except UnicodeDecodeError as error:
            last_error = error

        except Exception as error:
            raise DataLoadError(
                f"Failed to load CSV file '{path.name}': {error}"
            ) from error

    raise DataLoadError(
        f"Unable to decode CSV file '{path.name}' "
        f"using encodings: {', '.join(encodings)}"
    ) from last_error


def load_excel(
    file_path: str | Path,
    sheet_names: Sequence[str] | None = None,
) -> pd.DataFrame:
    path = validate_file_path(file_path)
    excel_file: pd.ExcelFile | None = None

    try:
        excel_file = pd.ExcelFile(
            path,
            engine="openpyxl",
        )

        available_sheets = excel_file.sheet_names

        if sheet_names is None:
            selected_sheets = available_sheets
        else:
            selected_sheets = list(sheet_names)

        missing_sheets = [
            sheet
            for sheet in selected_sheets
            if sheet not in available_sheets
        ]

        if missing_sheets:
            raise DataLoadError(
                f"Sheets not found in '{path.name}': "
                f"{', '.join(missing_sheets)}"
            )

        if not selected_sheets:
            raise DataLoadError(
                f"No Excel sheets selected for '{path.name}'."
            )

        dataframes: list[pd.DataFrame] = []
        expected_columns: set[str] | None = None
        expected_sheet: str | None = None

        for sheet_name in selected_sheets:
            dataframe = pd.read_excel(
                excel_file,
                sheet_name=sheet_name,
                dtype=IDENTIFIER_DTYPES,
            )

            current_columns = {
                str(column)
                for column in dataframe.columns
            }

            if expected_columns is None:
                expected_columns = current_columns
                expected_sheet = sheet_name
            elif current_columns != expected_columns:
                missing = sorted(expected_columns - current_columns)
                additional = sorted(current_columns - expected_columns)
                details: list[str] = []

                if missing:
                    details.append("missing: " + ", ".join(missing))
                if additional:
                    details.append("additional: " + ", ".join(additional))

                raise DataLoadError(
                    f"Schema mismatch in sheet '{sheet_name}' "
                    f"compared with '{expected_sheet}' in "
                    f"'{path.name}': " + "; ".join(details)
                )

            dataframe["_source_file"] = path.name
            dataframe["_source_sheet"] = sheet_name

            dataframes.append(dataframe)

        return pd.concat(
            dataframes,
            ignore_index=True,
            sort=False,
        )

    except DataLoadError:
        raise

    except Exception as error:
        raise DataLoadError(
            f"Failed to load Excel file '{path.name}': {error}"
        ) from error

    finally:
        if excel_file is not None:
            excel_file.close()


def load_file(
    file_path: str | Path,
    sheet_names: Sequence[str] | None = None,
    csv_separator: str = ",",
) -> pd.DataFrame:
    path = validate_file_path(file_path)
    extension = path.suffix.lower()

    if extension == ".xlsx":
        return load_excel(
            path,
            sheet_names=sheet_names,
        )

    if extension == ".csv":
        return load_csv(
            path,
            separator=csv_separator,
        )

    raise DataLoadError(
        f"Unsupported file format: {extension}"
    )


def load_multiple_files(
    file_paths: Iterable[str | Path],
) -> pd.DataFrame:
    paths = list(file_paths)

    if not paths:
        raise DataLoadError("No input files were provided.")

    dataframes: list[pd.DataFrame] = []

    for file_path in paths:
        dataframes.append(load_file(file_path))

    return pd.concat(
        dataframes,
        ignore_index=True,
        sort=False,
    )


def find_input_files(directory: str | Path) -> list[Path]:
    directory_path = Path(directory)

    if not directory_path.exists():
        raise FileNotFoundError(
            f"Directory was not found: {directory_path}"
        )

    if not directory_path.is_dir():
        raise DataLoadError(
            f"Path is not a directory: {directory_path}"
        )

    files = [
        path
        for path in directory_path.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not path.name.startswith("~$")
    ]

    return sorted(files)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sample_file = (
        project_root
        / "data"
        / "sample"
        / "sample_transactions.xlsx"
    )

    print("Testing data loader...")
    print(f"Input file: {sample_file}")

    dataframe = load_file(sample_file)

    print("\nLOAD RESULT")
    print(f"Rows loaded: {len(dataframe):,}")
    print(f"Columns loaded: {dataframe.shape[1]}")
    print(f"Source files: {dataframe['_source_file'].nunique()}")
    print(
        "Source sheets: "
        f"{dataframe['_source_sheet'].nunique(dropna=True)}"
    )

    print("\nCOLUMN NAMES")
    for column in dataframe.columns:
        print(f"- {column}")

    print("\nFIRST 5 ROWS")
    print(dataframe.head().to_string(index=False))

    print("\nData loader test completed successfully.")


if __name__ == "__main__":
    main()
