# -*- coding: utf-8 -*-
"""
NESO Wind Forecast Revision Monitor
Distinct light editorial / forecast-desk redesign.

Data source: NESO open data portal
Database: Supabase PostgreSQL
Dashboard: Streamlit
"""

import os
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st


# ---------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="NESO Wind Forecast Revision Monitor",
    page_icon="🌬️",
    layout="wide",
    initial_sidebar_state="expanded",
)

LONDON_TZ = ZoneInfo("Europe/London")

INK = "#24343B"
MUTED = "#6C7C80"
SEA = "#2E8B88"
SEA_DARK = "#1E6665"
SEA_LIGHT = "#DFF1EE"
SKY = "#77AFC4"
SAND = "#E9D8B4"
AMBER = "#C9862A"
CORAL = "#C85D4B"
GREEN = "#4F8C72"
PAPER = "#FAF9F5"
WHITE = "#FFFFFF"
LINE = "#DCE2DF"
SOFT = "#F1F4F1"
SLATE = "#91A0A3"

PLOT_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "autoScale2d",
    ],
}


# ---------------------------------------------------------------------
# Styling — intentionally different from later corporate dashboards
# ---------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    .stApp {{
        background: {PAPER};
        color: {INK};
    }}

    .block-container {{
        max-width: 1460px;
        padding-top: 1.15rem;
        padding-bottom: 3rem;
    }}

    header[data-testid="stHeader"] {{
        background: rgba(250,249,245,.94);
    }}

    #MainMenu, footer {{
        visibility: hidden;
    }}

    div[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #F3F8F7 0%, #F7F4EC 100%);
        border-right: 1px solid {LINE};
    }}

    div[data-testid="stMetric"] {{
        background: linear-gradient(135deg, #FFFFFF 0%, #EEF8F6 100%);
        border: 1px solid #D7E8E4;
        border-left: 4px solid {SEA};
        border-radius: 12px;
        padding: 12px 14px 11px 14px;
        min-height: 95px;
        box-shadow: 0 4px 14px rgba(36,52,59,.05);
    }}

    div[data-testid="stMetricLabel"] {{
        color: {MUTED};
        font-size: .78rem;
        letter-spacing: .04em;
        text-transform: uppercase;
    }}

    div[data-testid="stMetricValue"] {{
        color: {INK};
        font-size: 1.55rem;
        font-weight: 650;
    }}

    div[data-testid="stMetricDelta"] {{
        font-size: .78rem;
    }}

    div[data-testid="stDataFrame"] {{
        border: 1px solid {LINE};
        border-radius: 4px;
        overflow: hidden;
        background: {WHITE};
    }}

    div[data-testid="stExpander"] {{
        border: 1px solid {LINE};
        border-radius: 4px;
        background: {WHITE};
    }}

    div[data-testid="stTabs"] button {{
        color: {MUTED};
        font-weight: 600;
    }}

    div[data-testid="stTabs"] button[aria-selected="true"] {{
        color: {SEA_DARK};
        background: {SEA_LIGHT};
        border-radius: 8px 8px 0 0;
    }}

    .masthead {{
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 28px;
        align-items: end;
        border-top: 5px solid {SEA_DARK};
        border-bottom: 1px solid {LINE};
        padding: 18px 0 20px 0;
        margin-bottom: 18px;
    }}

    .eyebrow {{
        font-size: .70rem;
        font-weight: 750;
        letter-spacing: .16em;
        text-transform: uppercase;
        color: {SEA_DARK};
        margin-bottom: 8px;
    }}

    .masthead-title {{
        font-family: Georgia, "Times New Roman", serif;
        font-size: clamp(2rem, 3vw, 3.05rem);
        line-height: 1.04;
        color: {INK};
        margin: 0;
        font-weight: 500;
    }}

    .masthead-copy {{
        margin-top: 10px;
        max-width: 900px;
        color: {MUTED};
        font-size: .95rem;
        line-height: 1.55;
    }}

    .archive-stamp {{
        min-width: 215px;
        padding: 12px 14px;
        border-left: 1px solid {LINE};
    }}

    .stamp-label {{
        font-size: .68rem;
        text-transform: uppercase;
        letter-spacing: .10em;
        color: {MUTED};
        font-weight: 700;
    }}

    .stamp-value {{
        font-family: Georgia, "Times New Roman", serif;
        font-size: 1.1rem;
        color: {INK};
        margin-top: 4px;
    }}

    .stamp-sub {{
        font-size: .76rem;
        color: {MUTED};
        margin-top: 3px;
    }}

    .forecast-note {{
        background: {SEA_LIGHT};
        border-left: 4px solid {SEA};
        padding: 11px 14px;
        color: #355F5D;
        font-size: .86rem;
        line-height: 1.5;
        margin: 4px 0 22px 0;
    }}

    .section {{
        margin-top: 11px;
        margin-bottom: 12px;
    }}

    .section-label {{
        font-size: .69rem;
        font-weight: 760;
        text-transform: uppercase;
        letter-spacing: .13em;
        color: {SEA_DARK};
        margin-bottom: 4px;
    }}

    .section-title {{
        font-family: Georgia, "Times New Roman", serif;
        color: {INK};
        font-size: 1.55rem;
        line-height: 1.2;
        margin: 0 0 4px 0;
        font-weight: 500;
    }}

    .section-copy {{
        color: {MUTED};
        font-size: .87rem;
        line-height: 1.5;
        max-width: 930px;
    }}

    .desk-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 1px;
        background: {LINE};
        border: 1px solid {LINE};
        margin: 8px 0 18px 0;
    }}

    .desk-cell {{
        background: {WHITE};
        padding: 15px 16px;
        min-height: 108px;
    }}

    .desk-cell-label {{
        color: {MUTED};
        font-size: .67rem;
        text-transform: uppercase;
        letter-spacing: .08em;
        font-weight: 730;
    }}

    .desk-cell-value {{
        font-family: Georgia, "Times New Roman", serif;
        color: {INK};
        font-size: 1.22rem;
        margin-top: 5px;
    }}

    .desk-cell-copy {{
        color: {MUTED};
        font-size: .78rem;
        line-height: 1.42;
        margin-top: 5px;
    }}

    .status-strip {{
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        border-top: 1px solid {LINE};
        border-bottom: 1px solid {LINE};
        color: {INK};
        font-size: .84rem;
        margin-bottom: 17px;
    }}

    .status-mark {{
        width: 9px;
        height: 9px;
        border-radius: 50%;
        display: inline-block;
    }}

    .status-good {{
        background: {GREEN};
    }}

    .status-watch {{
        background: {AMBER};
    }}

    .status-critical {{
        background: {CORAL};
    }}

    .sidebar-brand {{
        padding: 4px 0 14px 0;
        border-bottom: 1px solid {LINE};
        margin-bottom: 14px;
    }}

    .sidebar-brand-title {{
        font-family: Georgia, "Times New Roman", serif;
        font-size: 1.16rem;
        color: {INK};
    }}

    .sidebar-brand-copy {{
        color: {MUTED};
        font-size: .76rem;
        line-height: 1.45;
        margin-top: 5px;
    }}

    .sidebar-stat {{
        border-bottom: 1px solid {LINE};
        padding: 8px 0;
    }}

    .sidebar-stat-label {{
        font-size: .66rem;
        text-transform: uppercase;
        letter-spacing: .07em;
        color: {MUTED};
        font-weight: 720;
    }}

    .sidebar-stat-value {{
        margin-top: 3px;
        color: {INK};
        font-size: .89rem;
        font-weight: 610;
    }}

    .method-list {{
        border-top: 1px solid {LINE};
        margin-top: 9px;
    }}

    .method-row {{
        display: grid;
        grid-template-columns: 54px 1fr;
        border-bottom: 1px solid {LINE};
        padding: 14px 0;
        gap: 12px;
    }}

    .method-number {{
        font-family: Georgia, "Times New Roman", serif;
        color: {SEA_DARK};
        font-size: 1.2rem;
    }}

    .method-title {{
        color: {INK};
        font-weight: 650;
        font-size: .90rem;
        margin-bottom: 3px;
    }}

    .method-copy {{
        color: {MUTED};
        font-size: .82rem;
        line-height: 1.48;
    }}

    .footer-note {{
        margin-top: 28px;
        border-top: 1px solid {LINE};
        padding-top: 13px;
        color: {MUTED};
        font-size: .76rem;
        line-height: 1.5;
    }}

    @media (max-width: 860px) {{
        .masthead {{
            grid-template-columns: 1fr;
        }}
        .archive-stamp {{
            border-left: 0;
            border-top: 1px solid {LINE};
            padding-left: 0;
        }}
        .desk-grid {{
            grid-template-columns: 1fr;
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def get_database_url():
    if "DATABASE_URL" in st.secrets:
        return st.secrets["DATABASE_URL"]

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    raise RuntimeError(
        "DATABASE_URL is missing. Add it to Streamlit secrets or your environment variables."
    )


def format_dt(value, fmt="%d %b %Y %H:%M"):
    if pd.isna(value):
        return "N/A"

    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")

    return ts.tz_convert(LONDON_TZ).strftime(fmt)


def classify_revision(abs_revision, watchlist_threshold, critical_threshold):
    if abs_revision >= critical_threshold:
        return "Critical revision"
    if abs_revision >= 1000:
        return "Major revision"
    if abs_revision >= 500:
        return "Significant revision"
    if abs_revision >= watchlist_threshold:
        return "Watchlist revision"
    if abs_revision >= 50:
        return "Minor revision"
    return "Normal movement"


def section_header(label, title, copy):
    st.markdown(
        f"""
        <div class="section">
            <div class="section-label">{label}</div>
            <div class="section-title">{title}</div>
            <div class="section-copy">{copy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_chart_style(fig, height=410, legend=True):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=12, r=12, t=24, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=WHITE,
        font=dict(
            family="Arial, sans-serif",
            size=12,
            color=INK,
        ),
        showlegend=legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=11),
        ),
        hoverlabel=dict(
            bgcolor=WHITE,
            bordercolor=LINE,
            font=dict(color=INK),
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=LINE,
        tickfont=dict(color=MUTED),
        title_font=dict(color=MUTED),
    )
    fig.update_yaxes(
        gridcolor="#E8ECE9",
        zerolinecolor=LINE,
        linecolor=LINE,
        tickfont=dict(color=MUTED),
        title_font=dict(color=MUTED),
    )
    return fig


@st.cache_data(ttl=300, show_spinner=False)
def load_forecast_history():
    database_url = get_database_url()

    query = """
    SELECT
        forecast_datetime,
        delivery_datetime,
        settlement_period,
        capacity_mw,
        wind_forecast_mw,
        collected_at
    FROM neso_wind_forecasts
    ORDER BY forecast_datetime, delivery_datetime
    """

    connection = psycopg2.connect(database_url)

    try:
        dataframe = pd.read_sql_query(query, connection)
    finally:
        connection.close()

    if dataframe.empty:
        return dataframe

    dataframe["forecast_datetime"] = pd.to_datetime(
        dataframe["forecast_datetime"],
        utc=True,
        errors="coerce",
    )
    dataframe["delivery_datetime"] = pd.to_datetime(
        dataframe["delivery_datetime"],
        utc=True,
        errors="coerce",
    )
    dataframe["collected_at"] = pd.to_datetime(
        dataframe["collected_at"],
        utc=True,
        errors="coerce",
    )

    dataframe["settlement_period"] = pd.to_numeric(
        dataframe["settlement_period"],
        errors="coerce",
    )
    dataframe["capacity_mw"] = pd.to_numeric(
        dataframe["capacity_mw"],
        errors="coerce",
    )
    dataframe["wind_forecast_mw"] = pd.to_numeric(
        dataframe["wind_forecast_mw"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=[
            "forecast_datetime",
            "delivery_datetime",
            "wind_forecast_mw",
        ]
    ).copy()

    return dataframe.sort_values(
        ["forecast_datetime", "delivery_datetime"]
    ).reset_index(drop=True)


def build_run_summary(history_df):
    summary = (
        history_df.groupby(
            "forecast_datetime",
            as_index=False,
        )
        .agg(
            delivery_start=("delivery_datetime", "min"),
            delivery_end=("delivery_datetime", "max"),
            periods=("delivery_datetime", "count"),
            peak_forecast_mw=("wind_forecast_mw", "max"),
            average_forecast_mw=("wind_forecast_mw", "mean"),
            average_capacity_mw=("capacity_mw", "mean"),
        )
        .sort_values(
            "forecast_datetime",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    summary["average_capacity_factor_pct"] = (
        summary["average_forecast_mw"]
        / summary["average_capacity_mw"].replace(0, pd.NA)
        * 100
    ).round(1)

    return summary


def build_comparison(previous_df, latest_df):
    previous = previous_df[
        ["delivery_datetime", "wind_forecast_mw"]
    ].rename(
        columns={
            "wind_forecast_mw": "previous_forecast_mw"
        }
    )

    latest = latest_df[
        ["delivery_datetime", "wind_forecast_mw"]
    ].rename(
        columns={
            "wind_forecast_mw": "latest_forecast_mw"
        }
    )

    comparison = pd.merge(
        previous,
        latest,
        on="delivery_datetime",
        how="inner",
    )

    comparison["revision_mw"] = (
        comparison["latest_forecast_mw"]
        - comparison["previous_forecast_mw"]
    )
    comparison["absolute_revision_mw"] = (
        comparison["revision_mw"].abs()
    )

    return comparison.sort_values(
        "delivery_datetime"
    ).reset_index(drop=True)


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------
st.sidebar.markdown(
    """
    <div class="sidebar-brand">
        <div class="sidebar-brand-title">Forecast controls</div>
        <div class="sidebar-brand-copy">
            Adjust the forward viewing window and the revision thresholds
            used to flag notable changes between forecast runs.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

forecast_horizon_days = st.sidebar.select_slider(
    "Forward horizon",
    options=list(range(1, 15)),
    value=7,
    format_func=lambda x: f"{x} day{'s' if x != 1 else ''}",
)

watchlist_threshold = st.sidebar.number_input(
    "Watchlist threshold (MW)",
    min_value=0,
    max_value=5000,
    value=250,
    step=50,
)

critical_threshold = st.sidebar.number_input(
    "Critical threshold (MW)",
    min_value=0,
    max_value=10000,
    value=3000,
    step=100,
)

if critical_threshold < watchlist_threshold:
    st.sidebar.warning(
        "Critical threshold is currently below the watchlist threshold."
    )

if st.sidebar.button(
    "Refresh archive",
    use_container_width=True,
):
    st.cache_data.clear()
    st.rerun()


# ---------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------
try:
    history = load_forecast_history()
except Exception as error:
    st.error("Database connection failed.")
    st.code(str(error))
    st.stop()

if history.empty:
    st.warning("No forecast records were found in the database.")
    st.stop()


# ---------------------------------------------------------------------
# Prepare
# ---------------------------------------------------------------------
run_summary = build_run_summary(history)

distinct_runs = (
    history["forecast_datetime"]
    .drop_duplicates()
    .sort_values()
    .tolist()
)

latest_run_time = distinct_runs[-1]
latest_df = history[
    history["forecast_datetime"] == latest_run_time
].copy()

# Choose the most recent earlier forecast run that actually overlaps
# the newest run on delivery_datetime. This keeps the dashboard
# comparing the newest publication with the last genuinely comparable run,
# even if an incomplete/duplicate archive run has been stored in between.
previous_run_time = None
previous_df = pd.DataFrame()
latest_delivery_times = set(
    latest_df["delivery_datetime"].dropna().tolist()
)

for candidate_run_time in reversed(distinct_runs[:-1]):
    candidate_df = history[
        history["forecast_datetime"] == candidate_run_time
    ].copy()

    candidate_delivery_times = set(
        candidate_df["delivery_datetime"].dropna().tolist()
    )

    if latest_delivery_times.intersection(candidate_delivery_times):
        previous_run_time = candidate_run_time
        previous_df = candidate_df
        break

latest_delivery_start = latest_df[
    "delivery_datetime"
].min()

latest_delivery_end = latest_df[
    "delivery_datetime"
].max()

display_end = (
    latest_delivery_start
    + pd.Timedelta(days=forecast_horizon_days)
)

latest_display_df = latest_df[
    (latest_df["delivery_datetime"] >= latest_delivery_start)
    & (latest_df["delivery_datetime"] < display_end)
].copy()

if latest_display_df.empty:
    latest_display_df = latest_df.copy()

latest_peak_mw = latest_display_df[
    "wind_forecast_mw"
].max()

latest_average_mw = latest_display_df[
    "wind_forecast_mw"
].mean()

latest_average_capacity = latest_display_df[
    "capacity_mw"
].mean()

latest_capacity_factor = (
    latest_average_mw / latest_average_capacity * 100
    if pd.notna(latest_average_capacity)
    and latest_average_capacity != 0
    else 0
)

latest_collection_time = (
    history["collected_at"].max()
    if "collected_at" in history.columns
    else pd.NaT
)

comparison = pd.DataFrame()

if previous_run_time is not None and not previous_df.empty:
    comparison = build_comparison(
        previous_df,
        latest_df,
    )

    comparison = comparison[
        (comparison["delivery_datetime"] >= latest_delivery_start)
        & (comparison["delivery_datetime"] < display_end)
    ].copy()

    if not comparison.empty:
        comparison["revision_class"] = comparison[
            "absolute_revision_mw"
        ].apply(
            lambda x: classify_revision(
                x,
                watchlist_threshold,
                critical_threshold,
            )
        )


# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------
st.markdown(
    f"""
    <div class="masthead">
        <div>
            <div class="eyebrow">Renewable Forecast Desk · Great Britain</div>
            <div class="masthead-title">NESO Wind Forecast Revision Monitor</div>
            <div class="masthead-copy">
                An archived view of how published wind forecasts evolve between
                successive NESO runs — designed to make changing expectations,
                larger forecast swings and the forward wind outlook easy to inspect.
            </div>
        </div>
        <div class="archive-stamp">
            <div class="stamp-label">Latest forecast run</div>
            <div class="stamp-value">{format_dt(latest_run_time, "%d %b %Y")}</div>
            <div class="stamp-sub">{format_dt(latest_run_time, "%H:%M")} Europe/London</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="forecast-note">
        <strong>Forecast interpretation.</strong>
        “Forecast Published” is when NESO issued the forecast.
        “Delivery Datetime” is the future half-hourly period being forecast.
        Future values are therefore forecast wind generation, not measured output.
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# Sidebar archive facts
# ---------------------------------------------------------------------
st.sidebar.markdown("### Archive")

st.sidebar.markdown(
    f"""
    <div class="sidebar-stat">
        <div class="sidebar-stat-label">Stored runs</div>
        <div class="sidebar-stat-value">{run_summary.shape[0]:,}</div>
    </div>
    <div class="sidebar-stat">
        <div class="sidebar-stat-label">Stored rows</div>
        <div class="sidebar-stat-value">{history.shape[0]:,}</div>
    </div>
    <div class="sidebar-stat">
        <div class="sidebar-stat-label">Newest run</div>
        <div class="sidebar-stat-value">{format_dt(latest_run_time)}</div>
    </div>
    <div class="sidebar-stat">
        <div class="sidebar-stat-label">Last collected</div>
        <div class="sidebar-stat-value">{format_dt(latest_collection_time)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------
forecast_tab, revision_tab, archive_tab, method_tab = st.tabs(
    [
        "Forecast Desk",
        "Revision Review",
        "Archive",
        "About the Monitor",
    ]
)


# ---------------------------------------------------------------------
# Forecast Desk
# ---------------------------------------------------------------------
with forecast_tab:
    section_header(
        "LATEST OUTLOOK",
        "Wind forecast at a glance",
        (
            f"Latest NESO forecast over the selected "
            f"{forecast_horizon_days}-day viewing window."
        ),
    )

    k1, k2, k3, k4 = st.columns(4)

    k1.metric(
        "Published",
        format_dt(
            latest_run_time,
            "%d %b · %H:%M",
        ),
    )

    k2.metric(
        "Peak forecast",
        f"{latest_peak_mw:,.0f} MW",
    )

    k3.metric(
        "Average forecast",
        f"{latest_average_mw:,.0f} MW",
    )

    k4.metric(
        "Average capacity factor",
        f"{latest_capacity_factor:.1f}%",
    )

    st.caption(
        f"Delivery range shown: "
        f"{format_dt(latest_delivery_start)} → "
        f"{format_dt(min(display_end, latest_delivery_end))}"
    )

    section_header(
        "FORECAST CURVE",
        "Expected wind generation through the horizon",
        (
            "The newest forecast is compared directly with the last comparable "
            "published run. Reported available capacity is also shown where available."
        ),
    )

    forecast_fig = go.Figure()

    if previous_run_time is not None and not comparison.empty:
        forecast_fig.add_trace(
            go.Scatter(
                x=comparison["delivery_datetime"],
                y=comparison["previous_forecast_mw"],
                mode="lines",
                name=f"Previous run · {format_dt(previous_run_time, '%d %b %H:%M')}",
                line=dict(
                    width=2.2,
                    color=AMBER,
                    dash="dash",
                ),
                hovertemplate=(
                    "<b>%{x|%d %b %Y %H:%M}</b><br>"
                    "Previous %{y:,.0f} MW"
                    "<extra></extra>"
                ),
            )
        )

    forecast_fig.add_trace(
        go.Scatter(
            x=latest_display_df["delivery_datetime"],
            y=latest_display_df["wind_forecast_mw"],
            mode="lines",
            name=f"Latest run · {format_dt(latest_run_time, '%d %b %H:%M')}",
            line=dict(
                width=3.2,
                color=SEA_DARK,
            ),
            fill="tozeroy",
            fillcolor="rgba(46,139,136,.10)",
            hovertemplate=(
                "<b>%{x|%d %b %Y %H:%M}</b><br>"
                "Latest %{y:,.0f} MW"
                "<extra></extra>"
            ),
        )
    )

    if latest_display_df["capacity_mw"].notna().any():
        forecast_fig.add_trace(
            go.Scatter(
                x=latest_display_df["delivery_datetime"],
                y=latest_display_df["capacity_mw"],
                mode="lines",
                name="Available capacity",
                line=dict(
                    width=1.8,
                    color=SKY,
                    dash="dot",
                ),
            )
        )

    forecast_fig = apply_chart_style(
        forecast_fig,
        height=450,
    )

    forecast_fig.update_xaxes(
        title="Delivery time"
    )
    forecast_fig.update_yaxes(
        title="MW"
    )

    st.plotly_chart(
        forecast_fig,
        use_container_width=True,
        config=PLOT_CONFIG,
    )

    if previous_run_time is not None and not comparison.empty:
        largest_revision = comparison[
            "absolute_revision_mw"
        ].max()

        average_revision = comparison[
            "revision_mw"
        ].mean()

        watch_count = (
            comparison["absolute_revision_mw"]
            >= watchlist_threshold
        ).sum()

        critical_count = (
            comparison["absolute_revision_mw"]
            >= critical_threshold
        ).sum()

        largest_row = comparison.loc[
            comparison["absolute_revision_mw"].idxmax()
        ]

        if largest_revision >= critical_threshold:
            status_class = "status-critical"
            status_text = "Critical-size revision present"
        elif largest_revision >= watchlist_threshold:
            status_class = "status-watch"
            status_text = "Revision watch active"
        else:
            status_class = "status-good"
            status_text = "Revision profile within watch threshold"

        st.markdown(
            f"""
            <div class="status-strip">
                <span class="status-mark {status_class}"></span>
                <strong>{status_text}</strong>
                <span>· Latest run compared with {format_dt(previous_run_time)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        direction = (
            "higher"
            if average_revision > 0
            else "lower"
            if average_revision < 0
            else "unchanged"
        )

        st.markdown(
            f"""
            <div class="desk-grid">
                <div class="desk-cell">
                    <div class="desk-cell-label">Largest change</div>
                    <div class="desk-cell-value">{largest_revision:,.0f} MW</div>
                    <div class="desk-cell-copy">
                        Largest absolute shift occurs around
                        {format_dt(largest_row["delivery_datetime"])}.
                    </div>
                </div>
                <div class="desk-cell">
                    <div class="desk-cell-label">Average direction</div>
                    <div class="desk-cell-value">{average_revision:+,.0f} MW</div>
                    <div class="desk-cell-copy">
                        The newest run is {direction} on average across comparable periods.
                    </div>
                </div>
                <div class="desk-cell">
                    <div class="desk-cell-label">Threshold review</div>
                    <div class="desk-cell-value">{watch_count:,} watch · {critical_count:,} critical</div>
                    <div class="desk-cell-copy">
                        Counts use the thresholds currently selected in the sidebar.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------
# Revision Review
# ---------------------------------------------------------------------
with revision_tab:
    if previous_run_time is None or comparison.empty:
        st.info(
            "At least two overlapping forecast runs are needed for revision analysis."
        )
    else:
        section_header(
            "RUN-TO-RUN CHANGE",
            "How the newest forecast differs from the previous run",
            (
                f"Latest run: {format_dt(latest_run_time)} · "
                f"Previous run: {format_dt(previous_run_time)}"
            ),
        )

        comparison_fig = go.Figure()

        comparison_fig.add_trace(
            go.Scatter(
                x=comparison["delivery_datetime"],
                y=comparison["previous_forecast_mw"],
                mode="lines",
                name=f"Previous · {format_dt(previous_run_time, '%d %b %H:%M')}",
                line=dict(
                    width=2.4,
                    color=AMBER,
                    dash="dash",
                ),
            )
        )

        comparison_fig.add_trace(
            go.Scatter(
                x=comparison["delivery_datetime"],
                y=comparison["latest_forecast_mw"],
                mode="lines",
                name=f"Latest · {format_dt(latest_run_time, '%d %b %H:%M')}",
                line=dict(
                    width=3.2,
                    color=SEA_DARK,
                ),
            )
        )

        comparison_fig = apply_chart_style(
            comparison_fig,
            height=410,
        )
        comparison_fig.update_xaxes(
            title="Delivery time"
        )
        comparison_fig.update_yaxes(
            title="Wind forecast (MW)"
        )

        st.plotly_chart(
            comparison_fig,
            use_container_width=True,
            config=PLOT_CONFIG,
        )

        section_header(
            "REVISION PROFILE",
            "Magnitude and direction of the change",
            (
                "Bars above zero are upward revisions; bars below zero are downward revisions."
            ),
        )

        revision_colours = [
            GREEN if value >= 0 else CORAL
            for value in comparison["revision_mw"]
        ]

        revision_fig = go.Figure()

        revision_fig.add_trace(
            go.Bar(
                x=comparison["delivery_datetime"],
                y=comparison["revision_mw"],
                marker_color=revision_colours,
                name="Revision",
                customdata=comparison[
                    [
                        "previous_forecast_mw",
                        "latest_forecast_mw",
                        "absolute_revision_mw",
                        "revision_class",
                    ]
                ],
                hovertemplate=(
                    "<b>%{x|%d %b %Y %H:%M}</b><br>"
                    "Revision %{y:+,.0f} MW<br>"
                    "Previous %{customdata[0]:,.0f} MW<br>"
                    "Latest %{customdata[1]:,.0f} MW<br>"
                    "%{customdata[3]}"
                    "<extra></extra>"
                ),
            )
        )

        revision_fig.add_hline(
            y=watchlist_threshold,
            line_dash="dash",
            line_color=AMBER,
            annotation_text=f"Watch {watchlist_threshold:,} MW",
        )
        revision_fig.add_hline(
            y=-watchlist_threshold,
            line_dash="dash",
            line_color=AMBER,
        )

        revision_fig.add_hline(
            y=critical_threshold,
            line_dash="dot",
            line_color=CORAL,
            annotation_text=f"Critical {critical_threshold:,} MW",
        )
        revision_fig.add_hline(
            y=-critical_threshold,
            line_dash="dot",
            line_color=CORAL,
        )

        revision_fig = apply_chart_style(
            revision_fig,
            height=415,
            legend=False,
        )

        revision_fig.update_xaxes(
            title="Delivery time"
        )
        revision_fig.update_yaxes(
            title="Revision (MW)"
        )

        st.plotly_chart(
            revision_fig,
            use_container_width=True,
            config=PLOT_CONFIG,
        )

        left, right = st.columns([1, 1])

        with left:
            section_header(
                "CLASSIFICATION",
                "Revision mix",
                "Number of delivery periods in each revision class.",
            )

            class_summary = (
                comparison.groupby(
                    "revision_class",
                    as_index=False,
                )
                .agg(
                    periods=("delivery_datetime", "count"),
                    average_absolute_revision_mw=(
                        "absolute_revision_mw",
                        "mean",
                    ),
                    maximum_absolute_revision_mw=(
                        "absolute_revision_mw",
                        "max",
                    ),
                )
                .sort_values(
                    "periods",
                    ascending=True,
                )
            )

            class_fig = px.bar(
                class_summary,
                x="periods",
                y="revision_class",
                orientation="h",
                text="periods",
            )
            class_fig.update_traces(
                marker_color=SKY,
            )
            class_fig = apply_chart_style(
                class_fig,
                height=330,
                legend=False,
            )
            class_fig.update_xaxes(
                title="Periods"
            )
            class_fig.update_yaxes(
                title=None
            )

            st.plotly_chart(
                class_fig,
                use_container_width=True,
                config=PLOT_CONFIG,
            )

        with right:
            section_header(
                "WATCHLIST",
                "Periods requiring closer inspection",
                (
                    f"Absolute revision at or above "
                    f"{watchlist_threshold:,} MW."
                ),
            )

            watchlist_df = comparison[
                comparison["absolute_revision_mw"]
                >= watchlist_threshold
            ].copy()

            if watchlist_df.empty:
                st.success(
                    "No periods currently exceed the watchlist threshold."
                )
            else:
                watchlist_df = watchlist_df[
                    [
                        "delivery_datetime",
                        "previous_forecast_mw",
                        "latest_forecast_mw",
                        "revision_mw",
                        "absolute_revision_mw",
                        "revision_class",
                    ]
                ].copy()

                watchlist_df["delivery_datetime"] = (
                    watchlist_df["delivery_datetime"]
                    .dt.tz_convert(LONDON_TZ)
                    .dt.strftime("%d %b %Y %H:%M")
                )

                watchlist_df = watchlist_df.rename(
                    columns={
                        "delivery_datetime": "Delivery",
                        "previous_forecast_mw": "Previous MW",
                        "latest_forecast_mw": "Latest MW",
                        "revision_mw": "Revision MW",
                        "absolute_revision_mw": "Absolute MW",
                        "revision_class": "Class",
                    }
                ).round(1)

                st.dataframe(
                    watchlist_df,
                    use_container_width=True,
                    hide_index=True,
                )

        critical_df = comparison[
            comparison["absolute_revision_mw"]
            >= critical_threshold
        ].copy()

        if not critical_df.empty:
            with st.expander(
                f"Critical revisions ({len(critical_df):,})",
                expanded=False,
            ):
                critical_display = critical_df[
                    [
                        "delivery_datetime",
                        "previous_forecast_mw",
                        "latest_forecast_mw",
                        "revision_mw",
                        "absolute_revision_mw",
                        "revision_class",
                    ]
                ].copy()

                critical_display[
                    "delivery_datetime"
                ] = (
                    critical_display["delivery_datetime"]
                    .dt.tz_convert(LONDON_TZ)
                    .dt.strftime("%d %b %Y %H:%M")
                )

                st.dataframe(
                    critical_display.round(1),
                    use_container_width=True,
                    hide_index=True,
                )


# ---------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------
with archive_tab:
    section_header(
        "ARCHIVE",
        "Published forecast history",
        (
            "Earlier runs are retained rather than overwritten so that "
            "forecast evolution can be reconstructed."
        ),
    )

    a1, a2, a3 = st.columns(3)

    a1.metric(
        "Forecast runs",
        f"{run_summary.shape[0]:,}",
    )
    a2.metric(
        "Forecast rows",
        f"{history.shape[0]:,}",
    )

    archive_span = (
        (
            run_summary["forecast_datetime"].max()
            - run_summary["forecast_datetime"].min()
        ).total_seconds()
        / 86400
        if len(run_summary) > 1
        else 0
    )

    a3.metric(
        "Archive span",
        f"{archive_span:.1f} days",
    )

    if len(run_summary) > 1:
        run_history = run_summary.sort_values(
            "forecast_datetime"
        )

        archive_fig = go.Figure()

        archive_fig.add_trace(
            go.Scatter(
                x=run_history["forecast_datetime"],
                y=run_history["peak_forecast_mw"],
                mode="lines+markers",
                name="Peak forecast",
                line=dict(
                    color=SEA,
                    width=2.5,
                ),
                marker=dict(size=5),
            )
        )

        archive_fig.add_trace(
            go.Scatter(
                x=run_history["forecast_datetime"],
                y=run_history["average_forecast_mw"],
                mode="lines+markers",
                name="Average forecast",
                line=dict(
                    color=AMBER,
                    width=2,
                ),
                marker=dict(size=4),
            )
        )

        archive_fig = apply_chart_style(
            archive_fig,
            height=340,
        )
        archive_fig.update_xaxes(
            title="Forecast publication time"
        )
        archive_fig.update_yaxes(
            title="MW"
        )

        st.plotly_chart(
            archive_fig,
            use_container_width=True,
            config=PLOT_CONFIG,
        )

    archive_display = run_summary.copy()

    for column in [
        "forecast_datetime",
        "delivery_start",
        "delivery_end",
    ]:
        archive_display[column] = archive_display[
            column
        ].apply(
            lambda x: format_dt(
                x,
                "%d %b %Y %H:%M",
            )
        )

    archive_display = archive_display.rename(
        columns={
            "forecast_datetime": "Forecast published",
            "delivery_start": "Delivery start",
            "delivery_end": "Delivery end",
            "periods": "Rows",
            "peak_forecast_mw": "Peak forecast (MW)",
            "average_forecast_mw": "Average forecast (MW)",
            "average_capacity_mw": "Average capacity (MW)",
            "average_capacity_factor_pct": "Average capacity factor (%)",
        }
    ).round(1)

    st.dataframe(
        archive_display,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Download archive summary",
        data=archive_display.to_csv(
            index=False
        ).encode("utf-8"),
        file_name="neso_wind_forecast_archive.csv",
        mime="text/csv",
    )

    with st.expander(
        "Latest forecast source records"
    ):
        latest_raw = latest_display_df.copy()

        latest_raw["forecast_datetime"] = (
            latest_raw["forecast_datetime"]
            .dt.tz_convert(LONDON_TZ)
            .dt.strftime("%d %b %Y %H:%M")
        )
        latest_raw["delivery_datetime"] = (
            latest_raw["delivery_datetime"]
            .dt.tz_convert(LONDON_TZ)
            .dt.strftime("%d %b %Y %H:%M")
        )
        latest_raw["collected_at"] = (
            latest_raw["collected_at"]
            .dt.tz_convert(LONDON_TZ)
            .dt.strftime("%d %b %Y %H:%M")
        )

        latest_raw = latest_raw.rename(
            columns={
                "forecast_datetime": "Forecast published",
                "delivery_datetime": "Delivery time",
                "settlement_period": "Settlement period",
                "capacity_mw": "Capacity (MW)",
                "wind_forecast_mw": "Wind forecast (MW)",
                "collected_at": "Collected at",
            }
        )

        st.dataframe(
            latest_raw,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------------------
# About
# ---------------------------------------------------------------------
with method_tab:
    section_header(
        "ABOUT",
        "How the monitor works",
        (
            "This is a forecast-revision monitoring application, not an "
            "official NESO operational or dispatch tool."
        ),
    )

    st.markdown(
        f"""
        <div class="method-list">
            <div class="method-row">
                <div class="method-number">01</div>
                <div>
                    <div class="method-title">Archive each forecast run</div>
                    <div class="method-copy">
                        NESO forecast records are stored in Supabase PostgreSQL.
                        Older runs remain available rather than being overwritten.
                    </div>
                </div>
            </div>
            <div class="method-row">
                <div class="method-number">02</div>
                <div>
                    <div class="method-title">Match comparable delivery periods</div>
                    <div class="method-copy">
                        The latest and previous forecast runs are aligned by delivery
                        datetime so that the change for the same half-hourly period
                        can be measured consistently.
                    </div>
                </div>
            </div>
            <div class="method-row">
                <div class="method-number">03</div>
                <div>
                    <div class="method-title">Measure the revision</div>
                    <div class="method-copy">
                        Revision MW = latest forecast minus previous forecast.
                        Positive values indicate an upward revision and negative values
                        indicate a downward revision.
                    </div>
                </div>
            </div>
            <div class="method-row">
                <div class="method-number">04</div>
                <div>
                    <div class="method-title">Flag larger movements</div>
                    <div class="method-copy">
                        The current watchlist threshold is {watchlist_threshold:,} MW
                        and the current critical threshold is {critical_threshold:,} MW.
                        These are analytical thresholds chosen for this monitor, not
                        official NESO operating limits.
                    </div>
                </div>
            </div>
            <div class="method-row">
                <div class="method-number">05</div>
                <div>
                    <div class="method-title">Keep database use light</div>
                    <div class="method-copy">
                        Streamlit caches the archive query for five minutes. A manual
                        refresh clears the cache and reloads the stored forecast history.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="forecast-note">
            <strong>Scope:</strong>
            This application supports analytical monitoring, learning and portfolio
            demonstration. It does not replace official NESO operational systems or
            professional system-control judgement.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------
st.markdown(
    """
    <div class="footer-note">
        NESO Wind Forecast Revision Monitor ·
        NESO open data · Supabase PostgreSQL · Streamlit ·
        Developed by Kamil Ridwan Kehinde.
    </div>
    """,
    unsafe_allow_html=True,
)
