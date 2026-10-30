"""
E-Commerce Sales Analytics Dashboard
====================================
Run from the project root:

    streamlit run dashboard/app.py

Default CSV (relative to the project root):

    data/ecommerce_sales_cleaned.csv

Expected CSV columns:
    Order_ID, Order_Date, Customer_ID, Product, Category,
    Price, Quantity, City, Payment_Method, Total_Sales

KPI DEFINITIONS (all calculated from the filtered data, nothing hardcoded)
--------------------------------------------------------------------------
Total Revenue        = sum of Total_Sales
Total Orders         = number of UNIQUE Order_ID values (an order is never counted twice)
Total Quantity Sold  = sum of Quantity
Average Order Value  = Total Revenue / Total Orders
Revenue change       = current period vs the previous period of the same length
"""

from __future__ import annotations

import html
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="E-Commerce Sales Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# 1. SETTINGS  (safe to edit)
# ----------------------------------------------------------------------------
CSV_RELATIVE = Path("data") / "ecommerce_sales_cleaned.csv"
CURRENCY = "₹"  # change to "$", "€", etc. if needed
INDIAN_STYLE = True  # True: Lakh / Crore   False: K / M / B

REQUIRED_COLUMNS = [
    "Order_ID", "Order_Date", "Customer_ID", "Product", "Category",
    "Price", "Quantity", "City", "Payment_Method", "Total_Sales",
]
CATEGORY_COLUMNS = ["Product", "Category", "City", "Payment_Method"]

PRIMARY = "#4F46E5"
ACCENT = "#10B981"
PALETTE = [
    "#4F46E5", "#10B981", "#F59E0B", "#EF4444", "#06B6D4",
    "#8B5CF6", "#EC4899", "#84CC16", "#F97316", "#14B8A6",
]

PLOT_CONFIG = {"displaylogo": False, "responsive": True}

# ----------------------------------------------------------------------------
# 2. NUMBER FORMATTING HELPERS
# ----------------------------------------------------------------------------


def full_money(value: float) -> str:
    """Full precision money text, e.g. ₹12,40,35,200 (Indian) or ₹1,240,352."""
    n = int(round(float(value)))
    sign = "-" if n < 0 else ""
    digits = str(abs(n))
    if INDIAN_STYLE and len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    elif not INDIAN_STYLE:
        digits = f"{abs(n):,}"
    return f"{sign}{CURRENCY}{digits}"


def pick_unit(max_value: float) -> tuple[float, str]:
    """Choose a divisor and label so chart axes show small readable numbers."""
    m = abs(float(max_value)) if pd.notna(max_value) else 0
    if INDIAN_STYLE:
        if m >= 1e7:
            return 1e7, "Cr"
        if m >= 1e5:
            return 1e5, "Lakh"
    else:
        if m >= 1e9:
            return 1e9, "B"
        if m >= 1e6:
            return 1e6, "M"
        if m >= 1e3:
            return 1e3, "K"
    return 1.0, ""


def short_money(value: float) -> str:
    """Compact money text for KPI cards and bar labels, e.g. ₹124.03 Cr."""
    div, label = pick_unit(value)
    if not label:
        return f"{CURRENCY}{value:,.0f}"
    return f"{CURRENCY}{value / div:,.2f} {label}"


def axis_title(name: str, unit_label: str) -> str:
    return f"{name} ({CURRENCY}{' ' + unit_label if unit_label else ''})"


def signed_money(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{full_money(value)}"


def signed_pct(value: float | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:+.{digits}f}%"


def safe_pct_change(current: float, previous: float) -> float | None:
    """Percentage change. Returns None when the previous value is 0 and current is not."""
    if previous == 0:
        if current == 0:
            return 0.0
        return None
    return (current - previous) / previous * 100.0


def parse_date_input(value, fallback_start: date, fallback_end: date) -> tuple[date, date]:
    """date_input returns 1 date while the user is still choosing the 2nd one."""
    if isinstance(value, (tuple, list)):
        if len(value) == 2:
            return value[0], value[1]
        if len(value) == 1:
            return value[0], value[0]
        return fallback_start, fallback_end
    return value, value


# ----------------------------------------------------------------------------
# 3. DATA LOADING, VALIDATION AND CLEANING
# ----------------------------------------------------------------------------


def resolve_csv_path() -> Path:
    """Find the cleaned CSV from the project root, the current folder, or next to this file."""
    here = Path(__file__).resolve().parent
    project_root = here.parent
    candidates = [
        project_root / CSV_RELATIVE,
        Path.cwd() / CSV_RELATIVE,
        (here / ".." / CSV_RELATIVE).resolve(),
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


@st.cache_data(show_spinner="Loading CSV file...")
def load_csv(path: str) -> pd.DataFrame:
    """Read everything as text first; types are converted safely later."""
    return pd.read_csv(path, dtype=str)


def prepare_data(raw: pd.DataFrame):
    """
    Validate columns, fix data types and handle missing values.
    Returns (clean_dataframe_or_None, report_dictionary).
    """
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return None, {"missing_columns": missing}

    df = df[REQUIRED_COLUMNS].copy()
    report: dict = {"rows_loaded": len(df)}

    before = len(df)
    df = df.drop_duplicates()
    report["duplicate_rows_removed"] = before - len(df)

    for col in REQUIRED_COLUMNS:
        if col in ("Price", "Quantity", "Total_Sales"):
            continue
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA)

    unknown_filled = 0
    for col in CATEGORY_COLUMNS + ["Customer_ID"]:
        unknown_filled += int(df[col].isna().sum())
        df[col] = df[col].fillna("Unknown").astype(str)
    report["unknown_labels_filled"] = unknown_filled

    for col in ("Price", "Quantity", "Total_Sales"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    dates = pd.to_datetime(df["Order_Date"], errors="coerce")
    if dates.isna().any():
        try:
            retry = pd.to_datetime(df["Order_Date"], errors="coerce", format="mixed")
            dates = dates.fillna(retry)
        except (TypeError, ValueError):
            pass
    df["Order_Date"] = dates.dt.normalize()

    can_fill = df["Total_Sales"].isna() & df["Price"].notna() & df["Quantity"].notna()
    df.loc[can_fill, "Total_Sales"] = df.loc[can_fill, "Price"] * df.loc[can_fill, "Quantity"]
    report["total_sales_recalculated"] = int(can_fill.sum())

    bad = (
        df["Order_ID"].isna()
        | df["Order_Date"].isna()
        | df["Quantity"].isna()
        | df["Total_Sales"].isna()
        | (df["Quantity"] <= 0)
        | (df["Total_Sales"] < 0)
    )
    report["unusable_rows_dropped"] = int(bad.sum())
    df = df[~bad].copy()

    expected = df["Price"] * df["Quantity"]
    report["total_sales_mismatch"] = int(
        (expected.notna() & ((expected - df["Total_Sales"]).abs() > 0.01)).sum()
    )

    df["Order_ID"] = df["Order_ID"].astype(str)
    df["Quantity"] = df["Quantity"].astype("int64")
    df["Month"] = df["Order_Date"].dt.to_period("M").dt.to_timestamp()
    df = df.sort_values("Order_Date").reset_index(drop=True)

    report["rows_final"] = len(df)
    report["duplicate_order_ids"] = int(df["Order_ID"].duplicated().sum())
    report["missing_columns"] = []
    return df, report


cached_prepare = st.cache_data(show_spinner="Cleaning data...")(prepare_data)


def apply_filters(df, start, end, categories, cities, payments, products):
    mask = (
        df["Order_Date"].between(pd.Timestamp(start), pd.Timestamp(end))
        & df["Category"].isin(categories)
        & df["City"].isin(cities)
        & df["Payment_Method"].isin(payments)
        & df["Product"].isin(products)
    )
    return df.loc[mask].copy()


def compute_kpis(fdf: pd.DataFrame) -> dict:
    revenue = float(fdf["Total_Sales"].sum()) if not fdf.empty else 0.0
    orders = int(fdf["Order_ID"].nunique()) if not fdf.empty else 0
    quantity = int(fdf["Quantity"].sum()) if not fdf.empty else 0
    aov = revenue / orders if orders else 0.0
    return {"revenue": revenue, "orders": orders, "quantity": quantity, "aov": aov}


def previous_window(start: date, end: date) -> tuple[date, date]:
    """The period immediately before start, with the same number of days."""
    days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    return prev_start, prev_end


def monthly_summary(fdf: pd.DataFrame) -> pd.DataFrame:
    m = (
        fdf.groupby("Month")
        .agg(Revenue=("Total_Sales", "sum"), Orders=("Order_ID", "nunique"))
        .reset_index()
        .sort_values("Month")
    )
    m["MoM"] = m["Revenue"].pct_change() * 100
    return m


def orders_over_time(fdf: pd.DataFrame, grain: str) -> pd.DataFrame:
    if grain == "Daily":
        key = fdf["Order_Date"]
    elif grain == "Weekly":
        key = fdf["Order_Date"].dt.to_period("W").dt.start_time
    else:
        key = fdf["Month"]
    s = fdf.groupby(key)["Order_ID"].nunique()
    if grain == "Daily" and len(s) > 0:
        s = s.reindex(pd.date_range(s.index.min(), s.index.max()), fill_value=0)
    return s.rename("Orders").rename_axis("Period").reset_index()


def product_table(fdf: pd.DataFrame) -> pd.DataFrame:
    t = (
        fdf.groupby(["Product", "Category"])
        .agg(
            Avg_Price=("Price", "mean"),
            Units_Sold=("Quantity", "sum"),
            Orders=("Order_ID", "nunique"),
            Revenue=("Total_Sales", "sum"),
        )
        .reset_index()
        .sort_values("Revenue", ascending=False)
    )
    total = t["Revenue"].sum()
    t["Revenue_Share_%"] = (t["Revenue"] / total * 100) if total else 0.0
    return t.reset_index(drop=True)


def build_summary_report(filtered: pd.DataFrame, kpis: dict, start: date, end: date) -> pd.DataFrame:
    """Compact KPI + dimension totals for CSV download."""
    rows = [
        {"Section": "Filter", "Item": "Start date", "Revenue": "", "Orders": "", "Quantity": "", "Note": str(start)},
        {"Section": "Filter", "Item": "End date", "Revenue": "", "Orders": "", "Quantity": "", "Note": str(end)},
        {"Section": "KPI", "Item": "Total Revenue", "Revenue": kpis["revenue"], "Orders": kpis["orders"],
         "Quantity": kpis["quantity"], "Note": full_money(kpis["revenue"])},
        {"Section": "KPI", "Item": "Average Order Value", "Revenue": kpis["aov"], "Orders": kpis["orders"],
         "Quantity": "", "Note": full_money(kpis["aov"])},
    ]
    for dim in ("Category", "City", "Product", "Payment_Method"):
        grouped = (
            filtered.groupby(dim)
            .agg(Revenue=("Total_Sales", "sum"), Orders=("Order_ID", "nunique"), Quantity=("Quantity", "sum"))
            .reset_index()
            .sort_values("Revenue", ascending=False)
        )
        for _, row in grouped.iterrows():
            rows.append({
                "Section": dim,
                "Item": row[dim],
                "Revenue": row["Revenue"],
                "Orders": row["Orders"],
                "Quantity": row["Quantity"],
                "Note": full_money(row["Revenue"]),
            })
    return pd.DataFrame(rows)


def build_insights(fdf: pd.DataFrame, monthly: pd.DataFrame) -> tuple[list[str], list[str]]:
    """
    Data-driven summaries. Observed lines are facts from the current filter.
    Recommendations are cautious next steps, not forecasts or guaranteed outcomes.
    """
    observed: list[str] = []
    recommendations: list[str] = []
    if fdf.empty:
        return ["No rows match the current filters, so no insights can be calculated."], []

    kpis = compute_kpis(fdf)
    observed.append(
        f"Filtered revenue is {full_money(kpis['revenue'])} from {kpis['orders']:,} unique orders "
        f"and {kpis['quantity']:,} units sold. Average order value is {full_money(kpis['aov'])}."
    )

    if len(monthly) >= 2:
        first, last = monthly.iloc[0], monthly.iloc[-1]
        peak = monthly.loc[monthly["Revenue"].idxmax()]
        trend_pct = safe_pct_change(float(last["Revenue"]), float(first["Revenue"]))
        trend_txt = signed_pct(trend_pct) if trend_pct is not None else "n/a (first month revenue is 0)"
        observed.append(
            f"Monthly revenue moved from {full_money(first['Revenue'])} in {first['Month']:%b %Y} "
            f"to {full_money(last['Revenue'])} in {last['Month']:%b %Y} "
            f"({trend_txt} across the filtered months). "
            f"The highest-revenue month in this view is {peak['Month']:%b %Y} "
            f"at {full_money(peak['Revenue'])}."
        )
        if trend_pct is not None and trend_pct < -10:
            recommendations.append(
                "Revenue in the latest filtered month is more than 10% below the first month. "
                "Review whether the drop is concentrated in a category, city, or product before changing assortment."
            )
        elif trend_pct is not None and trend_pct > 10:
            recommendations.append(
                "Revenue rose more than 10% from the first to the last filtered month. "
                "Check whether the increase is spread across products or driven by a small set of SKUs."
            )
    elif len(monthly) == 1:
        only = monthly.iloc[0]
        observed.append(
            f"Only one month is visible after filtering ({only['Month']:%b %Y}), "
            f"so a month-to-month trend cannot be calculated."
        )

    prod = product_table(fdf)
    if not prod.empty:
        top = prod.iloc[0]
        observed.append(
            f"The highest-revenue product is {top['Product']} ({top['Category']}) "
            f"with {full_money(top['Revenue'])} ({top['Revenue_Share_%']:.1f}% of filtered revenue), "
            f"{int(top['Units_Sold']):,} units, and {int(top['Orders']):,} unique orders."
        )
        if len(prod) >= 3:
            top3_share = prod.head(3)["Revenue_Share_%"].sum()
            observed.append(
                f"The top 3 products together account for {top3_share:.1f}% of filtered revenue."
            )
            if top3_share >= 60:
                recommendations.append(
                    "Revenue is concentrated in a few products. "
                    "Treat this as a concentration risk until you confirm stock and demand for the remaining catalogue."
                )

    city = (
        fdf.groupby("City")
        .agg(Revenue=("Total_Sales", "sum"), Orders=("Order_ID", "nunique"))
        .reset_index()
        .sort_values("Revenue", ascending=False)
    )
    if not city.empty:
        top_city = city.iloc[0]
        city_share = (top_city["Revenue"] / kpis["revenue"] * 100) if kpis["revenue"] else 0.0
        observed.append(
            f"The highest-revenue city is {top_city['City']} with {full_money(top_city['Revenue'])} "
            f"({city_share:.1f}% of filtered revenue) and {int(top_city['Orders']):,} unique orders."
        )
        if len(city) >= 2:
            second = city.iloc[1]
            observed.append(
                f"The second city is {second['City']} at {full_money(second['Revenue'])}."
            )
        if city_share >= 40 and len(city) >= 3:
            recommendations.append(
                f"{top_city['City']} contributes a large share of revenue. "
                "Compare fulfilment and return rates there against other cities before expanding the same mix elsewhere."
            )

    pay = (
        fdf.groupby("Payment_Method")
        .agg(Orders=("Order_ID", "nunique"), Revenue=("Total_Sales", "sum"))
        .reset_index()
        .sort_values("Orders", ascending=False)
    )
    if not pay.empty and kpis["orders"]:
        top_pay = pay.iloc[0]
        pay_share = top_pay["Orders"] / kpis["orders"] * 100
        observed.append(
            f"The most used payment method by unique orders is {top_pay['Payment_Method']} "
            f"({pay_share:.1f}% of orders, {full_money(top_pay['Revenue'])} revenue)."
        )

    if not recommendations:
        recommendations.append(
            "No strong concentration or trend flag stood out beyond the observed totals. "
            "Use the comparison and drill-down views to inspect a specific category or date range."
        )
    return observed, recommendations


# ----------------------------------------------------------------------------
# 4. PAGE SETUP AND STYLING
# ----------------------------------------------------------------------------
if "ui_theme" not in st.session_state:
    st.session_state["ui_theme"] = "Light"


def inject_theme_css(theme: str) -> None:
    dark = theme == "Dark"
    bg = "#0F172A" if dark else "#F8FAFC"
    panel = "#1E293B" if dark else "#FFFFFF"
    text = "#F8FAFC" if dark else "#0F172A"
    muted = "#94A3B8" if dark else "#64748B"
    border = "rgba(148,163,184,0.28)" if dark else "rgba(15,23,42,0.10)"
    st.markdown(
        f"""
        <style>
          .stApp {{ background: {bg}; color: {text}; overflow: visible; }}
          [data-testid="stHeader"] {{ background: transparent; }}
          [data-testid="stSidebar"] {{ background: {panel}; }}
          .block-container,
          [data-testid="stMainBlockContainer"] {{
              padding-top: 4.5rem !important;
              padding-bottom: 2.4rem;
              max-width: 1440px;
              overflow: visible;
          }}
          @media (max-width: 800px) {{
            .block-container,
            [data-testid="stMainBlockContainer"] {{ padding-top: 5.25rem !important; }}
          }}
          h1, h2, h3, h4, p, label, .stMarkdown {{ color: {text}; }}
          .dash-title {{
              font-size: 1.85rem;
              font-weight: 750;
              letter-spacing: -0.02em;
              line-height: 1.35;
              margin: 0;
              padding: 0.2rem 0 0.15rem 0;
              overflow: visible;
              color: {text};
          }}
          .dash-sub {{ color: {muted}; margin-top: .15rem; margin-bottom: 1.05rem; font-size: 0.95rem; }}
          .kpi-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 6px; }}
          @media (max-width: 1200px) {{ .kpi-grid {{ grid-template-columns: repeat(3, 1fr); }} }}
          @media (max-width: 800px)  {{ .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
          @media (max-width: 520px)  {{ .kpi-grid {{ grid-template-columns: 1fr; }} }}
          .kpi-card {{
              background: {panel};
              border: 1px solid {border};
              border-left: 5px solid {PRIMARY};
              border-radius: 12px; padding: 14px 16px;
              box-shadow: 0 8px 24px rgba(15,23,42,0.06);
              min-height: 108px;
          }}
          .kpi-card.c2 {{ border-left-color: {ACCENT}; }}
          .kpi-card.c3 {{ border-left-color: #F59E0B; }}
          .kpi-card.c4 {{ border-left-color: #EF4444; }}
          .kpi-card.c5 {{ border-left-color: #06B6D4; }}
          .kpi-label {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: {muted}; }}
          .kpi-value {{ font-size: 1.45rem; font-weight: 750; line-height: 1.3; color: {text}; margin-top: 4px; }}
          .kpi-note  {{ font-size: .78rem; color: {muted}; margin-top: 4px; }}
          .insight-box {{
              background: {panel}; border: 1px solid {border}; border-radius: 12px;
              padding: 14px 16px; margin-bottom: 10px;
          }}
          .insight-title {{ font-weight: 700; margin-bottom: 6px; color: {text}; }}
          .reco-box {{
              background: {"rgba(16,185,129,0.10)" if dark else "rgba(16,185,129,0.08)"};
              border: 1px solid {border}; border-radius: 12px; padding: 14px 16px;
          }}
          h3 {{ margin-top: .35rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def plotly_template(theme: str) -> str:
    return "plotly_dark" if theme == "Dark" else "plotly_white"


def style(fig: go.Figure, title: str, height: int = 380, legend: bool = True, theme: str = "Light") -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0.01, font=dict(size=16)),
        template=plotly_template(theme),
        height=height,
        margin=dict(l=10, r=10, t=55, b=10),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        hoverlabel=dict(font_size=13),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.22)")
    return fig


def show(fig: go.Figure, key: str) -> None:
    st.plotly_chart(fig, key=key, theme=None, config=PLOT_CONFIG)


def kpi_card(css: str, label: str, value: str, note: str, tooltip: str = "") -> str:
    return (
        f'<div class="kpi-card {css}" title="{html.escape(tooltip)}">'
        f'<div class="kpi-label">{html.escape(label)}</div>'
        f'<div class="kpi-value">{html.escape(value)}</div>'
        f'<div class="kpi-note">{html.escape(note)}</div></div>'
    )


# ----------------------------------------------------------------------------
# 5. SIDEBAR — THEME + DATA SOURCE
# ----------------------------------------------------------------------------
st.sidebar.markdown("### Controls")
theme_choice = st.sidebar.radio(
    "Appearance",
    ["Light", "Dark"],
    index=0 if st.session_state["ui_theme"] == "Light" else 1,
    horizontal=True,
    help="Changes dashboard colours and Plotly chart theme. Streamlit's own menu theme can still be set separately.",
)
st.session_state["ui_theme"] = theme_choice
inject_theme_css(theme_choice)
THEME = theme_choice

st.sidebar.divider()
st.sidebar.markdown("### Data source")

uploaded = st.sidebar.file_uploader(
    "Use a different CSV (optional)",
    type=["csv"],
    help=f"Leave empty to use `{CSV_RELATIVE.as_posix()}` from the project root.",
)

try:
    if uploaded is not None:
        raw_df = pd.read_csv(uploaded, dtype=str)
        source_name = uploaded.name
        csv_path = None
    else:
        csv_path = resolve_csv_path()
        if not csv_path.exists():
            st.error(
                f"**Could not find `{CSV_RELATIVE.as_posix()}`.**\n\n"
                "Place the cleaned CSV at `data/ecommerce_sales_cleaned.csv` in the project root, "
                "or upload a file from the sidebar.\n\n"
                f"Looked for: `{csv_path}`"
            )
            st.stop()
        raw_df = load_csv(str(csv_path))
        source_name = CSV_RELATIVE.as_posix()
except pd.errors.EmptyDataError:
    st.error("The CSV file is empty.")
    st.stop()
except UnicodeDecodeError:
    st.error("The CSV could not be read (encoding problem). Re-save it as UTF-8 CSV.")
    st.stop()

data, report = cached_prepare(raw_df)

if data is None:
    st.error(
        "**Required columns are missing:** " + ", ".join(f"`{c}`" for c in report["missing_columns"])
        + "\n\nRequired columns: " + ", ".join(f"`{c}`" for c in REQUIRED_COLUMNS)
    )
    st.stop()

if data.empty:
    st.error("No usable rows remain after cleaning. Please check your CSV.")
    st.stop()

# ----------------------------------------------------------------------------
# 6. SIDEBAR FILTERS
# ----------------------------------------------------------------------------
min_date = data["Order_Date"].min().date()
max_date = data["Order_Date"].max().date()
all_categories = sorted(data["Category"].unique())
all_cities = sorted(data["City"].unique())
all_products = sorted(data["Product"].unique())
all_payments = sorted(data["Payment_Method"].unique())

signature = (source_name, len(data), str(min_date), str(max_date))
if st.session_state.get("_data_signature") != signature:
    st.session_state["_data_signature"] = signature
    st.session_state["_filter_version"] = st.session_state.get("_filter_version", 0) + 1


def reset_filters() -> None:
    st.session_state["_filter_version"] += 1


fv = st.session_state["_filter_version"]
st.sidebar.divider()
st.sidebar.markdown("### Filters")
st.sidebar.caption("Every KPI, table, and chart below uses these filters.")

date_value = st.sidebar.date_input(
    "Order date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    key=f"f_date_{fv}",
)
sel_categories = st.sidebar.multiselect(
    "Product category", all_categories, default=all_categories, key=f"f_cat_{fv}"
)
sel_products = st.sidebar.multiselect(
    "Product", all_products, default=all_products, key=f"f_prod_{fv}"
)
sel_cities = st.sidebar.multiselect(
    "City", all_cities, default=all_cities, key=f"f_city_{fv}"
)
sel_payments = st.sidebar.multiselect(
    "Payment method", all_payments, default=all_payments, key=f"f_pay_{fv}"
)
st.sidebar.button("Reset all filters", on_click=reset_filters)
st.sidebar.caption("Downloads are also available under Insights & reports.")

start_date, end_date = parse_date_input(date_value, min_date, max_date)
if start_date > end_date:
    start_date, end_date = end_date, start_date

filtered = apply_filters(
    data, start_date, end_date, sel_categories, sel_cities, sel_payments, sel_products
)

# Previous window of the same length (for the revenue-change KPI).
prev_start, prev_end = previous_window(start_date, end_date)
prev_in_data = prev_end >= min_date and prev_start <= max_date
prev_filtered = apply_filters(
    data, prev_start, prev_end, sel_categories, sel_cities, sel_payments, sel_products
) if prev_in_data else data.iloc[0:0].copy()
prev_kpis = compute_kpis(prev_filtered)

# ----------------------------------------------------------------------------
# 7. HEADER
# ----------------------------------------------------------------------------
st.markdown('<div class="dash-title">E-Commerce Sales Analytics</div>', unsafe_allow_html=True)

if filtered.empty:
    st.markdown('<div class="dash-sub">No data for the current filters.</div>', unsafe_allow_html=True)
    st.warning(
        "No orders match the selected filters. Widen the date range or select at least "
        "one option in every filter."
    )
    st.stop()

total_orders_all = int(data["Order_ID"].nunique())
shown_orders = int(filtered["Order_ID"].nunique())
st.markdown(
    f'<div class="dash-sub">{start_date:%d %b %Y} → {end_date:%d %b %Y} &nbsp;•&nbsp; '
    f"showing {shown_orders:,} of {total_orders_all:,} unique orders &nbsp;•&nbsp; "
    f"source: {html.escape(str(source_name))}</div>",
    unsafe_allow_html=True,
)

st.sidebar.divider()
st.sidebar.download_button(
    "Download filtered data (CSV)",
    data=filtered.drop(columns=["Month"]).to_csv(index=False).encode("utf-8"),
    file_name="filtered_sales.csv",
    mime="text/csv",
    key="dl_filtered_sidebar",
)

k = compute_kpis(filtered)
rev_change_pct = safe_pct_change(k["revenue"], prev_kpis["revenue"]) if prev_in_data else None
if not prev_in_data:
    change_note = "Previous period is outside the dataset"
    change_value = "n/a"
    change_tip = f"Comparable window would be {prev_start:%d %b %Y} to {prev_end:%d %b %Y}."
elif prev_filtered.empty:
    change_note = "No orders in the previous window"
    change_value = "n/a"
    change_tip = f"Looked at {prev_start:%d %b %Y} to {prev_end:%d %b %Y} with the same filters."
elif rev_change_pct is None:
    change_note = "Previous revenue is 0, so % change is undefined"
    change_value = "n/a"
    change_tip = (
        f"Previous window {prev_start:%d %b %Y} to {prev_end:%d %b %Y}: "
        f"{full_money(prev_kpis['revenue'])}."
    )
else:
    change_value = signed_pct(rev_change_pct)
    change_note = f"vs {prev_start:%d %b %Y} – {prev_end:%d %b %Y}"
    change_tip = (
        f"Current {full_money(k['revenue'])} vs previous {full_money(prev_kpis['revenue'])} "
        f"({signed_money(k['revenue'] - prev_kpis['revenue'])})."
    )

st.markdown(
    '<div class="kpi-grid">'
    + kpi_card("", "Total Revenue", short_money(k["revenue"]), "Sum of Total_Sales", full_money(k["revenue"]))
    + kpi_card("c2", "Total Orders", f'{k["orders"]:,}', "Unique Order_ID count")
    + kpi_card("c3", "Quantity Sold", f'{k["quantity"]:,}', "Sum of Quantity")
    + kpi_card("c4", "Avg Order Value", full_money(k["aov"]), "Revenue ÷ unique orders")
    + kpi_card("c5", "Revenue change", change_value, change_note, change_tip)
    + "</div>",
    unsafe_allow_html=True,
)

category_colors = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(all_categories)}
pay_colors = {p: PALETTE[i % len(PALETTE)] for i, p in enumerate(all_payments)}

tab_sales, tab_geo, tab_drill, tab_compare, tab_insights = st.tabs(
    [
        "Sales analysis",
        "Geography & payments",
        "Product drill-down",
        "Date comparison",
        "Insights & reports",
    ]
)

# ----------------------------------------------------------------------------
# 8. SALES ANALYSIS
# ----------------------------------------------------------------------------
with tab_sales:
    st.subheader("Sales analysis")

    m = monthly_summary(filtered)
    div, unit = pick_unit(m["Revenue"].max())
    m["rev_txt"] = m["Revenue"].map(full_money)
    m["orders_txt"] = m["Orders"].map(lambda v: f"{v:,}")
    m["mom_txt"] = m["MoM"].map(lambda v: "n/a" if pd.isna(v) else f"{v:+.1f}%")

    fig = go.Figure(
        go.Scatter(
            x=m["Month"], y=m["Revenue"] / div, mode="lines+markers",
            line=dict(color=PRIMARY, width=3), marker=dict(size=8),
            fill="tozeroy", fillcolor="rgba(79,70,229,0.12)",
            customdata=m[["rev_txt", "orders_txt", "mom_txt"]].values,
            hovertemplate="<b>%{x|%B %Y}</b><br>Revenue: %{customdata[0]}"
                          "<br>Orders: %{customdata[1]}<br>vs previous month: %{customdata[2]}<extra></extra>",
        )
    )
    fig.update_xaxes(tickformat="%b %Y", title="")
    fig.update_yaxes(title=axis_title("Revenue", unit), rangemode="tozero")
    show(style(fig, "Monthly revenue trend", legend=False, theme=THEME), "monthly_revenue")

    grain = st.radio(
        "Order analysis – group by",
        ["Daily", "Weekly", "Monthly"],
        index=2,
        horizontal=True,
        key="orders_grain",
    )
    o = orders_over_time(filtered, grain)
    fig = go.Figure()
    if grain == "Daily":
        o["Avg7"] = o["Orders"].rolling(7, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=o["Period"], y=o["Orders"], mode="lines", name="Daily orders",
            line=dict(color="rgba(79,70,229,0.35)", width=1.5),
            hovertemplate="%{x|%d %b %Y}<br>Orders: %{y:,}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=o["Period"], y=o["Avg7"], mode="lines", name="7-day average",
            line=dict(color=PRIMARY, width=3),
            hovertemplate="%{x|%d %b %Y}<br>7-day avg: %{y:,.1f}<extra></extra>",
        ))
        fig.update_xaxes(tickformat="%d %b %Y")
    else:
        fig.add_trace(go.Bar(
            x=o["Period"], y=o["Orders"], name="Orders", marker_color=PRIMARY,
            hovertemplate=(
                ("%{x|%B %Y}" if grain == "Monthly" else "Week of %{x|%d %b %Y}")
                + "<br>Orders: %{y:,}<extra></extra>"
            ),
        ))
        fig.update_xaxes(tickformat="%b %Y" if grain == "Monthly" else "%d %b %Y")
    fig.update_yaxes(title="Unique orders", rangemode="tozero")
    show(style(fig, f"{grain} orders", height=360, legend=(grain == "Daily"), theme=THEME), f"orders_{grain}")

    col_a, col_b = st.columns(2)
    with col_a:
        cat = (
            filtered.groupby("Category", as_index=False)["Total_Sales"]
            .sum()
            .sort_values("Total_Sales", ascending=False)
        )
        fig = go.Figure(go.Pie(
            labels=cat["Category"], values=cat["Total_Sales"], hole=0.55, sort=False,
            marker=dict(colors=[category_colors.get(c, PRIMARY) for c in cat["Category"]]),
            customdata=cat["Total_Sales"].map(full_money),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>Revenue: %{customdata}<br>Share: %{percent}<extra></extra>",
        ))
        show(style(fig, "Revenue by product category", legend=False, theme=THEME), "cat_donut")

    with col_b:
        top_rev = (
            filtered.groupby(["Product", "Category"], as_index=False)["Total_Sales"]
            .sum()
            .sort_values("Total_Sales", ascending=False)
            .head(10)
        )
        div, unit = pick_unit(top_rev["Total_Sales"].max())
        top_rev["Scaled"] = top_rev["Total_Sales"] / div
        top_rev["txt"] = top_rev["Total_Sales"].map(full_money)
        order = top_rev.sort_values("Scaled")["Product"].tolist()
        fig = px.bar(
            top_rev, x="Scaled", y="Product", color="Category", orientation="h",
            color_discrete_map=category_colors, category_orders={"Product": order},
            custom_data=["txt", "Category"],
        )
        fig.update_traces(
            hovertemplate="<b>%{y}</b> (%{customdata[1]})<br>Revenue: %{customdata[0]}<extra></extra>"
        )
        fig.update_xaxes(title=axis_title("Revenue", unit))
        fig.update_yaxes(title="")
        show(style(fig, "Top 10 products by revenue", theme=THEME), "top10_revenue")

    st.markdown("**Highest-revenue products** (sorted by revenue)")
    ptable = product_table(filtered)
    display_table = ptable.rename(columns={
        "Avg_Price": f"Avg Price ({CURRENCY})",
        "Units_Sold": "Units Sold",
        "Revenue": f"Revenue ({CURRENCY})",
        "Revenue_Share_%": "Revenue Share (%)",
    })
    st.dataframe(
        display_table,
        hide_index=True,
        width="stretch",
        column_config={
            f"Avg Price ({CURRENCY})": st.column_config.NumberColumn(format="%.0f"),
            f"Revenue ({CURRENCY})": st.column_config.NumberColumn(format="%d"),
            "Revenue Share (%)": st.column_config.NumberColumn(format="%.1f"),
        },
    )

# ----------------------------------------------------------------------------
# 9. GEOGRAPHICAL + PAYMENT ANALYSIS
# ----------------------------------------------------------------------------
with tab_geo:
    col_c, col_d = st.columns(2)
    with col_c:
        st.subheader("Geographical analysis")
        city = (
            filtered.groupby("City")
            .agg(Revenue=("Total_Sales", "sum"), Orders=("Order_ID", "nunique"))
            .reset_index()
            .sort_values("Revenue", ascending=False)
        )
        div, unit = pick_unit(city["Revenue"].max())
        city["Scaled"] = city["Revenue"] / div
        city["txt"] = city["Revenue"].map(full_money)
        city["orders_txt"] = city["Orders"].map(lambda v: f"{v:,}")
        city["label"] = city["Revenue"].map(short_money)
        fig = px.bar(
            city.sort_values("Scaled"), x="Scaled", y="City", orientation="h",
            text="label", custom_data=["txt", "orders_txt"],
            color_discrete_sequence=[PRIMARY],
        )
        fig.update_traces(
            textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Revenue: %{customdata[0]}<br>Orders: %{customdata[1]}<extra></extra>",
        )
        fig.update_xaxes(title=axis_title("Revenue", unit))
        fig.update_yaxes(title="")
        show(style(fig, "Revenue by city", height=420, legend=False, theme=THEME), "city_revenue")

    with col_d:
        st.subheader("Payment analysis")
        pay = (
            filtered.groupby("Payment_Method")
            .agg(Orders=("Order_ID", "nunique"), Revenue=("Total_Sales", "sum"))
            .reset_index()
            .sort_values("Orders", ascending=False)
        )
        pay["rev_txt"] = pay["Revenue"].map(full_money)
        fig = go.Figure(go.Pie(
            labels=pay["Payment_Method"], values=pay["Orders"], hole=0.55, sort=False,
            marker=dict(colors=[pay_colors.get(p, PRIMARY) for p in pay["Payment_Method"]]),
            customdata=pay["rev_txt"], textinfo="label+percent",
            hovertemplate=(
                "<b>%{label}</b><br>Orders: %{value:,}<br>Share of orders: %{percent}"
                "<br>Revenue: %{customdata}<extra></extra>"
            ),
        ))
        show(style(fig, "Orders by payment method", height=420, legend=False, theme=THEME), "pay_donut")

    col_e, col_f = st.columns(2)
    with col_e:
        top_qty = (
            filtered.groupby(["Product", "Category"], as_index=False)["Quantity"]
            .sum()
            .sort_values("Quantity", ascending=False)
            .head(10)
        )
        order = top_qty.sort_values("Quantity")["Product"].tolist()
        top_qty["txt"] = top_qty["Quantity"].map(lambda v: f"{v:,}")
        fig = px.bar(
            top_qty, x="Quantity", y="Product", color="Category", orientation="h",
            color_discrete_map=category_colors, category_orders={"Product": order},
            custom_data=["txt", "Category"],
        )
        fig.update_traces(
            hovertemplate="<b>%{y}</b> (%{customdata[1]})<br>Units sold: %{customdata[0]}<extra></extra>"
        )
        fig.update_xaxes(title="Units sold")
        fig.update_yaxes(title="")
        show(style(fig, "Top-selling products by quantity", theme=THEME), "top_qty")

    with col_f:
        cm = filtered.groupby(["Month", "Category"], as_index=False)["Total_Sales"].sum()
        div, unit = pick_unit(cm.groupby("Month")["Total_Sales"].sum().max())
        cm["Scaled"] = cm["Total_Sales"] / div
        cm["txt"] = cm["Total_Sales"].map(full_money)
        fig = px.bar(
            cm, x="Month", y="Scaled", color="Category", barmode="stack",
            color_discrete_map=category_colors, custom_data=["txt", "Category"],
        )
        fig.update_traces(
            hovertemplate="<b>%{x|%B %Y}</b><br>%{customdata[1]}: %{customdata[0]}<extra></extra>"
        )
        fig.update_xaxes(tickformat="%b %Y", title="")
        fig.update_yaxes(title=axis_title("Revenue", unit))
        show(style(fig, "Category-wise revenue comparison (by month)", theme=THEME), "cat_monthly")

# ----------------------------------------------------------------------------
# 10. PRODUCT DRILL-DOWN
# ----------------------------------------------------------------------------
with tab_drill:
    st.subheader("Product drill-down")
    st.caption(
        "Pick a category to inspect its products. Totals still respect the sidebar date, city, "
        "product, and payment filters."
    )
    cats_in_view = sorted(filtered["Category"].unique())
    drill_cat = st.selectbox("Category to explore", cats_in_view, key="drill_category")
    drill_df = filtered[filtered["Category"] == drill_cat]
    drill_table = product_table(drill_df)

    if drill_table.empty:
        st.info("No products in this category for the current filters.")
    else:
        d_k = compute_kpis(drill_df)
        c1, c2, c3 = st.columns(3)
        c1.metric("Category revenue", short_money(d_k["revenue"]), help=full_money(d_k["revenue"]))
        c2.metric("Unique orders", f'{d_k["orders"]:,}')
        c3.metric("Units sold", f'{d_k["quantity"]:,}')

        div, unit = pick_unit(drill_table["Revenue"].max())
        chart_df = drill_table.copy()
        chart_df["Scaled"] = chart_df["Revenue"] / div
        chart_df["rev_txt"] = chart_df["Revenue"].map(full_money)
        chart_df["qty_txt"] = chart_df["Units_Sold"].map(lambda v: f"{int(v):,}")
        chart_df["ord_txt"] = chart_df["Orders"].map(lambda v: f"{int(v):,}")
        order = chart_df.sort_values("Scaled")["Product"].tolist()
        fig = px.bar(
            chart_df, x="Scaled", y="Product", orientation="h",
            category_orders={"Product": order},
            custom_data=["rev_txt", "qty_txt", "ord_txt"],
            color_discrete_sequence=[PRIMARY],
        )
        fig.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>Revenue: %{customdata[0]}"
                "<br>Units sold: %{customdata[1]}<br>Orders: %{customdata[2]}<extra></extra>"
            )
        )
        fig.update_xaxes(title=axis_title("Revenue", unit))
        fig.update_yaxes(title="")
        show(style(fig, f"Products in {drill_cat}", height=max(360, 28 * len(chart_df) + 80),
                   legend=False, theme=THEME), "drill_products")

        st.dataframe(
            drill_table.rename(columns={
                "Avg_Price": f"Avg Price ({CURRENCY})",
                "Units_Sold": "Units Sold",
                "Revenue": f"Revenue ({CURRENCY})",
                "Revenue_Share_%": "Share of category (%)",
            }),
            hide_index=True,
            width="stretch",
            column_config={
                f"Avg Price ({CURRENCY})": st.column_config.NumberColumn(format="%.0f"),
                f"Revenue ({CURRENCY})": st.column_config.NumberColumn(format="%d"),
                "Share of category (%)": st.column_config.NumberColumn(format="%.1f"),
            },
        )

# ----------------------------------------------------------------------------
# 11. DATE COMPARISON
# ----------------------------------------------------------------------------
with tab_compare:
    st.subheader("Compare two date ranges")
    st.caption(
        "Category, city, product, and payment filters from the sidebar still apply. "
        "These two date ranges replace the main date filter for this section only."
    )

    default_b_start, default_b_end = previous_window(start_date, end_date)
    if default_b_start < min_date:
        default_b_start = min_date
    if default_b_end < min_date:
        default_b_end = min_date
    if default_b_end > max_date:
        default_b_end = max_date

    left, right = st.columns(2)
    with left:
        range_a_raw = st.date_input(
            "Range A",
            value=(start_date, end_date),
            min_value=min_date,
            max_value=max_date,
            key="cmp_a",
        )
    with right:
        range_b_raw = st.date_input(
            "Range B",
            value=(default_b_start, default_b_end),
            min_value=min_date,
            max_value=max_date,
            key="cmp_b",
        )

    a_start, a_end = parse_date_input(range_a_raw, start_date, end_date)
    b_start, b_end = parse_date_input(range_b_raw, default_b_start, default_b_end)
    if a_start > a_end:
        a_start, a_end = a_end, a_start
    if b_start > b_end:
        b_start, b_end = b_end, b_start

    df_a = apply_filters(data, a_start, a_end, sel_categories, sel_cities, sel_payments, sel_products)
    df_b = apply_filters(data, b_start, b_end, sel_categories, sel_cities, sel_payments, sel_products)
    kpi_a = compute_kpis(df_a)
    kpi_b = compute_kpis(df_b)

    def compare_row(label: str, a_val: float, b_val: float, money: bool = False) -> dict:
        diff = a_val - b_val
        pct = safe_pct_change(a_val, b_val)
        if money:
            a_txt, b_txt, diff_txt = full_money(a_val), full_money(b_val), signed_money(diff)
        else:
            a_txt, b_txt, diff_txt = f"{a_val:,.0f}", f"{b_val:,.0f}", f"{diff:+,.0f}"
        if b_val == 0 and a_val != 0:
            pct_txt = "n/a (Range B is 0)"
        else:
            pct_txt = signed_pct(pct)
        return {
            "Metric": label,
            "Range A": a_txt,
            "Range B": b_txt,
            "Difference (A − B)": diff_txt,
            "% change vs B": pct_txt,
        }

    compare_df = pd.DataFrame([
        compare_row("Revenue", kpi_a["revenue"], kpi_b["revenue"], money=True),
        compare_row("Unique orders", kpi_a["orders"], kpi_b["orders"]),
        compare_row("Quantity sold", kpi_a["quantity"], kpi_b["quantity"]),
        compare_row("Average order value", kpi_a["aov"], kpi_b["aov"], money=True),
    ])
    st.dataframe(compare_df, hide_index=True, width="stretch")

    if df_a.empty:
        st.info("Range A has no matching orders.")
    if df_b.empty:
        st.info("Range B has no matching orders.")

    m_a = monthly_summary(df_a)
    m_b = monthly_summary(df_b)
    if not m_a.empty or not m_b.empty:
        peak_a = float(m_a["Revenue"].max()) if not m_a.empty else 0.0
        peak_b = float(m_b["Revenue"].max()) if not m_b.empty else 0.0
        div, unit = pick_unit(max(peak_a, peak_b))
        fig = go.Figure()
        if not m_a.empty:
            fig.add_trace(go.Scatter(
                x=m_a["Month"], y=m_a["Revenue"] / div, mode="lines+markers", name="Range A",
                line=dict(color=PRIMARY, width=3),
                customdata=m_a["Revenue"].map(full_money),
                hovertemplate="Range A · %{x|%b %Y}<br>%{customdata}<extra></extra>",
            ))
        if not m_b.empty:
            fig.add_trace(go.Scatter(
                x=m_b["Month"], y=m_b["Revenue"] / div, mode="lines+markers", name="Range B",
                line=dict(color=ACCENT, width=3),
                customdata=m_b["Revenue"].map(full_money),
                hovertemplate="Range B · %{x|%b %Y}<br>%{customdata}<extra></extra>",
            ))
        fig.update_yaxes(title=axis_title("Revenue", unit), rangemode="tozero")
        fig.update_xaxes(tickformat="%b %Y", title="")
        show(style(fig, "Monthly revenue — Range A vs Range B", theme=THEME), "compare_trend")

    st.download_button(
        "Download comparison table (CSV)",
        data=compare_df.to_csv(index=False).encode("utf-8"),
        file_name="date_range_comparison.csv",
        mime="text/csv",
        key="dl_compare",
    )

# ----------------------------------------------------------------------------
# 12. INSIGHTS, DOWNLOADS, DEFINITIONS, DATA QUALITY
# ----------------------------------------------------------------------------
with tab_insights:
    st.subheader("Business insights")
    st.caption(
        "These notes are calculated in Python from the currently filtered data. "
        "They are not a forecast and do not use an external AI API."
    )
    observed, recommendations = build_insights(filtered, monthly_summary(filtered))

    st.markdown('<div class="insight-box"><div class="insight-title">Observed from the data</div>', unsafe_allow_html=True)
    for line in observed:
        st.markdown(f"- {line}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="reco-box"><div class="insight-title">Recommendations (interpret with care)</div>',
        unsafe_allow_html=True,
    )
    st.caption("Recommendations are suggested next checks, not proven actions or guaranteed results.")
    for line in recommendations:
        st.markdown(f"- {line}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    st.subheader("Downloads")
    summary_report = build_summary_report(filtered, k, start_date, end_date)
    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "Download filtered data (CSV)",
            data=filtered.drop(columns=["Month"]).to_csv(index=False).encode("utf-8"),
            file_name="filtered_sales.csv",
            mime="text/csv",
            key="dl_filtered",
        )
    with dl2:
        st.download_button(
            "Download summary report (CSV)",
            data=summary_report.to_csv(index=False).encode("utf-8"),
            file_name="sales_summary_report.csv",
            mime="text/csv",
            key="dl_summary",
        )

    st.divider()
    with st.expander("KPI definitions"):
        st.markdown(
            """
- **Total Revenue** = sum of `Total_Sales` for the filtered rows.
- **Total Orders** = number of **unique** `Order_ID` values (an order is never counted twice, even if it spans several rows).
- **Total Quantity Sold** = sum of `Quantity`.
- **Average Order Value (AOV)** = Total Revenue ÷ Total Orders.
- **Revenue change** = current filtered dates versus the previous window of the same length, using the same category / city / product / payment filters.
- **Revenue Share** = a product's revenue ÷ revenue of all products in the current filter.
- All values come from your CSV and respond to every filter. Currency symbol and Lakh/Crore style can be changed at the top of `app.py`.
            """
        )

    with st.expander("Data quality report (what was checked / fixed on load)"):
        st.markdown(
            f"""
| Check | Result |
|---|---|
| Rows loaded from CSV | {report['rows_loaded']:,} |
| Exact duplicate rows removed | {report['duplicate_rows_removed']:,} |
| Rows dropped (invalid date / missing Order_ID, Quantity or Total_Sales / non-positive Quantity / negative sales) | {report['unusable_rows_dropped']:,} |
| Missing Total_Sales recalculated as Price × Quantity | {report['total_sales_recalculated']:,} |
| Missing text labels replaced with "Unknown" | {report['unknown_labels_filled']:,} |
| Rows where Total_Sales ≠ Price × Quantity (checked only, not changed) | {report['total_sales_mismatch']:,} |
| Repeated Order_ID values (counted once in Total Orders) | {report['duplicate_order_ids']:,} |
| **Rows used in the dashboard** | **{report['rows_final']:,}** |
            """
        )
        if csv_path is not None:
            st.caption(f"Loaded file: `{csv_path}`")
