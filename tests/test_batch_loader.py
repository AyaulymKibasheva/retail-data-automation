import pandas as pd
import pytest

from src.batch_loader import (
    BatchLoadError,
    calculate_combined_sha256,
    discover_input_files,
    load_and_merge_files,
    load_input_batch,
)


def test_discover_input_files_is_recursive_and_ignores_temporary_files(
    tmp_path, simple_source_dataframe
):
    nested = tmp_path / "nested"
    nested.mkdir()
    simple_source_dataframe.to_csv(tmp_path / "part_1.csv", index=False)
    simple_source_dataframe.to_excel(nested / "part_2.xlsx", index=False)
    simple_source_dataframe.to_excel(tmp_path / "~$open.xlsx", index=False)
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    files = discover_input_files(tmp_path)

    assert {file.name for file in files} == {"part_1.csv", "part_2.xlsx"}


def test_load_and_merge_compatible_files(tmp_path, simple_source_dataframe):
    first = tmp_path / "part_1.csv"
    second = tmp_path / "part_2.xlsx"
    simple_source_dataframe.iloc[:1].to_csv(first, index=False)
    simple_source_dataframe.iloc[1:].to_excel(second, index=False)

    result = load_and_merge_files([first, second])

    assert len(result) == 2
    assert set(result["_source_file"]) == {"part_1.csv", "part_2.xlsx"}


def test_load_and_merge_rejects_schema_mismatch(
    tmp_path, simple_source_dataframe
):
    first = tmp_path / "correct.csv"
    second = tmp_path / "missing_country.csv"
    simple_source_dataframe.to_csv(first, index=False)
    simple_source_dataframe.drop(columns=["Country"]).to_csv(second, index=False)

    with pytest.raises(BatchLoadError, match="Schema mismatch"):
        load_and_merge_files([first, second])


def test_discover_input_files_rejects_empty_directory(tmp_path):
    with pytest.raises(BatchLoadError, match="No supported files"):
        discover_input_files(tmp_path)


def test_load_input_batch_reports_files_size_and_checksum(
    tmp_path, simple_source_dataframe
):
    first = tmp_path / "part_1.csv"
    second = tmp_path / "part_2.csv"
    simple_source_dataframe.iloc[:1].to_csv(first, index=False)
    simple_source_dataframe.iloc[1:].to_csv(second, index=False)

    result = load_input_batch(tmp_path)

    assert len(result.files) == 2
    assert len(result.dataframe) == 2
    assert result.total_size_mb >= 0
    assert len(result.combined_sha256) == 64
    assert result.combined_sha256 == calculate_combined_sha256(result.files)
