"""Refresh data/county_centroids.csv from the U.S. Census Gazetteer file."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_counties_national.zip"
STATE_FIPS_TO_ABBR = {
    "01":"AL","02":"AK","04":"AZ","05":"AR","06":"CA","08":"CO","09":"CT","10":"DE","11":"DC",
    "12":"FL","13":"GA","15":"HI","16":"ID","17":"IL","18":"IN","19":"IA","20":"KS","21":"KY",
    "22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN","28":"MS","29":"MO","30":"MT",
    "31":"NE","32":"NV","33":"NH","34":"NJ","35":"NM","36":"NY","37":"NC","38":"ND","39":"OH",
    "40":"OK","41":"OR","42":"PA","44":"RI","45":"SC","46":"SD","47":"TN","48":"TX","49":"UT",
    "50":"VT","51":"VA","53":"WA","54":"WV","55":"WI","56":"WY","72":"PR",
}


def main() -> None:
    response = requests.get(URL, timeout=60)
    response.raise_for_status()
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    text_name = next(name for name in archive.namelist() if name.lower().endswith(".txt"))
    with archive.open(text_name) as handle:
        frame = pd.read_csv(handle, sep="|", dtype=str)
    frame.columns = [column.strip() for column in frame.columns]
    frame = frame.rename(columns={
        "GEOID": "fips", "USPS": "state_abbr", "NAME": "county_name",
        "INTPTLAT": "latitude", "INTPTLONG": "longitude", "ALAND_SQMI": "land_area_sqmi",
    })
    if "state_abbr" not in frame:
        frame["state_abbr"] = frame["fips"].str[:2].map(STATE_FIPS_TO_ABBR)
    keep = [column for column in ["fips", "state_abbr", "county_name", "latitude", "longitude", "land_area_sqmi"] if column in frame]
    frame = frame[keep].dropna(subset=["state_abbr", "latitude", "longitude"])
    destination = Path(__file__).resolve().parents[1] / "data" / "county_centroids.csv"
    frame.to_csv(destination, index=False)
    print(f"Wrote {len(frame):,} county records to {destination}")


if __name__ == "__main__":
    main()
