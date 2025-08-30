import marimo

__generated_with = "0.15.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    # Spatial Filtering Analysis

    ## Background from the Project Board

    Current de-duplication has some failure cases:

    - Failure case A: City bike rings in OpenStreetMap that do not have an operator tag like "City of Toronto" - these are currently retained even if they are obvious duplicates of features from the City dataset.
    - Failure case B: Bike parking from OpenStreetMap with with an operator like "City of Toronto" that is not contained within the City datasets (e.g. not yet added, bike parking in parks, etc.) - these are currently removed even if there is no nearby feature from the city data (unless they've been tagged with `ref:open.toronto.ca=no`)

    ## Suggested solutions

    Suggested solution for failure case A:

    - Only check OSM features which are likely to be bike rings (e.g. include only `bicycle_parking=` `bollard`, `stands`, and no `bicycle_parking` tag at all)
    - Spatial join with City street furniture dataset with 5m buffer (excluding racks but keeping `bollard` and no type tag)
    - Any OSM features with a successful join should be excluded

    5m aligns with the distance used for ring de-duplication; this approach improves data quality while avoiding user-noticeable false positive matches. Geolocation for city rings data generally appears to be accurate to 1-2m.

    Suggested solution for failure case B (this logic can be integrated with the current operator match exclusion filter):

    - Check OSM features with an operator like "City of Toronto"
    - Spatial join with all city datasets with 30m buffer
    - Any OSM features without a successful join should be retained; otherwise features are removed

    30m aligns with the distance used for rack clustering and the City of Toronto maximum zoning distance between an entrance and zoning-credited bicycle parking. This should prevent false negatives where the city data location is based on address geolocation and is therefore less precise.
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Set Up""")
    return


@app.cell
def _():
    import marimo as mo
    import geopandas as gpd
    import pandas as pd
    import numpy as np
    return gpd, mo, np, pd


@app.cell
def _(gpd, pd):
    # get data
    city_unclustered_url = "https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/bicycle_parking/display_files/open_toronto_ca_unclustered.geojson"
    osm_url = "https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/bicycle_parking/display_files/openstreetmap.geojson"

    city_unclustered = gpd.read_file(city_unclustered_url)
    osm = gpd.read_file(osm_url)
    all_sources = gpd.GeoDataFrame(
        pd.concat([city_unclustered, osm], ignore_index=True)
    )
    return all_sources, city_unclustered, osm


@app.cell
def _():
    # reduce extraneous columns
    useful_cols = [
        "bicycle_parking",
        "capacity",
        "operator",
        "access",
        "description",
        "ref:open.toronto.ca:bicycle-parking-bike-stations-indoor:id",
        "ref:open.toronto.ca:bicycle-parking-high-capacity-outdoor:id",
        "ref:open.toronto.ca:bicycle-parking-racks:objectid",
        "ref:open.toronto.ca:street-furniture-bicycle-parking:id",
        "meta_source",
        "geometry",
    ]

    useful_cols_city = [
        "meta_source_dataset",
    ]

    useful_cols_osm = ["quantity", "note", "ref:open.toronto.ca", "meta_osm_id"]

    useful_cols_all = [
        *useful_cols,
        *useful_cols_city,
        *useful_cols_osm,
    ]
    return useful_cols, useful_cols_all, useful_cols_city, useful_cols_osm


@app.cell
def _(
    all_sources,
    city_unclustered,
    osm,
    useful_cols,
    useful_cols_all,
    useful_cols_city,
    useful_cols_osm,
):
    # convert to projected CRS to do joins in metres
    utm_17_n = "EPSG:32617"
    wgs_84 = "EPSG:4326"

    city_utm = city_unclustered[[*useful_cols, *useful_cols_city]].to_crs(utm_17_n)
    osm_utm = osm[[*useful_cols, *useful_cols_osm]].to_crs(utm_17_n)
    all_utm = all_sources[useful_cols_all].to_crs(utm_17_n)
    return city_utm, osm_utm


@app.cell
def _(osm_utm):
    # add the other drop attributes to the osm data
    osm_utm_attr = osm_utm.assign(
        _osm_operator_city=lambda df: (
            df["operator"].str.contains(
                r"city\s*?of\s*?toronto",
                case=False,
                regex=True,
                na=False,
            )
        ),
        _osm_has_ref=lambda df: (
            df.filter(
                regex=r"ref:(open\.)?toronto\.ca",
                axis=1,
            )
            .notna()
            .any(axis=1)
        ),
        _osm_drop_operator_city=lambda df: (
            (df["_osm_operator_city"]) & (~df["_osm_has_ref"])
        ),
    )
    return (osm_utm_attr,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""## Spatial Filter 1: OSM features that are likely a ring & post and within 5m of a likely City ring & post"""
    )
    return


@app.cell
def _(city_utm, osm_utm_attr):
    osm_city_5m_join = osm_utm_attr.sjoin_nearest(
        city_utm[~city_utm["bicycle_parking"].eq("rack")],
        how="left",
        max_distance=5,
        distance_col="distance",
    )
    return (osm_city_5m_join,)


@app.cell
def _(osm_city_5m_join):
    osm_city_5m_join
    return


@app.cell(hide_code=True)
def _(mo, osm_city_5m_join):
    mo.md(
        f"""
    ### Some questions about the joined data

    Spatial match results:

    - Total: {len(osm_city_5m_join[~osm_city_5m_join.index.duplicated()]):,}
    - No spatial match: {
            len(
                osm_city_5m_join[
                    osm_city_5m_join["distance"].isna()
                    & ~osm_city_5m_join.index.duplicated()
                ]
            ):,}
    - Spatial match: {
            len(
                osm_city_5m_join[
                    ~osm_city_5m_join["distance"].isna()
                    & ~osm_city_5m_join.index.duplicated()
                ]
            )
        }

    How many additional points would get filtered out?

    - **Additional filtered out: {
            len(
                osm_city_5m_join[
                    ~osm_city_5m_join.index.duplicated()
                    & ~osm_city_5m_join["distance"].isna()
                    & ~osm_city_5m_join["_osm_has_ref"]
                    & ~osm_city_5m_join["_osm_drop_operator_city"]
                    & (
                        osm_city_5m_join["bicycle_parking_left"].isin(
                            ["bollard", "stands"]
                        )
                        | osm_city_5m_join["bicycle_parking_left"].isna()
                    )
                ]
            )
        }** (bicycle_parking=bollard/stands/NA, not already dropped from Operator, not already kept from ref)
    - Spatial match already filtered out: {
            len(
                osm_city_5m_join[
                    ~osm_city_5m_join.index.duplicated()
                    & (~osm_city_5m_join["distance"].isna())
                    & osm_city_5m_join["_osm_drop_operator_city"]
                ]
            )
        }
    - Spatial match kept via ref check: {
            len(
                osm_city_5m_join[
                    ~osm_city_5m_join.index.duplicated()
                    & osm_city_5m_join["_osm_has_ref"]
                    & (~osm_city_5m_join["distance"].isna())
                ]
            )
        }
    - Not filtered because the OSM feature is not bollard, stands, or NA: {
            len(
                osm_city_5m_join[
                    ~osm_city_5m_join.index.duplicated()
                    & (~osm_city_5m_join["distance"].isna())
                    & ~osm_city_5m_join["_osm_has_ref"]
                    & (~osm_city_5m_join["_osm_drop_operator_city"])
                    & ~(
                        osm_city_5m_join["bicycle_parking_left"].isin(
                            ["bollard", "stands"]
                        )
                        | osm_city_5m_join["bicycle_parking_left"].isna()
                    )
                ]
            )
        }
    """
    )
    return


@app.cell(hide_code=True)
def _(mo, osm_city_5m_join):
    mo.md(
        rf"""
    ### Does the data have any duplicates?

    From the [documentation](https://geopandas.org/en/latest/docs/reference/api/geopandas.GeoDataFrame.sjoin_nearest.html): "Results will include multiple output records for a single input record where there are multiple equidistant nearest or intersected neighbors."

    Number of duplicate rows: {len(osm_city_5m_join[osm_city_5m_join.index.duplicated(keep=False)])}

    **Recommendation is to remove duplicates like so before additional processing:** (Although strictly speaking, since the final check is done on an index match, it doesn't matter...)

    ```python
    osm_city_5m_join[~osm_city_5m_join.index.duplicated()]
    ```
    """
    )
    return


@app.cell
def _(osm_city_5m_join):
    # show duplicates
    osm_city_5m_join[osm_city_5m_join.index.duplicated(keep=False)]
    return


@app.cell
def _(np, osm_city_5m_join, osm_utm):
    # recommended approach and result
    # use join query from beginning of section; only include fields used there and below

    filter_out = osm_city_5m_join[
        ~osm_city_5m_join.index.duplicated()
        & ~osm_city_5m_join["distance"].isna()
        & ~osm_city_5m_join["_osm_has_ref"]
        & ~osm_city_5m_join["_osm_drop_operator_city"]
        & (
            osm_city_5m_join["bicycle_parking_left"].isin(["bollard", "stands"])
            | osm_city_5m_join["bicycle_parking_left"].isna()
        )
    ]

    index_match = osm_utm.index.isin(filter_out.index)
    np.unique(index_match, return_counts=True)
    return (filter_out,)


@app.cell
def _(city_utm, filter_out):
    # interactive map of additional filtered out points
    m = city_utm.explore(color="blue")
    filter_out.explore(color="red", m=m, marker_kwds={"radius": 5})
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""## Spatial Filter 2: OSM Features with City Operator that are not within 30m of a City feature"""
    )
    return


@app.cell
def _(city_utm, osm_utm_attr):
    osm_city_30m_join = osm_utm_attr.sjoin_nearest(
        city_utm,
        how="left",
        max_distance=30,
        distance_col="distance",
    )
    return (osm_city_30m_join,)


@app.cell
def _(osm_city_30m_join):
    osm_city_30m_join
    return


@app.cell(hide_code=True)
def _(mo, osm_city_30m_join):
    mo.md(
        rf"""
    ### Some questions about the joined data

    Spatial match results:

    - Total: {len(osm_city_30m_join[~osm_city_30m_join.index.duplicated()]):,}
    - No spatial match: {
            len(
                osm_city_30m_join[
                    osm_city_30m_join["distance"].isna()
                    & ~osm_city_30m_join.index.duplicated()
                ]
            ):,}
    - Spatial match: {
            len(
                osm_city_30m_join[
                    ~osm_city_30m_join["distance"].isna()
                    & ~osm_city_30m_join.index.duplicated()
                ]
            ):,}

    How many additional points would get retained?

    - **Additional retained: {
            len(
                osm_city_30m_join[
                    ~osm_city_30m_join.index.duplicated()
                    & osm_city_30m_join["distance"].isna()
                    & osm_city_30m_join["_osm_operator_city"]
                    & ~osm_city_30m_join["_osm_has_ref"]
                ]
            ):,}** (no spatial match, operator like City of Toronto, no ref)
    - Already retained due to ref tag: {
            len(
                osm_city_30m_join[
                    ~osm_city_30m_join.index.duplicated()
                    & osm_city_30m_join["distance"].isna()
                    & osm_city_30m_join["_osm_operator_city"]
                    & osm_city_30m_join["_osm_has_ref"]
                ]
            ):,}
    - Already retained due to operator not like City of Toronto: {
            len(
                osm_city_30m_join[
                    ~osm_city_30m_join.index.duplicated()
                    & osm_city_30m_join["distance"].isna()
                    & ~osm_city_30m_join["_osm_operator_city"]
                ]
            ):,}
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ### Some Additional Notes

    It's clear from the interactive map that these are all lockers right now (which is mostly a function of me being too lazy to load them in too...)
    """
    )
    return


@app.cell
def _(osm_utm_attr):
    # are there any non-ref city datapoints that aren't lockers?

    len(
        osm_utm_attr[
            osm_utm_attr["_osm_operator_city"]
            & ~osm_utm_attr["_osm_has_ref"]
            & ~osm_utm_attr["bicycle_parking"].eq("lockers")
        ]
    )
    return


@app.cell
def _(osm_utm_attr):
    # how many datapoints are currently tagged ref:open.toronto.ca:no?

    osm_utm_attr
    return


@app.cell
def _(osm_city_30m_join):
    # how many ref:open.toronto.ca:no would get pulled with the spatial inclusion?

    osm_city_30m_join
    return


@app.cell(hide_code=True)
def _(mo, osm_city_30m_join):
    mo.md(
        rf"""
    ### Does the data have any duplicates?

    From the [documentation](https://geopandas.org/en/latest/docs/reference/api/geopandas.GeoDataFrame.sjoin_nearest.html): "Results will include multiple output records for a single input record where there are multiple equidistant nearest or intersected neighbors."

    Number of duplicate rows: {len(osm_city_30m_join[osm_city_30m_join.index.duplicated(keep=False)])}

    **Recommendation is to remove duplicates like so before additional processing:** (Although strictly speaking, since the final check is done on an index match, it doesn't matter...)

    ```python
    osm_city_30m_join[~osm_city_30m_join.index.duplicated()]
    ```
    """
    )
    return


@app.cell
def _(osm_city_30m_join):
    # show duplicates
    osm_city_30m_join[osm_city_30m_join.index.duplicated(keep=False)]
    return


@app.cell
def _(np, osm_city_30m_join, osm_utm):
    # recommended approach and result
    # use join query from beginning of section; only include fields used there and below
    # at the moment, this won't add anything, but it will catch features added by other mappers with operator like City of Toronto and might allow removal of ref:open.toronto.ca=no tags in many cases (e.g. for lifecycle purposes)

    retain = osm_city_30m_join[
        ~osm_city_30m_join.index.duplicated()
        & osm_city_30m_join["distance"].isna()
        & osm_city_30m_join["_osm_operator_city"]
        & ~osm_city_30m_join["_osm_has_ref"]
    ]

    index_match_retain = osm_utm.index.isin(retain.index)
    np.unique(index_match_retain, return_counts=True)
    return (retain,)


@app.cell
def _(city_utm, retain):
    # interactive map of results
    m1 = city_utm.explore(color="blue")
    retain.explore(color="red", m=m1, marker_kwds={"radius": 5})
    return


if __name__ == "__main__":
    app.run()
