from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "online_retail.xlsx"
OUTPUT_FILE = PROJECT_ROOT / "data" / "sample" / "sample_transactions.xlsx"

RANDOM_STATE = 42


def select_rows(
    dataframe: pd.DataFrame,
    condition: pd.Series,
    number_of_rows: int,
) -> pd.DataFrame:
    candidates = dataframe.loc[condition]

    if candidates.empty:
        return candidates.copy()

    sample_size = min(number_of_rows, len(candidates))

    return candidates.sample(
        n=sample_size,
        random_state=RANDOM_STATE,
    )


def create_sample() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file was not found: {INPUT_FILE}"
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("Loading source dataset...")

    dataframe = pd.read_excel(
        INPUT_FILE,
        engine="openpyxl",
    )

    invoice_numbers = dataframe["InvoiceNo"].astype("string")

    cancellation_mask = invoice_numbers.str.startswith(
        "C",
        na=False,
    )

    normal_sales_mask = (
        ~cancellation_mask
        & dataframe["Description"].notna()
        & dataframe["CustomerID"].notna()
        & (dataframe["Quantity"] > 0)
        & (dataframe["UnitPrice"] > 0)
    )

    missing_customer_mask = dataframe["CustomerID"].isna()
    missing_description_mask = dataframe["Description"].isna()
    negative_quantity_mask = dataframe["Quantity"] < 0
    zero_quantity_mask = dataframe["Quantity"] == 0
    negative_price_mask = dataframe["UnitPrice"] < 0
    zero_price_mask = dataframe["UnitPrice"] == 0

    duplicate_rows = dataframe.loc[
        dataframe.duplicated(keep=False)
    ].head(300)

    groups = {
        "normal sales": select_rows(
            dataframe,
            normal_sales_mask,
            4_000,
        ),
        "cancellations": select_rows(
            dataframe,
            cancellation_mask,
            500,
        ),
        "missing customer": select_rows(
            dataframe,
            missing_customer_mask,
            500,
        ),
        "missing description": select_rows(
            dataframe,
            missing_description_mask,
            300,
        ),
        "negative quantity": select_rows(
            dataframe,
            negative_quantity_mask,
            300,
        ),
        "zero quantity": select_rows(
            dataframe,
            zero_quantity_mask,
            100,
        ),
        "negative price": select_rows(
            dataframe,
            negative_price_mask,
            100,
        ),
        "zero price": select_rows(
            dataframe,
            zero_price_mask,
            300,
        ),
        "duplicate rows": duplicate_rows,
    }

    sample = pd.concat(
        groups.values(),
        ignore_index=False,
    )

    sample = sample.loc[
        ~sample.index.duplicated(keep="first")
    ]

    sample = sample.sample(
        frac=1,
        random_state=RANDOM_STATE,
    ).reset_index(drop=True)

    sample.to_excel(
        OUTPUT_FILE,
        index=False,
        engine="openpyxl",
    )

    print("\nFULL DATASET QUALITY SUMMARY")
    print(f"Total rows: {len(dataframe):,}")
    print(f"Exact duplicate rows: {dataframe.duplicated().sum():,}")
    print(f"Cancellation rows: {cancellation_mask.sum():,}")
    print(f"Missing CustomerID: {missing_customer_mask.sum():,}")
    print(f"Missing Description: {missing_description_mask.sum():,}")
    print(f"Negative Quantity: {negative_quantity_mask.sum():,}")
    print(f"Zero Quantity: {zero_quantity_mask.sum():,}")
    print(f"Negative UnitPrice: {negative_price_mask.sum():,}")
    print(f"Zero UnitPrice: {zero_price_mask.sum():,}")

    negative_not_cancelled = (
        negative_quantity_mask & ~cancellation_mask
    )

    cancelled_without_negative_quantity = (
        cancellation_mask
        & (dataframe["Quantity"] >= 0)
    )

    print(
        "Negative Quantity without cancellation InvoiceNo: "
        f"{negative_not_cancelled.sum():,}"
    )

    print(
        "Cancellation InvoiceNo without negative Quantity: "
        f"{cancelled_without_negative_quantity.sum():,}"
    )

    print("\nNEGATIVE PRICE EXAMPLES")
    print(
        dataframe.loc[negative_price_mask]
        .head(20)
        .to_string(index=False)
    )

    print("\nNEGATIVE QUANTITY WITHOUT CANCELLATION EXAMPLES")
    print(
        dataframe.loc[negative_not_cancelled]
        .head(20)
        .to_string(index=False)
    )

    print("\nSAMPLE SUMMARY")
    print(f"Sample rows: {len(sample):,}")
    print(f"Sample columns: {sample.shape[1]}")
    print(f"Saved to: {OUTPUT_FILE}")

    print("\nSample created successfully.")


if __name__ == "__main__":
    create_sample()