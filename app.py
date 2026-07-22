from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from mushroom_watch.analysis import (
    aggregate_frame,
    analyze_guild,
    point_map_frame,
    representative_detail,
)
from mushroom_watch.config import dump_watch_config
from mushroom_watch.geo import CountyCatalog, LocationError, geocode_candidates, sample_radius
from mushroom_watch.models import Location, SamplePoint
from mushroom_watch.monitor import local_now
from mushroom_watch.observations import ObservationStore
from mushroom_watch.profiles import load_profiles
from mushroom_watch.recharge import aggregate_recharge_events, find_recharge_events
from mushroom_watch.repository import (
    detect_repository_slug,
    edit_file_url,
    issue_form_url,
    normalize_repository_slug,
    observation_issues_url,
)
from mushroom_watch.weather import WeatherError, fetch_weather_points

ROOT = Path(__file__).resolve().parent
PROFILE_PATH = ROOT / "config" / "guilds.yaml"
COUNTY_PATH = ROOT / "data" / "county_centroids.csv"
OBSERVATION_PATH = ROOT / "data" / "observations.sqlite3"
DETECTED_REPOSITORY = detect_repository_slug(ROOT)

st.set_page_config(page_title="Mushroom Watch 2.0", page_icon="🍄", layout="wide")


@st.cache_resource
def get_profiles() -> dict[str, dict[str, Any]]:
    return load_profiles(PROFILE_PATH)


@st.cache_resource
def get_county_catalog() -> CountyCatalog:
    return CountyCatalog.from_csv(COUNTY_PATH)


@st.cache_data(ttl=86400, show_spinner=False)
def cached_geocode(query: str) -> list[Location]:
    return geocode_candidates(query, count=12)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_weather(
    point_rows: tuple[tuple[str, float, float, float, float], ...],
    forecast_days: int,
):
    points = [
        SamplePoint(
            point_id=row[0],
            latitude=row[1],
            longitude=row[2],
            distance_miles=row[3],
            bearing_degrees=row[4],
        )
        for row in point_rows
    ]
    return fetch_weather_points(points, past_days=30, forecast_days=forecast_days + 1)


PROFILES = get_profiles()
CATALOG = get_county_catalog()


def score_band(score: float) -> str:
    if score >= 80:
        return "Very favorable"
    if score >= 65:
        return "Favorable"
    if score >= 50:
        return "Watch"
    if score >= 35:
        return "Marginal"
    return "Unfavorable"


def profile_label(key: str) -> str:
    return str(PROFILES[key]["display_name"])


def resolve_sidebar_location(method: str) -> Location:
    if method == "County":
        record = st.session_state.get("selected_county_record")
        if record is None:
            raise LocationError("Choose a county.")
        return CATALOG.as_location(record)
    if method == "City or ZIP":
        candidates = st.session_state.get("place_candidates", [])
        selected_index = st.session_state.get("place_candidate_index", 0)
        if not candidates:
            query = str(st.session_state.get("place_query", "")).strip()
            candidates = cached_geocode(query)
            st.session_state["place_candidates"] = candidates
        return candidates[min(int(selected_index), len(candidates) - 1)]
    return Location(
        label=str(st.session_state.get("coordinate_label") or "Custom coordinates"),
        latitude=float(st.session_state.get("coordinate_latitude", 41.63)),
        longitude=float(st.session_state.get("coordinate_longitude", -85.00)),
        timezone="auto",
        source="coordinates",
    )


def run_analysis(location: Location, radius_miles: float, sample_count: int, guilds: list[str], forecast_days: int, threshold: float):
    points = sample_radius(location.latitude, location.longitude, radius_miles, sample_count)
    point_rows = tuple(
        (
            point.point_id,
            point.latitude,
            point.longitude,
            point.distance_miles,
            point.bearing_degrees,
        )
        for point in points
    )
    weather_points = cached_weather(point_rows, forecast_days)
    now = local_now(weather_points[0].timezone if weather_points else location.timezone)
    today = now.date()
    guild_results: dict[str, dict[str, Any]] = {}
    for guild in guilds:
        point_scores, aggregates = analyze_guild(
            weather_points,
            guild,
            PROFILES[guild],
            threshold=threshold,
        )
        guild_results[guild] = {
            "point_scores": point_scores,
            "aggregates": aggregates,
            "frame": aggregate_frame(aggregates),
        }
    events_by_point = {
        item.point.point_id: find_recharge_events(
            item.hourly,
            threshold_inches=1.0,
            minimum_hours=8,
            maximum_hours=72,
            now=now,
        )
        for item in weather_points
    }
    recharge_events = aggregate_recharge_events(events_by_point, total_points=len(weather_points))
    return {
        "location": location,
        "points": points,
        "weather_points": weather_points,
        "guild_results": guild_results,
        "recharge_events": recharge_events,
        "today": today,
        "radius_miles": radius_miles,
        "sample_count": sample_count,
        "guilds": guilds,
        "forecast_days": forecast_days,
        "threshold": threshold,
    }


st.title("🍄 Mushroom Watch 2.0")
st.caption(
    "Weather-compatibility estimates for four ecological mushroom guilds. "
    "This app does not identify mushrooms, prove presence, or determine edibility."
)

with st.sidebar:
    st.header("1. Choose a center")
    location_method = st.radio("Location method", ["County", "City or ZIP", "Coordinates"], horizontal=False)

    if location_method == "County":
        states = CATALOG.states()
        state_labels = [name for _, name in states]
        default_state = state_labels.index("Indiana") if "Indiana" in state_labels else 0
        selected_state_name = st.selectbox("State", state_labels, index=default_state)
        selected_state_abbr = next(abbr for abbr, name in states if name == selected_state_name)
        county_records = CATALOG.counties(selected_state_abbr)
        county_names = [record.county_name for record in county_records]
        default_county = county_names.index("Steuben") if selected_state_abbr == "IN" and "Steuben" in county_names else 0
        selected_county_name = st.selectbox("County or equivalent", county_names, index=default_county)
        st.session_state["selected_county_record"] = next(
            record for record in county_records if record.county_name == selected_county_name
        )
    elif location_method == "City or ZIP":
        st.text_input(
            "City, town, or ZIP code",
            value=st.session_state.get("place_query", "Angola, Indiana"),
            key="place_query",
        )
        if st.button("Find location matches", use_container_width=True):
            try:
                st.session_state["place_candidates"] = cached_geocode(st.session_state["place_query"])
                st.session_state["place_candidate_index"] = 0
            except LocationError as exc:
                st.error(str(exc))
        candidates = st.session_state.get("place_candidates", [])
        if candidates:
            labels = [f"{item.label} ({item.latitude:.3f}, {item.longitude:.3f})" for item in candidates]
            selected_label = st.selectbox("Match", labels)
            st.session_state["place_candidate_index"] = labels.index(selected_label)
    else:
        st.text_input("Location label", value="Custom coordinates", key="coordinate_label")
        st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=41.63, format="%.5f", key="coordinate_latitude")
        st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=-85.00, format="%.5f", key="coordinate_longitude")

    st.header("2. Set the area")
    radius_miles = st.slider(
        "Radius in miles",
        min_value=0,
        max_value=150,
        value=20,
        step=5,
        help="Points are distributed across the disk instead of only around its edge.",
    )
    sample_count = st.select_slider(
        "Weather sample points",
        options=[1, 5, 9, 13, 17, 25, 33],
        value=9,
        help="More points better capture scattered rainfall, but increase API work.",
    )

    st.header("3. Select models")
    selected_guilds = st.multiselect(
        "Mushroom guilds",
        options=list(PROFILES),
        default=list(PROFILES),
        format_func=profile_label,
    )
    forecast_days = st.slider("Forecast days", 3, 10, 7)
    score_threshold = st.slider("Favorable score threshold", 40, 90, 65)
    minimum_area_pct = st.slider("Minimum favorable area", 0, 100, 40, step=5)
    analyze_button = st.button("Analyze conditions", type="primary", use_container_width=True)

    st.divider()
    st.caption(
        "Open-Meteo values are gridded model estimates. Canopy, slope, host trees, substrate, and localized storms may differ sharply."
    )

if analyze_button:
    if not selected_guilds:
        st.error("Select at least one mushroom guild.")
    else:
        try:
            location = resolve_sidebar_location(location_method)
            with st.spinner("Loading 30 days of antecedent weather and the forecast…"):
                st.session_state["analysis"] = run_analysis(
                    location,
                    float(radius_miles),
                    int(sample_count),
                    selected_guilds,
                    int(forecast_days),
                    float(score_threshold),
                )
            st.session_state["minimum_area_pct"] = minimum_area_pct
        except (LocationError, WeatherError, ValueError) as exc:
            st.error(f"Analysis could not be completed: {exc}")
        except Exception as exc:  # Surface unexpected API/schema failures without hiding them.
            st.error(f"Unexpected analysis error: {exc}")

analysis = st.session_state.get("analysis")
if not analysis:
    st.subheader("What changed in 2.0")
    st.markdown(
        """
        - A full 30-day antecedent-precipitation index instead of a short rain window
        - Soil moisture normalized to each location's recent modeled range
        - A multiplicative moisture gate that can cap an otherwise high temperature score
        - Separate morel, ectomycorrhizal, wood-decay, and soil/litter saprotroph models
        - Degree-days, temperature trend, VPD, ET₀, wind, and humidity dry-down
        - Rolling 8–72-hour recharge alerts for at least 1 inch of forecast precipitation
        - County/state selection, area-balanced radius points, GitHub Issue field logs, ntfy, Codespaces, tests, and GitHub Actions
        """
    )
    st.info("Choose a location and click **Analyze conditions**.")
    st.stop()

location: Location = analysis["location"]
today: date = analysis["today"]
minimum_area_pct = int(st.session_state.get("minimum_area_pct", 40))
st.success(
    f"Analyzing **{location.label}** within **{analysis['radius_miles']:.0f} miles** "
    f"using **{len(analysis['weather_points'])} area-balanced weather points**."
)

summary_rows: list[dict[str, Any]] = []
for guild in analysis["guilds"]:
    aggregates = analysis["guild_results"][guild]["aggregates"]
    future = [
        item for item in aggregates
        if item.date >= today and (item.date - today).days <= analysis["forecast_days"]
    ]
    if not future:
        continue
    current = min(future, key=lambda item: abs((item.date - today).days))
    best = max(future, key=lambda item: (item.median_score, item.favorable_fraction))
    would_alert = best.median_score >= analysis["threshold"] and best.favorable_fraction * 100 >= minimum_area_pct
    summary_rows.append(
        {
            "Guild": profile_label(guild),
            "Current": current.median_score,
            "Current band": score_band(current.median_score),
            "Peak": best.median_score,
            "Best date": best.date.strftime("%a %b %d"),
            "Favorable area": best.favorable_fraction,
            "Evidence / confidence": best.confidence_label,
            "Alert": "Yes" if would_alert else "No",
            "_guild": guild,
        }
    )
summary = pd.DataFrame(summary_rows)

if summary.empty:
    st.warning("The weather response did not contain scoreable forecast dates.")
    st.stop()

metric_columns = st.columns(min(4, len(summary)))
for column, row in zip(metric_columns, summary.to_dict(orient="records")):
    column.metric(row["Guild"], f"{row['Current']:.0f}/100", row["Current band"])

outlook_tab, detail_tab, recharge_tab, field_tab, config_tab = st.tabs(
    ["Outlook", "Model detail", "Recharge events", "Field observations", "Alert configuration"]
)

with outlook_tab:
    st.subheader("Guild outlook")
    visible_summary = summary.drop(columns=["_guild"])
    st.dataframe(
        visible_summary,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Current": st.column_config.ProgressColumn(min_value=0, max_value=100),
            "Peak": st.column_config.ProgressColumn(min_value=0, max_value=100),
            "Favorable area": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
        },
    )

    chart_rows = []
    for guild in analysis["guilds"]:
        frame = analysis["guild_results"][guild]["frame"]
        frame = frame[(frame["date"] >= today)].head(analysis["forecast_days"] + 1)
        for row in frame.itertuples(index=False):
            chart_rows.append({"Date": pd.Timestamp(row.date), "Score": row.median_score, "Guild": profile_label(guild)})
    chart = pd.DataFrame(chart_rows)
    if not chart.empty:
        st.line_chart(chart, x="Date", y="Score", color="Guild", use_container_width=True)

    map_left, map_right = st.columns([1, 2])
    with map_left:
        map_guild = st.selectbox("Map guild", analysis["guilds"], format_func=profile_label, key="map_guild")
        available_dates = [item.date for item in analysis["guild_results"][map_guild]["aggregates"] if item.date >= today]
        map_date = st.selectbox("Map date", available_dates[: analysis["forecast_days"] + 1], format_func=lambda item: item.strftime("%a %b %d"))
    with map_right:
        map_frame = point_map_frame(
            analysis["weather_points"],
            analysis["guild_results"][map_guild]["point_scores"],
            map_date,
        )
        if not map_frame.empty:
            map_frame["marker_size"] = 30 + map_frame["score"] * 4
            st.map(map_frame, latitude="latitude", longitude="longitude", size="marker_size", use_container_width=True)
            st.caption("Marker size represents the guild score at each modeled weather grid.")

with detail_tab:
    st.subheader("Why the model produced its score")
    detail_guild = st.selectbox("Guild", analysis["guilds"], format_func=profile_label, key="detail_guild")
    detail_dates = [item.date for item in analysis["guild_results"][detail_guild]["aggregates"] if item.date >= today]
    if not detail_dates:
        st.info("No scoreable forecast dates are available for this guild.")
    else:
        detail_date = st.selectbox("Date", detail_dates[: analysis["forecast_days"] + 1], format_func=lambda item: item.strftime("%A, %B %d"), key="detail_date")
        detail = representative_detail(analysis["guild_results"][detail_guild]["point_scores"], detail_date)
        aggregate = next(item for item in analysis["guild_results"][detail_guild]["aggregates"] if item.date == detail_date)
        if detail:
            cols = st.columns(5)
            cols[0].metric("Median area score", f"{aggregate.median_score:.0f}/100")
            cols[1].metric("Base weather score", f"{detail.base_score:.0f}/100")
            cols[2].metric("Moisture multiplier", f"×{detail.moisture_multiplier:.2f}")
            cols[3].metric("Dry-down index", f"{detail.drydown_index:.2f}")
            cols[4].metric("Evidence / confidence", aggregate.confidence_label)
            st.caption(
                "The final score equals the base guild score multiplied by the moisture limiter. "
                "The confidence label describes data completeness, history, forecast lead, and spatial agreement, not taxonomic certainty."
            )
            component_frame = pd.DataFrame(
                [{"Component": name.replace("_", " ").title(), "Points": value} for name, value in detail.components.items()]
            ).sort_values("Points", ascending=False)
            st.dataframe(component_frame, hide_index=True, use_container_width=True)
            metric_frame = pd.DataFrame(
                [{"Metric": name.replace("_", " ").title(), "Value": value} for name, value in detail.metrics.items()]
            )
            st.dataframe(metric_frame, hide_index=True, use_container_width=True)
            for reason in detail.reasons + aggregate.reasons:
                st.info(reason)
            with st.expander("Guild model notes"):
                st.write(PROFILES[detail_guild].get("scientific_scope", ""))
                for note in PROFILES[detail_guild].get("model_notes", []):
                    st.write(f"• {note}")

with recharge_tab:
    st.subheader("Rolling 8–72-hour recharge events")
    st.caption(
        "An event is shown when a rolling forecast window reaches at least 1.00 inch. "
        "Area coverage indicates how many sampled weather grids detect a similar event."
    )
    events = analysis["recharge_events"]
    if not events:
        st.info("No qualifying 1-inch recharge event appears in the available forecast.")
    else:
        event_rows = [
            {
                "Start": event.start,
                "End": event.end,
                "Duration hours": event.duration_hours,
                "Precipitation": event.precipitation_in,
                "Peak probability": event.peak_probability_pct,
                "Area coverage": event.sample_fraction,
                "Would alert": "Yes" if event.sample_fraction * 100 >= minimum_area_pct else "No",
            }
            for event in events
        ]
        st.dataframe(
            pd.DataFrame(event_rows),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Precipitation": st.column_config.NumberColumn(format="%.2f in"),
                "Peak probability": st.column_config.NumberColumn(format="%.0f%%"),
                "Area coverage": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
            },
        )

with field_tab:
    st.subheader("GitHub field-observation log")
    st.info(
        "Permanent observations are stored as GitHub Issues labeled `field-observation`. "
        "This survives Codespaces and Streamlit restarts and keeps the calibration record with the repository."
    )
    repository_input = st.text_input(
        "GitHub repository",
        value=DETECTED_REPOSITORY or "",
        placeholder="owner/repository",
        help="Usually detected automatically in Codespaces. Enter owner/repository when deployed elsewhere.",
        key="github_repository_slug",
    )
    repository_slug = normalize_repository_slug(repository_input)
    selected_for_log = st.selectbox(
        "Guild to prefill",
        analysis["guilds"],
        format_func=profile_label,
        key="github_observation_guild",
    )
    modeled_for_log = representative_detail(
        analysis["guild_results"][selected_for_log]["point_scores"], today
    )
    if repository_slug:
        prefill = {
            "observed_at": today.isoformat(),
            "location": location.label,
            "coordinates": f"{location.latitude:.3f}, {location.longitude:.3f}",
            "modeled_score": f"{modeled_for_log.score:.0f}" if modeled_for_log else None,
            "confidence": modeled_for_log.confidence_label if modeled_for_log else None,
        }
        left, right = st.columns(2)
        left.link_button(
            "Log an observation in GitHub",
            issue_form_url(repository_slug, values=prefill),
            type="primary",
            use_container_width=True,
        )
        right.link_button(
            "View all field observations",
            observation_issues_url(repository_slug),
            use_container_width=True,
        )
        st.caption(
            "The form opens in GitHub. Record unsuccessful searches too; negative observations help calibrate false positives. "
            "Use broad locations or rounded coordinates when a site is sensitive."
        )
    else:
        st.warning(
            "Enter the repository as `owner/repository` to activate the permanent GitHub observation form."
        )

    with st.expander("Temporary scratch log inside this running app"):
        st.warning(
            "Scratch entries use a local SQLite file and may disappear when a Codespace is deleted or a hosted app restarts. "
            "Use the GitHub form above for the permanent record."
        )
        store = ObservationStore(OBSERVATION_PATH)
        with st.form("observation_form", clear_on_submit=True):
            observed_at = st.date_input("Observation date", value=today)
            observation_guild = st.selectbox("Guild", analysis["guilds"], format_func=profile_label)
            taxon = st.text_input("Species or field name, if known")
            found = st.toggle("Mushrooms found", value=True)
            abundance = st.selectbox("Abundance", ["None", "Single", "Few", "Many", "Abundant"])
            habitat = st.text_input("Habitat", placeholder="Example: mature oak-maple woods")
            substrate = st.text_input("Substrate", placeholder="Example: buried wood, soil, standing snag")
            host_tree = st.text_input("Host tree or nearby trees")
            photo_url = st.text_input("Photo link, optional")
            notes = st.text_area("Notes")
            save_observation = st.form_submit_button("Save temporary observation")
        if save_observation:
            modeled = representative_detail(
                analysis["guild_results"][observation_guild]["point_scores"], observed_at
            )
            store.add(
                {
                    "observed_at": observed_at.isoformat(),
                    "location_label": location.label,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "guild": observation_guild,
                    "taxon": taxon,
                    "found": found,
                    "abundance": abundance,
                    "habitat": habitat,
                    "substrate": substrate,
                    "host_tree": host_tree,
                    "notes": notes,
                    "photo_url": photo_url,
                    "modeled_score": modeled.score if modeled else None,
                    "confidence_label": modeled.confidence_label if modeled else None,
                }
            )
            st.success("Temporary observation saved in this running environment.")
        observations = store.list()
        if not observations.empty:
            st.dataframe(observations, hide_index=True, use_container_width=True)
            st.download_button(
                "Download temporary observations CSV",
                data=store.export_csv(),
                file_name="mushroom_watch_observations.csv",
                mime="text/csv",
            )
        uploaded = st.file_uploader("Import or merge a temporary observations CSV", type=["csv"])
        if uploaded is not None and st.button("Import temporary observations"):
            try:
                count = store.import_csv(uploaded.getvalue())
                st.success(f"Imported {count} observation(s).")
            except ValueError as exc:
                st.error(str(exc))

with config_tab:
    st.subheader("Download a scheduled-alert configuration")
    if location.source == "county_catalog" and location.state_abbr and location.county_name:
        location_config: dict[str, Any] = {
            "mode": "county",
            "state": location.state_abbr,
            "county": location.county_name,
        }
    else:
        location_config = {
            "mode": "coordinates",
            "label": location.label,
            "latitude": round(location.latitude, 6),
            "longitude": round(location.longitude, 6),
            "timezone": location.timezone,
        }
    watch = {
        "name": location.label,
        "location": location_config,
        "radius_miles": int(analysis["radius_miles"]),
        "sample_points": int(analysis["sample_count"]),
        "guilds": analysis["guilds"],
        "score_threshold": int(analysis["threshold"]),
        "minimum_area_fraction": round(minimum_area_pct / 100, 2),
        "minimum_confidence": 0.45,
        "forecast_days": int(analysis["forecast_days"]),
        "recharge_threshold_inches": 1.0,
        "recharge_minimum_area_fraction": round(minimum_area_pct / 100, 2),
        "cooldown_hours": 72,
    }
    yaml_text = dump_watch_config(watch)
    st.code(yaml_text, language="yaml")
    st.download_button(
        "Download watch_config.yaml",
        data=yaml_text.encode("utf-8"),
        file_name="watch_config.yaml",
        mime="text/yaml",
    )
    repository_slug = normalize_repository_slug(st.session_state.get("github_repository_slug", "")) or DETECTED_REPOSITORY
    st.markdown(
        "Commit this YAML as `watch_config.yaml` in the repository root. Add `NTFY_TOPIC` as a GitHub Actions secret, "
        "then run **Actions → Mushroom alerts** with **Dry run** enabled once."
    )
    if repository_slug:
        st.link_button(
            "Open watch_config.yaml in GitHub",
            edit_file_url(repository_slug, "watch_config.yaml"),
            use_container_width=True,
        )

st.divider()
st.caption(
    "Safety: Never eat a wild mushroom based on this app, a photo, or weather conditions. "
    "Use complete taxonomic characters and qualified local expertise."
)
