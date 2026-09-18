from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pandas as pd

from .loader import load_file


SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
METADATA_COLUMNS = {"_source_file", "_source_sheet"}


class BatchLoadError(Exception):
    """Raised when input files cannot be merged safely."""


@dataclass
class InputBatch:
    dataframe: pd.DataFrame
    files: list[Path]
    total_size_mb: float
    combined_sha256: str


def discover_input_files(input_path: str | Path) -> list[Path]:
    path = Path(input_path)

    if not path.exists():
        raise FileNotFoundError(f"Input path was not found: {path}")

    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise BatchLoadError(
                f"Unsupported input format '{path.suffix.lower()}'. "
                f"Supported formats: {supported}"
            )
        if path.name.startswith("~$"):
            raise BatchLoadError(
                f"Temporary Excel file cannot be processed: {path.name}"
            )
        return [path]

    files = sorted(
        (
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file()
            and candidate.suffix.lower() in SUPPORTED_EXTENSIONS
            and not candidate.name.startswith("~$")
        ),
        key=lambda candidate: str(candidate).lower(),
    )

    if not files:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise BatchLoadError(
            f"No supported files were found in '{path}'. "
            f"Supported formats: {supported}"
        )

    return files


def calculate_combined_sha256(files: list[Path]) -> str:
    digest = sha256()

    for file_path in files:
        digest.update(file_path.name.encode("utf-8"))
        with file_path.open("rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                digest.update(chunk)

    return digest.hexdigest()


def business_columns(dataframe: pd.DataFrame) -> set[str]:
    return {
        str(column)
        for column in dataframe.columns
        if str(column) not in METADATA_COLUMNS
    }


def load_and_merge_files(files: list[Path]) -> pd.DataFrame:
    if not files:
        raise BatchLoadError("No input files were provided.")

    loaded_frames: list[pd.DataFrame] = []
    expected_columns: set[str] | None = None
    expected_file: Path | None = None

    for file_path in files:
        dataframe = load_file(file_path)

        if dataframe.empty:
            raise BatchLoadError(f"Input file is empty: {file_path.name}")

        current_columns = business_columns(dataframe)

        if expected_columns is None:
            expected_columns = current_columns
            expected_file = file_path
        elif current_columns != expected_columns:
            missing_columns = sorted(expected_columns - current_columns)
            additional_columns = sorted(current_columns - expected_columns)
            details: list[str] = []

            if missing_columns:
                details.append("missing: " + ", ".join(missing_columns))
            if additional_columns:
                details.append("additional: " + ", ".join(additional_columns))

            raise BatchLoadError(
                f"Schema mismatch in '{file_path.name}' compared with "
                f"'{expected_file.name}': " + "; ".join(details)
            )

        loaded_frames.append(dataframe)

    return pd.concat(
        loaded_frames,
        ignore_index=True,
        sort=False,
    )


def load_input_batch(input_path: str | Path) -> InputBatch:
    files = discover_input_files(input_path)
    dataframe = load_and_merge_files(files)
    total_size_bytes = sum(file_path.stat().st_size for file_path in files)

    return InputBatch(
        dataframe=dataframe,
        files=files,
        total_size_mb=round(total_size_bytes / 1024 / 1024, 2),
        combined_sha256=calculate_combined_sha256(files),
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sample_directory = project_root / "data" / "batch_sample"

    print(f"Discovering files in: {sample_directory}")
    batch = load_input_batch(sample_directory)

    print("\nBATCH LOAD RESULT")
    print(f"Files loaded: {len(batch.files)}")
    print(f"Rows loaded: {len(batch.dataframe):,}")
    print(f"Columns loaded: {batch.dataframe.shape[1]}")
    print(f"Total size MB: {batch.total_size_mb:.2f}")
    print(f"Combined SHA256: {batch.combined_sha256}")

    print("\nSOURCE FILES")
    for file_path in batch.files:
        print(f"- {file_path.name}")


if __name__ == "__main__":
    main()
