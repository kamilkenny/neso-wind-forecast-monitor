# NESO Wind Forecast Revision Monitor

A database backed Streamlit dashboard for monitoring run to run revisions in NESO 14 day ahead wind power forecasts.

## What the app does

1. Collects NESO wind forecast runs from the NESO API.
2. Stores each new forecast publication in a Supabase PostgreSQL database.
3. Compares the latest two comparable forecast runs.
4. Calculates wind forecast revisions in MW and percentage terms.
5. Classifies forecast movements into normal, minor, moderate, significant, major and critical revisions.
6. Displays watchlist and critical swing alerts.
7. Uses GitHub Actions for scheduled data collection.
8. Deploys on Streamlit Community Cloud.

## Architecture

GitHub Actions fetches the latest NESO forecast and stores it in Supabase.  
The Streamlit app reads the stored forecast history from Supabase and displays the dashboard.

## Main files

- app.py, Streamlit dashboard
- collector.py, NESO API collector
- requirements.txt, Python dependencies
- .github/workflows/collect_neso.yml, scheduled GitHub Actions workflow

## Required secrets

Both GitHub Actions and Streamlit Community Cloud need this secret:

DATABASE_URL

This should contain the Supabase PostgreSQL connection string.
