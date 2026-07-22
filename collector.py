
import os

import pandas as pd
import psycopg2
import requests
from psycopg2.extras import execute_values


NESO_API_URL = "https://api.neso.energy/api/3/action/datastore_search"
NESO_RESOURCE_ID = "93c3048e-1dab-4057-a2a9-417540583929"


def get_database_url():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing. Add it as a GitHub Actions secret."
        )

    return database_url


def fetch_latest_neso_forecast():
    parameters = {
        "resource_id": NESO_RESOURCE_ID,
        "limit": 5000
    }

    response = requests.get(
        NESO_API_URL,
        params=parameters,
        timeout=30
    )

    response.raise_for_status()

    payload = response.json()

    if not payload.get("success"):
        raise RuntimeError("NESO API returned success=False.")

    records = payload.get("result", {}).get("records", [])

    if not records:
        raise RuntimeError("No records returned from NESO API.")

    dataframe = pd.DataFrame(records)

    required_columns = [
        "Datetime",
        "Settlement_Period",
        "Capacity",
        "Wind_Forecast",
        "ForecastDateTime"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise RuntimeError(f"Missing expected columns: {missing_columns}")

    dataframe["delivery_datetime"] = pd.to_datetime(
        dataframe["Datetime"],
        utc=True,
        errors="coerce"
    )

    dataframe["forecast_datetime"] = pd.to_datetime(
        dataframe["ForecastDateTime"],
        utc=True,
        errors="coerce"
    )

    dataframe["settlement_period"] = pd.to_numeric(
        dataframe["Settlement_Period"],
        errors="coerce"
    )

    dataframe["capacity_mw"] = pd.to_numeric(
        dataframe["Capacity"],
        errors="coerce"
    )

    dataframe["wind_forecast_mw"] = pd.to_numeric(
        dataframe["Wind_Forecast"],
        errors="coerce"
    )

    dataframe = dataframe.dropna(
        subset=[
            "forecast_datetime",
            "delivery_datetime",
            "settlement_period",
            "capacity_mw",
            "wind_forecast_mw"
        ]
    )

    dataframe = dataframe[
        [
            "forecast_datetime",
            "delivery_datetime",
            "settlement_period",
            "capacity_mw",
            "wind_forecast_mw"
        ]
    ].copy()

    dataframe["settlement_period"] = dataframe["settlement_period"].astype(int)

    return dataframe


def create_table_if_needed(connection):
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS neso_wind_forecasts (
        id BIGSERIAL PRIMARY KEY,
        forecast_datetime TIMESTAMPTZ NOT NULL,
        delivery_datetime TIMESTAMPTZ NOT NULL,
        settlement_period INTEGER,
        capacity_mw NUMERIC,
        wind_forecast_mw NUMERIC,
        collected_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (forecast_datetime, delivery_datetime)
    );

    CREATE INDEX IF NOT EXISTS idx_neso_forecast_datetime
    ON neso_wind_forecasts (forecast_datetime);

    CREATE INDEX IF NOT EXISTS idx_neso_delivery_datetime
    ON neso_wind_forecasts (delivery_datetime);
    """

    with connection.cursor() as cursor:
        cursor.execute(create_table_sql)

    connection.commit()


def get_total_rows(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM neso_wind_forecasts;")
        total_rows = cursor.fetchone()[0]

    return total_rows


def insert_forecast_rows(connection, dataframe):
    rows = [
        (
            row.forecast_datetime.to_pydatetime(),
            row.delivery_datetime.to_pydatetime(),
            int(row.settlement_period),
            float(row.capacity_mw),
            float(row.wind_forecast_mw)
        )
        for row in dataframe.itertuples(index=False)
    ]

    insert_sql = """
    INSERT INTO neso_wind_forecasts (
        forecast_datetime,
        delivery_datetime,
        settlement_period,
        capacity_mw,
        wind_forecast_mw
    )
    VALUES %s
    ON CONFLICT (forecast_datetime, delivery_datetime)
    DO NOTHING;
    """

    count_before = get_total_rows(connection)

    with connection.cursor() as cursor:
        execute_values(
            cursor,
            insert_sql,
            rows
        )

    connection.commit()

    count_after = get_total_rows(connection)

    inserted_rows = count_after - count_before

    return inserted_rows


def main():
    database_url = get_database_url()

    dataframe = fetch_latest_neso_forecast()

    latest_run = dataframe["forecast_datetime"].max()
    delivery_start = dataframe["delivery_datetime"].min()
    delivery_end = dataframe["delivery_datetime"].max()

    print("Latest NESO forecast fetched successfully.")
    print(f"Forecast publication time: {latest_run}")
    print(f"Forecast delivery starts: {delivery_start}")
    print(f"Forecast delivery ends: {delivery_end}")
    print(f"Rows fetched: {len(dataframe):,}")

    connection = psycopg2.connect(database_url)

    try:
        create_table_if_needed(connection)

        inserted_rows = insert_forecast_rows(
            connection,
            dataframe
        )

        total_rows = get_total_rows(connection)

        print("=" * 60)
        print(f"Rows inserted into database: {inserted_rows:,}")
        print(f"Total rows now in database: {total_rows:,}")

        if inserted_rows == 0:
            print("No new rows inserted. This forecast run already exists.")
        else:
            print("New NESO forecast run archived successfully.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
