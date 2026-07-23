# NESO Wind Forecast Revision Monitor

A cloud deployed renewable energy analytics dashboard for monitoring run to run revisions in NESO 14 day ahead wind power forecasts.

Live dashboard:  
https://neso-wind-forecast-monitor-knbc32cgs89awbzxdfujqi.streamlit.app/

---

## Project Overview

The NESO Wind Forecast Revision Monitor is a database backed Streamlit application designed to collect, archive, compare and visualise Great Britain wind power forecast publications from the National Energy System Operator, NESO.

The main objective of the project is to monitor how wind generation forecasts change from one forecast publication to another. These changes are known as forecast revisions.

In renewable dominated power systems, forecast revisions are important because expected wind generation can change significantly as weather predictions are updated. Monitoring these changes can support better visibility of renewable variability, operational planning, flexibility assessment and energy market analysis.

This project turns open energy data into a live cloud based dashboard using Python, PostgreSQL, GitHub Actions, Supabase and Streamlit.

---

## Live Application

The deployed Streamlit dashboard can be accessed here:

[NESO Wind Forecast Revision Monitor](https://neso-wind-forecast-monitor-knbc32cgs89awbzxdfujqi.streamlit.app/)

---

## What the App Does

The dashboard currently performs the following tasks:

* Collects NESO 14 day ahead wind forecast data from the NESO API
* Stores each new forecast publication as a separate forecast run
* Archives forecast history in a Supabase PostgreSQL database
* Reads the stored forecast history into a live Streamlit dashboard
* Displays the latest NESO wind forecast profile
* Shows key forecast indicators such as peak forecast, average forecast and capacity factor
* Compares the latest forecast run with the previous comparable run
* Calculates run to run forecast revisions in MW
* Classifies forecast movements into normal, minor, significant, major and critical revisions
* Displays watchlist alerts when forecast revisions exceed selected thresholds
* Displays critical swing alerts when large changes are detected
* Uses GitHub Actions for automated scheduled data collection
* Deploys the user interface through Streamlit Community Cloud

---

## Why Forecast Revision Monitoring Matters

Wind generation depends heavily on weather conditions, so forecast values can change as new weather information becomes available.

A single forecast tells us what wind generation is expected to be. However, comparing forecast runs tells us something more useful:

* whether the expected wind output is increasing or decreasing
* where the largest forecast changes are occurring
* whether there are major swings in the coming days
* whether the forecast is becoming more stable or more uncertain
* which future delivery periods may require closer operational attention

For example, if the latest forecast shows a large downward revision compared with the previous publication, this may indicate reduced expected wind output for a future period. This type of insight can be useful for grid awareness, reserve planning, balancing analysis, flexibility decisions and energy market interpretation.

---

## Data Source

The data used in this project comes from the National Energy System Operator, NESO open data portal.

Dataset used:

**NESO 14 Days Ahead Wind Forecasts**

Resource ID:

```text
93c3048e-1dab-4057-a2a9-417540583929
