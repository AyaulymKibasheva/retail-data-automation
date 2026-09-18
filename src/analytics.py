from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .cleaner import clean_dataframe
from .loader import load_file
from .transformer import (
    TransformationResult,
    transform_cleaning_result,
)


class AnalyticsError(Exception):
    """Raised when business analytics cannot be calculated."""


@dataclass
class AnalyticsResult:
    kpis: pd.DataFrame
    monthly_summary: pd.DataFrame
    country_summary: pd.DataFrame
    product_summary: pd.DataFrame
    cancellation_summary: pd.DataFrame
    adjustment_summary: pd.DataFrame


def safe_divide(
    numerator: float,
    denominator: float,
) -> float:
    if denominator == 0:
        return 0.0

    return numerator / denominator


def validate_analytics_input(
    result: TransformationResult,
) -> None:
    required_sales_columns = {
        "invoice_no",
        "stock_code",
        "description",
        "quantity",
        "unit_price",
        "customer_id",
        "country",
        "revenue",
        "year_month",
        "market_type",
        "customer_type",
    }

    missing_columns = (
        required_sales_columns
        - set(result.sales.columns)
    )

    if missing_columns:
        raise AnalyticsError(
            "Sales data is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )


def create_kpis(
    result: TransformationResult,
) -> pd.DataFrame:
    sales = result.sales
    cancellations = result.cancellations
    adjustments = result.adjustments

    total_revenue = float(
        sales["revenue"].sum()
    )

    sales_orders = int(
        sales["invoice_no"].nunique()
    )

    units_sold = int(
        sales["quantity"].sum()
    )

    unique_customers = int(
        sales["customer_id"].nunique()
    )

    countries = int(
        sales["country"].nunique()
    )

    average_order_value = safe_divide(
        total_revenue,
        sales_orders,
    )

    cancellation_orders = int(
        cancellations["invoice_no"].nunique()
    )

    cancellation_value = float(
        cancellations[
            "cancellation_value"
        ].sum()
    )

    cancellation_rate = safe_divide(
        cancellation_orders,
        sales_orders + cancellation_orders,
    )

    adjustment_value = float(
        adjustments[
            "adjustment_value"
        ].sum()
    )

    anonymous_sales_rows = int(
        sales["customer_id"].isna().sum()
    )

    anonymous_sales_share = safe_divide(
        anonymous_sales_rows,
        len(sales),
    )

    domestic_revenue = float(
        sales.loc[
            sales["market_type"].eq("domestic"),
            "revenue",
        ].sum()
    )

    international_revenue = float(
        sales.loc[
            sales["market_type"].eq("international"),
            "revenue",
        ].sum()
    )

    records = [
        {
            "metric": "Total revenue",
            "value": round(total_revenue, 2),
            "unit": "GBP",
        },
        {
            "metric": "Sales orders",
            "value": sales_orders,
            "unit": "orders",
        },
        {
            "metric": "Units sold",
            "value": units_sold,
            "unit": "units",
        },
        {
            "metric": "Average order value",
            "value": round(average_order_value, 2),
            "unit": "GBP",
        },
        {
            "metric": "Unique registered customers",
            "value": unique_customers,
            "unit": "customers",
        },
        {
            "metric": "Countries",
            "value": countries,
            "unit": "countries",
        },
        {
            "metric": "Cancellation orders",
            "value": cancellation_orders,
            "unit": "orders",
        },
        {
            "metric": "Cancellation value",
            "value": round(cancellation_value, 2),
            "unit": "GBP",
        },
        {
            "metric": "Cancellation rate",
            "value": round(cancellation_rate, 4),
            "unit": "ratio",
        },
        {
            "metric": "Adjustment value",
            "value": round(adjustment_value, 2),
            "unit": "GBP",
        },
        {
            "metric": "Anonymous sales rows",
            "value": anonymous_sales_rows,
            "unit": "rows",
        },
        {
            "metric": "Anonymous sales share",
            "value": round(anonymous_sales_share, 4),
            "unit": "ratio",
        },
        {
            "metric": "Domestic revenue",
            "value": round(domestic_revenue, 2),
            "unit": "GBP",
        },
        {
            "metric": "International revenue",
            "value": round(international_revenue, 2),
            "unit": "GBP",
        },
    ]

    return pd.DataFrame(records)


def create_monthly_summary(
    sales: pd.DataFrame,
) -> pd.DataFrame:
    summary = (
        sales.groupby(
            "year_month",
            as_index=False,
        )
        .agg(
            revenue=("revenue", "sum"),
            orders=("invoice_no", "nunique"),
            units_sold=("quantity", "sum"),
            registered_customers=(
                "customer_id",
                "nunique",
            ),
            sales_rows=("invoice_no", "size"),
        )
    )

    summary["average_order_value"] = (
        summary["revenue"]
        / summary["orders"]
    ).round(2)

    summary["revenue"] = (
        summary["revenue"].round(2)
    )

    summary = summary.sort_values(
        "year_month"
    ).reset_index(drop=True)

    return summary[
        [
            "year_month",
            "revenue",
            "orders",
            "units_sold",
            "average_order_value",
            "registered_customers",
            "sales_rows",
        ]
    ]


def create_country_summary(
    sales: pd.DataFrame,
) -> pd.DataFrame:
    summary = (
        sales.groupby(
            "country",
            as_index=False,
        )
        .agg(
            revenue=("revenue", "sum"),
            orders=("invoice_no", "nunique"),
            units_sold=("quantity", "sum"),
            registered_customers=(
                "customer_id",
                "nunique",
            ),
            sales_rows=("invoice_no", "size"),
        )
    )

    summary["average_order_value"] = (
        summary["revenue"]
        / summary["orders"]
    ).round(2)

    total_revenue = summary["revenue"].sum()

    summary["revenue_share"] = (
        summary["revenue"]
        / total_revenue
    ).round(4)

    summary["revenue"] = (
        summary["revenue"].round(2)
    )

    summary = summary.sort_values(
        "revenue",
        ascending=False,
    ).reset_index(drop=True)

    summary["revenue_rank"] = (
        summary.index + 1
    )

    return summary[
        [
            "revenue_rank",
            "country",
            "revenue",
            "revenue_share",
            "orders",
            "units_sold",
            "average_order_value",
            "registered_customers",
            "sales_rows",
        ]
    ]


def most_common_description(
    descriptions: pd.Series,
) -> str | pd.NA:
    valid_descriptions = descriptions.dropna()

    if valid_descriptions.empty:
        return pd.NA

    modes = valid_descriptions.mode()

    if modes.empty:
        return valid_descriptions.iloc[0]

    return modes.iloc[0]


def create_product_summary(
    sales: pd.DataFrame,
) -> pd.DataFrame:
    descriptions = (
        sales.groupby("stock_code")[
            "description"
        ]
        .agg(most_common_description)
        .rename("description")
        .reset_index()
    )

    summary = (
        sales.groupby(
            "stock_code",
            as_index=False,
        )
        .agg(
            units_sold=("quantity", "sum"),
            revenue=("revenue", "sum"),
            orders=("invoice_no", "nunique"),
            average_unit_price=(
                "unit_price",
                "mean",
            ),
            sales_rows=("invoice_no", "size"),
        )
    )

    summary = summary.merge(
        descriptions,
        on="stock_code",
        how="left",
        validate="one_to_one",
    )

    total_revenue = summary["revenue"].sum()

    summary["revenue_share"] = (
        summary["revenue"]
        / total_revenue
    ).round(4)

    summary["revenue"] = (
        summary["revenue"].round(2)
    )

    summary["average_unit_price"] = (
        summary["average_unit_price"].round(2)
    )

    summary = summary.sort_values(
        "revenue",
        ascending=False,
    ).reset_index(drop=True)

    summary["revenue_rank"] = (
        summary.index + 1
    )

    return summary[
        [
            "revenue_rank",
            "stock_code",
            "description",
            "revenue",
            "revenue_share",
            "units_sold",
            "orders",
            "average_unit_price",
            "sales_rows",
        ]
    ]


def create_cancellation_summary(
    cancellations: pd.DataFrame,
) -> pd.DataFrame:
    if cancellations.empty:
        return pd.DataFrame(
            columns=[
                "year_month",
                "cancellation_value",
                "cancelled_orders",
                "cancelled_units",
                "cancellation_rows",
            ]
        )

    summary = (
        cancellations.groupby(
            "year_month",
            as_index=False,
        )
        .agg(
            cancellation_value=(
                "cancellation_value",
                "sum",
            ),
            cancelled_orders=(
                "invoice_no",
                "nunique",
            ),
            cancelled_units=(
                "quantity",
                lambda values: values.abs().sum(),
            ),
            cancellation_rows=(
                "invoice_no",
                "size",
            ),
        )
    )

    summary["cancellation_value"] = (
        summary[
            "cancellation_value"
        ].round(2)
    )

    return summary.sort_values(
        "year_month"
    ).reset_index(drop=True)


def create_adjustment_summary(
    adjustments: pd.DataFrame,
) -> pd.DataFrame:
    if adjustments.empty:
        return pd.DataFrame(
            columns=[
                "adjustment_reason",
                "adjustment_rows",
                "adjustment_value",
            ]
        )

    summary = (
        adjustments.groupby(
            "adjustment_reason",
            as_index=False,
            dropna=False,
        )
        .agg(
            adjustment_rows=(
                "invoice_no",
                "size",
            ),
            adjustment_value=(
                "adjustment_value",
                "sum",
            ),
        )
    )

    summary["adjustment_value"] = (
        summary["adjustment_value"].round(2)
    )

    return summary.sort_values(
        "adjustment_rows",
        ascending=False,
    ).reset_index(drop=True)


def create_analytics(
    result: TransformationResult,
) -> AnalyticsResult:
    validate_analytics_input(result)

    return AnalyticsResult(
        kpis=create_kpis(result),
        monthly_summary=create_monthly_summary(
            result.sales
        ),
        country_summary=create_country_summary(
            result.sales
        ),
        product_summary=create_product_summary(
            result.sales
        ),
        cancellation_summary=(
            create_cancellation_summary(
                result.cancellations
            )
        ),
        adjustment_summary=(
            create_adjustment_summary(
                result.adjustments
            )
        ),
    )


def save_analytics_result(
    result: AnalyticsResult,
    output_directory: str | Path,
) -> None:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)

    output_path = (
        directory
        / "sample_analytics_result.xlsx"
    )

    try:
        with pd.ExcelWriter(
            output_path,
            engine="openpyxl",
        ) as writer:
            result.kpis.to_excel(
                writer,
                sheet_name="KPI",
                index=False,
            )

            result.monthly_summary.to_excel(
                writer,
                sheet_name="Monthly Summary",
                index=False,
            )

            result.country_summary.to_excel(
                writer,
                sheet_name="Country Summary",
                index=False,
            )

            result.product_summary.to_excel(
                writer,
                sheet_name="Product Summary",
                index=False,
            )

            result.cancellation_summary.to_excel(
                writer,
                sheet_name="Cancellation Summary",
                index=False,
            )

            result.adjustment_summary.to_excel(
                writer,
                sheet_name="Adjustment Summary",
                index=False,
            )

    except PermissionError as error:
        raise AnalyticsError(
            f"Cannot save '{output_path.name}'. "
            "Close the file in Excel and run the program again."
        ) from error


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    sample_file = (
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

    print("Loading sample dataset...")
    dataframe = load_file(sample_file)

    print("Cleaning dataset...")
    cleaning_result = clean_dataframe(dataframe)

    print("Transforming dataset...")
    transformation_result = (
        transform_cleaning_result(
            cleaning_result
        )
    )

    print("Calculating business analytics...")
    analytics_result = create_analytics(
        transformation_result
    )

    print("\nKEY PERFORMANCE INDICATORS")
    print(
        analytics_result.kpis.to_string(
            index=False
        )
    )

    print("\nMONTHLY SUMMARY")
    print(
        analytics_result.monthly_summary.to_string(
            index=False
        )
    )

    print("\nTOP 10 COUNTRIES")
    print(
        analytics_result.country_summary.head(
            10
        ).to_string(index=False)
    )

    print("\nTOP 10 PRODUCTS")
    print(
        analytics_result.product_summary.head(
            10
        ).to_string(index=False)
    )

    save_analytics_result(
        analytics_result,
        output_directory,
    )

    output_file = (
        output_directory
        / "sample_analytics_result.xlsx"
    )

    print(f"\nWorkbook saved to: {output_file}")
    print("Analytics completed successfully.")


if __name__ == "__main__":
    main()