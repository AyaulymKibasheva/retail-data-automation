import pandas as pd
import pytest

from src.loader import DataLoadError, load_csv, load_excel, load_file


def test_load_csv_adds_source_metadata(tmp_path, simple_source_dataframe):
    input_file = tmp_path / "transactions.csv"
    simple_source_dataframe.to_csv(input_file, index=False)

    result = load_csv(input_file)

    assert len(result) == 2
    assert result["_source_file"].unique().tolist() == ["transactions.csv"]
    assert result["_source_sheet"].isna().all()


def test_load_excel_combines_all_sheets(tmp_path, simple_source_dataframe):
    input_file = tmp_path / "transactions.xlsx"
    with pd.ExcelWriter(input_file, engine="openpyxl") as writer:
        simple_source_dataframe.iloc[:1].to_excel(
            writer, sheet_name="January", index=False
        )
        simple_source_dataframe.iloc[1:].to_excel(
            writer, sheet_name="February", index=False
        )

    result = load_excel(input_file)

    assert len(result) == 2
    assert set(result["_source_sheet"]) == {"January", "February"}
    assert result["_source_file"].nunique() == 1


def test_load_excel_rejects_unknown_sheet(tmp_path, simple_source_dataframe):
    input_file = tmp_path / "transactions.xlsx"
    simple_source_dataframe.to_excel(input_file, index=False)

    with pytest.raises(DataLoadError, match="Sheets not found"):
        load_excel(input_file, sheet_names=["Missing"])


def test_load_file_rejects_unsupported_extension(tmp_path):
    input_file = tmp_path / "notes.txt"
    input_file.write_text("not retail data", encoding="utf-8")

    with pytest.raises(DataLoadError, match="Unsupported file format"):
        load_file(input_file)


def test_load_file_rejects_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_file(tmp_path / "missing.csv")
