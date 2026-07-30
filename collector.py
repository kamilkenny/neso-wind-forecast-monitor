import time
import sys
import logging

# configure simple logging near the top of the file
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def fetch_latest_neso_forecast(retries=3, backoff=2):
    parameters = {
        "resource_id": NESO_RESOURCE_ID,
        "limit": 5000
    }

    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            response = requests.get(
                NESO_API_URL,
                params=parameters,
                timeout=30
            )
            response.raise_for_status()
            payload = response.json()

            if not payload.get("success"):
                logging.warning("NESO API returned success=False on attempt %d: %s", attempt, payload)
            else:
                records = payload.get("result", {}).get("records", [])
                if records:
                    dataframe = pd.DataFrame(records)
                    # continue with original validation/transform steps below
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

                # no records in payload
                logging.warning("NESO API returned 0 records on attempt %d.", attempt)

        except (requests.RequestException, ValueError) as exc:
            logging.warning("Request attempt %d failed: %s", attempt, exc)

        # retry if we still have attempts left
        if attempt < retries:
            sleep_seconds = backoff ** (attempt - 1)
            logging.info("Retrying in %s seconds...", sleep_seconds)
            time.sleep(sleep_seconds)

    # After retries, return an empty DataFrame with the expected columns so caller can decide
    logging.info("No NESO records after %d attempts; returning empty dataframe.", retries)
    empty_df = pd.DataFrame(columns=[
        "forecast_datetime",
        "delivery_datetime",
        "settlement_period",
        "capacity_mw",
        "wind_forecast_mw"
    ])
    return empty_df


def insert_forecast_rows(connection, dataframe):
    if dataframe is None or dataframe.empty:
        logging.info("No rows to insert (empty dataframe).")
        return 0

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

    if dataframe.empty:
        logging.info("No forecast records fetched from NESO. Exiting without inserting.")
        # exit 0 so the GitHub Action run doesn't fail due to no data
        sys.exit(0)

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
            print("No new rows inserted. This forecast run already exists or no data to insert.")
        else:
            print("New NESO forecast run archived successfully.")

    finally:
        connection.close()
