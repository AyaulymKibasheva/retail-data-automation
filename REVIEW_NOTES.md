# Review handoff

## Changes

- CLI rejects source/output collisions and output paths inside a batch folder.
- CLI handles loader, cleaning and transformation errors without a raw traceback.
- CSV/XLSX identifier columns are read as strings, preserving stored leading zeros.
- Streamlit result signature includes a content hash, not only name and size.
- Dashboard no longer labels every input as a development sample.
- International chart axis uses automatic tick spacing for different data scales.
- Added CLI, identifier and Excel exporter regression tests.
- Filled the previously empty README; documented metric definitions and limitations.
- Converted requirements to UTF-8 and retained five direct dependencies with the
  same pinned versions supplied by the author. Removed transitive pins, not packages
  from the author's environment.
- Added ignore rules for common local secrets and review archives.

## Verification limits

Local tests use Python 3.12, pandas 2.2.3, numpy 2.3.5, openpyxl 3.1.5 and
pytest 9.1.1. This is not the author's exact pinned environment.
The sample CLI was rerun. The full dataset was not rerun in this review.
Streamlit was compiled but not browser-tested after these edits.
The generated Excel structure was tested; this is not visual verification in Excel.
No guarantee is made that every defect or security issue has been found.

## Still needed before release

- Verify a fresh install from requirements.txt and the latest GitHub Actions run.
- Rerun tests and Streamlit locally, including upload, sheet selection and download.
- Add screenshots and choose a code license; verify dataset redistribution terms.
- Review hardening for arbitrary untrusted inputs, including spreadsheet formula
  injection, non-finite numeric values, upload/resource limits and Excel row limits.
- CLI and Streamlit still duplicate some orchestration; shared pipeline refactoring
  should be a separate tested change, not mixed into these focused fixes.

## Applying the update safely

Extract retail_review_updates.zip into a NEW temporary folder first. Back up or
commit your current work, then copy its files into the existing project, preserving
relative paths. Do not replace/delete .git, .venv, data/raw or your output folder.
This update overwrites only the named code/configuration/documentation files.

Run from the project folder:

```powershell
python -m pytest -q
python main.py
python -m streamlit run app.py
git status
```

The separate clean source archive omits Git history, environments, editor caches,
raw data and generated reports. It is a distribution copy, not a replacement for
your existing Git working folder. Nothing was deleted from the original upload.
