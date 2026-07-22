
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st


st.set_page_config(
    page_title="NESO Wind Forecast Revision Monitor",
    page_icon="🌬️",
    layout="wide"
)


def get_database_url():
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        database_url = os.environ.get("DATABASE_URL")

        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is missing. Add it in Streamlit secrets."
            )

        return database_url


def get_connection():
    return psycopg2.connect(get_database_url())


@st.cache_data(ttl=300)
def load_distinct_runs():
    query = """
    SELECT
        forecast_datetime,
        MIN(delivery_datetime) AS forecast_start,
        MAX(delivery_datetime) AS forecast_end,
        COUNT(*) AS records,
        MAX(wind_forecast_mw) AS peak_mw,
        AVG(wind_forecast_mw) AS average_mw,
        AVG(wind_forecast_mw / NULLIF(capacity_mw, 0) * 100) AS average_capacity_factor_pct
    FROM neso_wind_forecasts
    GROUP BY forecast_datetime
    ORDER BY forecast_datetime;
    """

    with get_connection() as connection:
        dataframe = pd.read_sql_query(
            query,
            connection,
            parse_dates=[
                "forecast_datetime",
                "forecast_start",
                "forecast_end"
            ]
        )

    return dataframe


@st.cache_data(ttl=300)
def load_forecast_run(forecast_datetime):
    query = """
    SELECT
        forecast_datetime,
        delivery_datetime,
        settlement_period,
        capacity_mw,
        wind_forecast_mw
    FROM neso_wind_forecasts
    WHERE forecast_datetime = %s
    ORDER BY delivery_datetime;
    """

    with get_connection() as connection:
        dataframe = pd.read_sql_query(
            query,
            connection,
            params=[forecast_datetime],
            parse_dates=[
                "forecast_datetime",
                "delivery_datetime"
            ]
        )

    dataframe["capacity_factor_pct"] = (
        dataframe["wind_forecast_mw"]
        / dataframe["capacity_mw"]
        * 100
    )

    return dataframe


def classify_revision(abs_revision_mw):
    if abs_revision_mw >= 3000:
        return "Critical swing"

    if abs_revision_mw >= 1000:
        return "Major revision"

    if abs_revision_mw >= 500:
        return "Significant revision"

    if abs_revision_mw >= 250:
        return "Moderate revision"

    if abs_revision_mw >= 100:
        return "Minor revision"

    return "Normal movement"


def build_comparison(
    previous_df,
    latest_df,
    watchlist_threshold_mw,
    critical_threshold_mw
):
    previous = previous_df[
        [
            "delivery_datetime",
            "wind_forecast_mw",
            "capacity_mw"
        ]
    ].rename(
        columns={
            "wind_forecast_mw": "previous_forecast_mw",
            "capacity_mw": "previous_capacity_mw"
        }
    )

    latest = latest_df[
        [
            "delivery_datetime",
            "wind_forecast_mw",
            "capacity_mw"
        ]
    ].rename(
        columns={
            "wind_forecast_mw": "latest_forecast_mw",
            "capacity_mw": "latest_capacity_mw"
        }
    )

    comparison_df = pd.merge(
        previous,
        latest,
        on="delivery_datetime",
        how="inner"
    )

    comparison_df = comparison_df.sort_values(
        "delivery_datetime"
    ).reset_index(drop=True)

    if comparison_df.empty:
        return comparison_df

    comparison_df["revision_mw"] = (
        comparison_df["latest_forecast_mw"]
        - comparison_df["previous_forecast_mw"]
    )

    comparison_df["absolute_revision_mw"] = comparison_df[
        "revision_mw"
    ].abs()

    comparison_df["revision_pct"] = (
        comparison_df["revision_mw"]
        / comparison_df["previous_forecast_mw"]
        * 100
    )

    comparison_df["revision_direction"] = "No change"

    comparison_df.loc[
        comparison_df["revision_mw"] > 0,
        "revision_direction"
    ] = "Upward revision"

    comparison_df.loc[
        comparison_df["revision_mw"] < 0,
        "revision_direction"
    ] = "Downward revision"

    comparison_df["revision_class"] = comparison_df[
        "absolute_revision_mw"
    ].apply(classify_revision)

    comparison_df["watchlist_alert"] = (
        comparison_df["absolute_revision_mw"]
        >= watchlist_threshold_mw
    )

    comparison_df["critical_alert"] = (
        comparison_df["absolute_revision_mw"]
        >= critical_threshold_mw
    )

    return comparison_df


def find_latest_comparable_pair(runs_df):
    if len(runs_df) < 2:
        return None

    run_times = list(runs_df["forecast_datetime"])

    for latest_index in range(len(run_times) - 1, 0, -1):
        latest_run_time = run_times[latest_index]
        previous_run_time = run_times[latest_index - 1]

        previous_df = load_forecast_run(previous_run_time)
        latest_df = load_forecast_run(latest_run_time)

        overlap = pd.merge(
            previous_df[["delivery_datetime"]],
            latest_df[["delivery_datetime"]],
            on="delivery_datetime",
            how="inner"
        )

        if len(overlap) > 0:
            return (
                previous_run_time,
                latest_run_time,
                previous_df,
                latest_df,
                len(overlap)
            )

    return None


def build_latest_forecast_chart(latest_run_df):
    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=latest_run_df["delivery_datetime"],
            y=latest_run_df["wind_forecast_mw"],
            mode="lines",
            name="Latest NESO forecast",
            hovertemplate=(
                "Future delivery time, %{x}<br>"
                "Forecasted wind generation, %{y:,.0f} MW"
                "<extra></extra>"
            )
        )
    )

    figure.update_layout(
        title="Latest NESO 14 Day Wind Forecast",
        xaxis_title="Future delivery time",
        yaxis_title="Forecasted wind generation, MW",
        hovermode="x unified",
        height=500
    )

    return figure


def build_comparison_chart(
    filtered_df,
    previous_run_time,
    latest_run_time,
    horizon_days
):
    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=filtered_df["delivery_datetime"],
            y=filtered_df["previous_forecast_mw"],
            mode="lines",
            name=f"Previous run, {previous_run_time.strftime('%d %b %H:%M')}",
            hovertemplate=(
                "Future delivery time, %{x}<br>"
                "Previous forecast, %{y:,.0f} MW"
                "<extra></extra>"
            )
        )
    )

    figure.add_trace(
        go.Scatter(
            x=filtered_df["delivery_datetime"],
            y=filtered_df["latest_forecast_mw"],
            mode="lines",
            name=f"Latest run, {latest_run_time.strftime('%d %b %H:%M')}",
            hovertemplate=(
                "Future delivery time, %{x}<br>"
                "Latest forecast, %{y:,.0f} MW"
                "<extra></extra>"
            )
        )
    )

    figure.update_layout(
        title=f"Run to Run Forecast Comparison, Next {horizon_days} Days",
        xaxis_title="Future delivery time",
        yaxis_title="Forecasted wind generation, MW",
        hovermode="x unified",
        height=600
    )

    return figure


def build_revision_chart(
    filtered_df,
    horizon_days,
    watchlist_threshold_mw,
    critical_threshold_mw
):
    figure = go.Figure()

    figure.add_trace(
        go.Bar(
            x=filtered_df["delivery_datetime"],
            y=filtered_df["revision_mw"],
            name="Forecast revision",
            customdata=filtered_df[
                [
                    "previous_forecast_mw",
                    "latest_forecast_mw",
                    "revision_pct",
                    "revision_class"
                ]
            ],
            hovertemplate=(
                "Future delivery time, %{x}<br>"
                "Revision, %{y:+,.0f} MW<br>"
                "Previous forecast, %{customdata[0]:,.0f} MW<br>"
                "Latest forecast, %{customdata[1]:,.0f} MW<br>"
                "Revision percentage, %{customdata[2]:+.2f}%<br>"
                "Class, %{customdata[3]}"
                "<extra></extra>"
            )
        )
    )

    figure.add_hline(
        y=0,
        line_width=1
    )

    figure.add_hline(
        y=watchlist_threshold_mw,
        line_dash="dash",
        annotation_text=f"Watchlist, +{watchlist_threshold_mw:,} MW"
    )

    figure.add_hline(
        y=-watchlist_threshold_mw,
        line_dash="dash",
        annotation_text=f"Watchlist, -{watchlist_threshold_mw:,} MW"
    )

    figure.add_hline(
        y=critical_threshold_mw,
        line_dash="dot",
        annotation_text=f"Critical, +{critical_threshold_mw:,} MW"
    )

    figure.add_hline(
        y=-critical_threshold_mw,
        line_dash="dot",
        annotation_text=f"Critical, -{critical_threshold_mw:,} MW"
    )

    figure.update_layout(
        title=f"Run to Run Wind Forecast Revisions, Next {horizon_days} Days",
        xaxis_title="Future delivery time",
        yaxis_title="Revision, MW",
        hovermode="x unified",
        height=550
    )

    return figure


def make_csv_download(dataframe):
    return dataframe.to_csv(index=False).encode("utf-8")


st.sidebar.title("Controls")

horizon_days = st.sidebar.selectbox(
    "Forecast horizon, days",
    options=[2, 3, 5, 7, 10, 14],
    index=3
)

watchlist_threshold_mw = st.sidebar.number_input(
    "Watchlist threshold, MW",
    min_value=50,
    max_value=3000,
    value=250,
    step=50
)

critical_threshold_mw = st.sidebar.number_input(
    "Critical swing threshold, MW",
    min_value=500,
    max_value=10000,
    value=3000,
    step=500
)

if st.sidebar.button("Refresh dashboard data"):
    st.cache_data.clear()
    st.sidebar.success("Dashboard cache cleared. The latest database data will be loaded.")


st.title("🌬️ NESO Wind Forecast Revision Monitor")

st.caption(
    "Database backed NESO wind forecast archive, run to run revision analysis and swing detection."
)

st.info(
    "ForecastDateTime is when NESO published the forecast. "
    "Delivery datetime is the future half hourly period being forecast. "
    "Dates after today are therefore expected forecasted wind generation values, not measured actual output."
)


try:
    runs_df = load_distinct_runs()
except Exception as error:
    st.error(f"Database connection failed, {error}")
    st.stop()


if runs_df.empty:
    st.warning(
        "No forecast runs found in the database yet. Run the GitHub Actions collector first."
    )
    st.stop()


latest_run_time = runs_df["forecast_datetime"].max()
latest_run_df = load_forecast_run(latest_run_time)

latest_peak_forecast = latest_run_df["wind_forecast_mw"].max()
latest_average_forecast = latest_run_df["wind_forecast_mw"].mean()
latest_average_capacity_factor = latest_run_df["capacity_factor_pct"].mean()
latest_forecast_start = latest_run_df["delivery_datetime"].min()
latest_forecast_end = latest_run_df["delivery_datetime"].max()


st.sidebar.subheader("Database Archive")

st.sidebar.metric(
    "Stored runs",
    len(runs_df)
)

st.sidebar.metric(
    "Newest run",
    latest_run_time.strftime("%d %b %H:%M")
)


st.subheader("Latest NESO Forecast Snapshot")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Forecast Published",
    latest_run_time.strftime("%d %b %H:%M")
)

col2.metric(
    "Peak Forecast",
    f"{latest_peak_forecast:,.0f} MW"
)

col3.metric(
    "Average Forecast",
    f"{latest_average_forecast:,.0f} MW"
)

col4.metric(
    "Average Capacity Factor",
    f"{latest_average_capacity_factor:.1f}%"
)

st.caption(
    f"Forecast delivery window, {latest_forecast_start} to {latest_forecast_end}"
)

st.plotly_chart(
    build_latest_forecast_chart(latest_run_df),
    use_container_width=True
)

st.download_button(
    label="Download latest forecast CSV",
    data=make_csv_download(latest_run_df),
    file_name="latest_neso_wind_forecast.csv",
    mime="text/csv"
)

st.divider()


st.subheader("Run to Run Forecast Revision Analysis")

pair = find_latest_comparable_pair(runs_df)

if pair is None:
    st.warning(
        "Only one forecast run is currently stored. "
        "Run to run revision analysis will appear after a second comparable NESO forecast run is collected."
    )

    st.dataframe(
        runs_df,
        use_container_width=True
    )

    st.stop()


previous_run_time, comparison_latest_run_time, previous_df, latest_df, matching_periods = pair

comparison_df = build_comparison(
    previous_df=previous_df,
    latest_df=latest_df,
    watchlist_threshold_mw=watchlist_threshold_mw,
    critical_threshold_mw=critical_threshold_mw
)

if comparison_df.empty:
    st.warning("The selected forecast runs have no overlapping delivery periods.")
    st.stop()


if comparison_latest_run_time != latest_run_time:
    st.warning(
        f"The newest database run is {latest_run_time}, but it has no comparable nearby partner yet. "
        f"The dashboard is showing the newest valid comparable pair, {previous_run_time} to {comparison_latest_run_time}."
    )


start_time = comparison_df["delivery_datetime"].min()
end_time = start_time + pd.Timedelta(days=horizon_days)

filtered_df = comparison_df[
    comparison_df["delivery_datetime"] <= end_time
].copy()


st.info(
    f"Comparing {previous_run_time} with {comparison_latest_run_time}. "
    f"Matching future delivery periods, {matching_periods:,}."
)


latest_peak_mw = comparison_df["latest_forecast_mw"].max()
latest_average_mw = comparison_df["latest_forecast_mw"].mean()
largest_revision_mw = comparison_df["absolute_revision_mw"].max()
watchlist_alerts = int(comparison_df["watchlist_alert"].sum())
critical_alerts = int(comparison_df["critical_alert"].sum())

metric1, metric2, metric3, metric4, metric5 = st.columns(5)

metric1.metric(
    "Latest Peak Forecast",
    f"{latest_peak_mw:,.0f} MW"
)

metric2.metric(
    "Latest Avg Forecast",
    f"{latest_average_mw:,.0f} MW"
)

metric3.metric(
    "Largest Revision",
    f"{largest_revision_mw:,.0f} MW"
)

metric4.metric(
    "Watchlist Alerts",
    f"{watchlist_alerts:,}"
)

metric5.metric(
    "Critical Alerts",
    f"{critical_alerts:,}"
)


st.plotly_chart(
    build_comparison_chart(
        filtered_df,
        previous_run_time,
        comparison_latest_run_time,
        horizon_days
    ),
    use_container_width=True
)


st.plotly_chart(
    build_revision_chart(
        filtered_df,
        horizon_days,
        watchlist_threshold_mw,
        critical_threshold_mw
    ),
    use_container_width=True
)


st.subheader("Top Forecast Revisions")

top_revisions_df = (
    comparison_df
    .sort_values(
        "absolute_revision_mw",
        ascending=False
    )
    .head(15)
)

st.dataframe(
    top_revisions_df,
    use_container_width=True
)


st.subheader("Watchlist Alerts")

watchlist_df = comparison_df[
    comparison_df["watchlist_alert"]
].copy()

watchlist_df = watchlist_df.sort_values(
    "absolute_revision_mw",
    ascending=False
)

if watchlist_df.empty:
    st.success(
        f"No periods changed by {watchlist_threshold_mw:,} MW or more."
    )
else:
    st.dataframe(
        watchlist_df,
        use_container_width=True
    )


st.subheader("Critical Swing Alerts")

critical_df = comparison_df[
    comparison_df["critical_alert"]
].copy()

critical_df = critical_df.sort_values(
    "absolute_revision_mw",
    ascending=False
)

if critical_df.empty:
    st.success(
        f"No critical swings detected. No period changed by {critical_threshold_mw:,} MW or more."
    )
else:
    st.dataframe(
        critical_df,
        use_container_width=True
    )


st.subheader("Revision Classification Summary")

revision_class_summary_df = (
    comparison_df
    .groupby("revision_class")
    .agg(
        periods=("delivery_datetime", "count"),
        average_absolute_revision_mw=("absolute_revision_mw", "mean"),
        maximum_absolute_revision_mw=("absolute_revision_mw", "max")
    )
    .reset_index()
    .sort_values(
        "maximum_absolute_revision_mw",
        ascending=False
    )
)

st.dataframe(
    revision_class_summary_df,
    use_container_width=True
)

revision_class_figure = px.bar(
    revision_class_summary_df,
    x="revision_class",
    y="periods",
    title="Forecast Revision Classification",
    labels={
        "revision_class": "Revision class",
        "periods": "Number of periods"
    }
)

revision_class_figure.update_layout(
    height=450
)

st.plotly_chart(
    revision_class_figure,
    use_container_width=True
)


with st.expander("View archived forecast runs"):
    st.dataframe(
        runs_df,
        use_container_width=True
    )


with st.expander("View raw comparison data"):
    st.dataframe(
        comparison_df,
        use_container_width=True
    )

    st.download_button(
        label="Download comparison CSV",
        data=make_csv_download(comparison_df),
        file_name="neso_wind_forecast_comparison.csv",
        mime="text/csv"
    )
