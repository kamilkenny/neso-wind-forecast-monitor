import io
import os
import time

import pandas as pd
import psycopg2
import requests
from psycopg2.extras import execute_values


# ============================================================
# NESO source configuration
# ============================================================

NESO_RESOURCE_ID = "93c3048e-1dab-4057-a2a9-417540583929"

NESO_DATASTORE_URL = (
    "https://api.neso.energy/api/3/action/datastore_search"
)

NESO_CSV_URL = (
    "https://api.neso.energy/"
    "dataset/2f134a4e-92e5-43b8-96c3-0dd7d92fcc52/"
    "resource/93c3048e-1dab-4057-a2a9-417540583929/"
    "download/14da_wind_forecast.csv"
)

REQUEST_HEADERS = {
    "User-Agent": "NESO-Wind-Forecast-Monitor/1.0"
}

STANDARD_COLUMNS = [
    "forecast_datetime",
    "delivery_datetime",
    "settlement_period",
    "capacity_mw",
    "wind_forecast_mw",
]


# ============================================================
# Database configuration
# ============================================================

def get_database_url():
    """
    Read the Supabase database connection string from
    the GitHub Actions DATABASE_URL secret.
    """

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing. "
            "Add it as a GitHub Actions repository secret."
        )

    return database_url


# ============================================================
# NESO data preparation
# ============================================================

def normalise_neso_forecast(dataframe):
    """
    Convert either NESO DataStore or CSV fields into
    the standard database column structure.
    """

    if dataframe is None or dataframe.empty:
        raise RuntimeError(
            "NESO data was retrieved but contained no rows."
        )

    dataframe = dataframe.copy()

    # Remove whitespace and a possible UTF-8 byte-order mark.
    dataframe.columns = [
        str(column).replace("\ufeff", "").strip()
        for column in dataframe.columns
    ]

    # Support the field-name variations used by NESO.
    rename_map = {
        "ForecastDateTime": "forecast_datetime",
        "ForecastDatetime": "forecast_datetime",
        "forecast_datetime": "forecast_datetime",

        "Datetime": "delivery_datetime",
        "DateTime": "delivery_datetime",
        "datetime": "delivery_datetime",
        "delivery_datetime": "delivery_datetime",

        "Settlement_Period": "settlement_period",
        "Settlement Period": "settlement_period",
        "settlement_period": "settlement_period",

        "Capacity": "capacity_mw",
        "capacity": "capacity_mw",
        "capacity_mw": "capacity_mw",

        "Wind_Forecast": "wind_forecast_mw",
        "Wind Forecast": "wind_forecast_mw",
        "wind_forecast": "wind_forecast_mw",
        "wind_forecast_mw": "wind_forecast_mw",
    }

    dataframe = dataframe.rename(
        columns=rename_map
    )

    missing_columns = [
        column
        for column in STANDARD_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        available_columns = ", ".join(
            str(column)
            for column in dataframe.columns
        )

        raise RuntimeError(
            "NESO response is missing required columns: "
            + ", ".join(missing_columns)
            + ". Available columns: "
            + available_columns
        )

    # Convert timestamps.
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

    # Convert numerical fields.
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

    # Remove invalid records.
    dataframe = dataframe.dropna(
        subset=STANDARD_COLUMNS
    ).copy()

    if dataframe.empty:
        raise RuntimeError(
            "NESO data was downloaded, but no valid rows "
            "remained after date and numeric conversion."
        )

    dataframe["settlement_period"] = (
        dataframe["settlement_period"].astype(int)
    )

    # Remove duplicate rows within the downloaded dataset.
    dataframe = dataframe.drop_duplicates(
        subset=[
            "forecast_datetime",
            "delivery_datetime",
        ],
        keep="last",
    )

    dataframe = dataframe.sort_values(
        [
            "forecast_datetime",
            "delivery_datetime",
        ]
    ).reset_index(drop=True)

    return dataframe[STANDARD_COLUMNS]


# ============================================================
# NESO DataStore retrieval
# ============================================================

def fetch_from_datastore():
    """
    Try the NESO CKAN DataStore three times.

    If the DataStore remains empty or unavailable,
    raise an error so the CSV fallback can be used.
    """

    last_error = None

    for attempt in range(1, 4):

        try:
            response = requests.get(
                NESO_DATASTORE_URL,
                params={
                    "resource_id": NESO_RESOURCE_ID,
                    "limit": 10000,
                },
                headers=REQUEST_HEADERS,
                timeout=60,
            )

            print(
                f"NESO DataStore attempt {attempt}: "
                f"HTTP {response.status_code}"
            )

            response.raise_for_status()

            payload = response.json()

            if not payload.get("success", False):
                raise RuntimeError(
                    "NESO DataStore returned success=False."
                )

            records = (
                payload.get("result", {})
                .get("records", [])
            )

            print(
                "DataStore records returned:",
                len(records),
            )

            if records:
                print(
                    "NESO forecast retrieved from "
                    "the DataStore API."
                )

                return normalise_neso_forecast(
                    pd.DataFrame(records)
                )

            last_error = RuntimeError(
                "NESO DataStore returned zero records."
            )

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
        ) as error:

            last_error = error

            print(
                f"DataStore attempt {attempt} failed: "
                f"{error}"
            )

        if attempt < 3:
            wait_seconds = attempt * 10

            print(
                f"Retrying DataStore in "
                f"{wait_seconds} seconds..."
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        "NESO DataStore remained empty or unavailable "
        f"after three attempts. Last error: {last_error}"
    )


# ============================================================
# Official CSV fallback
# ============================================================

def fetch_from_csv():
    """
    Download and normalise the official NESO CSV
    when the CKAN DataStore returns no records.
    """

    print(
        "Falling back to the official NESO CSV..."
    )

    response = requests.get(
        NESO_CSV_URL,
        headers=REQUEST_HEADERS,
        timeout=120,
    )

    print(
        "NESO CSV response:",
        response.status_code,
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    if "text/html" in content_type:
        raise RuntimeError(
            "NESO CSV URL returned HTML instead "
            "of a CSV file."
        )

    dataframe = pd.read_csv(
        io.BytesIO(response.content)
    )

    print(
        "CSV rows downloaded:",
        len(dataframe),
    )

    normalised_dataframe = (
        normalise_neso_forecast(dataframe)
    )

    print(
        "NESO forecast retrieved successfully "
        "from the CSV fallback."
    )

    return normalised_dataframe


def fetch_latest_neso_forecast():
    """
    Retrieve the latest NESO forecast.

    First try the CKAN DataStore with retries.
    If that fails, use the official downloadable CSV.
    """

    datastore_error = None

    try:
        return fetch_from_datastore()

    except Exception as error:
        datastore_error = error

        print(
            "DataStore retrieval did not succeed:",
            error,
        )

    try:
        return fetch_from_csv()

    except Exception as csv_error:
        raise RuntimeError(
            "Both NESO DataStore and CSV retrieval failed. "
            f"DataStore error: {datastore_error}. "
            f"CSV error: {csv_error}"
        ) from csv_error


# ============================================================
# Supabase table management
# ============================================================

def create_table_if_needed(connection):
    """
    Create the Supabase table and indexes if they
    do not already exist.
    """

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS neso_wind_forecasts (
        id BIGSERIAL PRIMARY KEY,
        forecast_datetime TIMESTAMPTZ NOT NULL,
        delivery_datetime TIMESTAMPTZ NOT NULL,
        settlement_period INTEGER,
        capacity_mw NUMERIC,
        wind_forecast_mw NUMERIC,
        collected_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (
            forecast_datetime,
            delivery_datetime
        )
    );

    CREATE INDEX IF NOT EXISTS
        idx_neso_forecast_datetime
    ON neso_wind_forecasts (
        forecast_datetime
    );

    CREATE INDEX IF NOT EXISTS
        idx_neso_delivery_datetime
    ON neso_wind_forecasts (
        delivery_datetime
    );
    """

    with connection.cursor() as cursor:
        cursor.execute(create_table_sql)

    connection.commit()


def get_total_rows(connection):
    """
    Return the total number of stored wind records.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM neso_wind_forecasts;
            """
        )

        total_rows = cursor.fetchone()[0]

    return total_rows


def insert_forecast_rows(
    connection,
    dataframe,
):
    """
    Insert new wind-forecast rows into Supabase.

    Duplicate forecast and delivery timestamps
    are ignored.
    """

    rows = [
        (
            row.forecast_datetime.to_pydatetime(),
            row.delivery_datetime.to_pydatetime(),
            int(row.settlement_period),
            float(row.capacity_mw),
            float(row.wind_forecast_mw),
        )
        for row in dataframe.itertuples(
            index=False
        )
    ]

    if not rows:
        raise RuntimeError(
            "No valid NESO forecast rows are "
            "available for insertion."
        )

    insert_sql = """
    INSERT INTO neso_wind_forecasts (
        forecast_datetime,
        delivery_datetime,
        settlement_period,
        capacity_mw,
        wind_forecast_mw
    )
    VALUES %s
    ON CONFLICT (
        forecast_datetime,
        delivery_datetime
    )
    DO NOTHING;
    """

    count_before = get_total_rows(
        connection
    )

    with connection.cursor() as cursor:

        execute_values(
            cursor,
            insert_sql,
            rows,
        )

    connection.commit()

    count_after = get_total_rows(
        connection
    )

    inserted_rows = (
        count_after - count_before
    )

    return inserted_rows


# ============================================================
# Main collector
# ============================================================

def main():
    """
    Fetch the latest NESO wind forecast and
    archive it in Supabase.
    """

    database_url = get_database_url()

    dataframe = fetch_latest_neso_forecast()

    latest_run = (
        dataframe["forecast_datetime"].max()
    )

    delivery_start = (
        dataframe["delivery_datetime"].min()
    )

    delivery_end = (
        dataframe["delivery_datetime"].max()
    )

    print(
        "Latest NESO forecast fetched successfully."
    )

    print(
        f"Forecast publication time: {latest_run}"
    )

    print(
        f"Forecast delivery starts: {delivery_start}"
    )

    print(
        f"Forecast delivery ends: {delivery_end}"
    )

    print(
        f"Rows fetched: {len(dataframe):,}"
    )

    connection = psycopg2.connect(
        database_url,
        connect_timeout=30,
    )

    try:
        create_table_if_needed(
            connection
        )

        inserted_rows = insert_forecast_rows(
            connection,
            dataframe,
        )

        total_rows = get_total_rows(
            connection
        )

        print("=" * 60)

        print(
            f"Rows inserted into database: "
            f"{inserted_rows:,}"
        )

        print(
            f"Total rows now in database: "
            f"{total_rows:,}"
        )

        if inserted_rows == 0:
            print(
                "No new rows inserted. "
                "This forecast run already exists."
            )

        else:
            print(
                "New NESO forecast run "
                "archived successfully."
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
