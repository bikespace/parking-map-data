"""Functions for downstream processing of bicycle_parking data, e.g. data clustering and extracting city ref tags from OpenStreetMap features."""

import hashlib
from typing import Literal

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa
from pandera.engines.geopandas_engine import Geometry
from sklearn.cluster import DBSCAN


def summarize_freq(mylist: pd.Series):
    """Summarize frequency of value if more than one, otherwise return first value. pd.NA is treated as a unique value type and '' (blank string) and None are coerced to pd.NA."""
    mylist = mylist.replace({None: pd.NA, "": pd.NA})
    items = list(mylist.value_counts(dropna=False).items())
    if len(items) > 1:
        return ", ".join(
            [
                f"{pd.NA if pd.isna(value) else value} (n={count})"
                for value, count in items
            ]
        )
    else:
        return items[0][0]


def combine_list(mylist: pd.Series):
    """Combine values with ';' similar to OpenStreetMap tagging for multi-value fields. '' (blank string) and None are coerced to pd.NA. If all values are NA, then pd.NA is returned."""
    mylist = mylist.replace({None: pd.NA, "": pd.NA})
    if mylist.isna().all():
        return pd.NA
    return ";".join([str(x) for x in mylist.dropna().values])


def summarize_boolean(mylist: pd.Series, fill_value: Literal["yes", "no", None] = None):
    """Summarize fields that are expected to be primarily 'yes', 'no', or blank.

    '' (blank string) and None are coerced to pd.NA. NA values can be assumed to mean 'yes' or 'no' based on the value specified by fill_value; by default, NA values are not changed.

    Potential outputs:
    - all 'yes': 'yes'
    - all 'yes' with some pd.NA: 'probably yes'
    - all 'no': 'no'
    - all 'no' with some pd.NA: 'probably no'
    - some 'yes' and some 'no' (with or without pd.NA): 'maybe'
    - if there are any values other than 'yes', 'no', and pd.NA, then the output of summarize_freq is used instead
    """
    mylist = mylist.replace({None: pd.NA, "": pd.NA})
    if fill_value is not None:
        mylist = mylist.fillna(fill_value)

    if not mylist.isin(["yes", "no", pd.NA]).all():
        return summarize_freq(mylist)

    if mylist.eq("yes").all():
        return "yes"
    elif mylist.dropna().eq("yes").all():
        return "probably yes"
    elif mylist.eq("no").all():
        return "no"
    elif mylist.dropna().eq("no").all():
        return "probably no"
    elif mylist.eq("yes").any() and mylist.eq("no").any():
        return "maybe"
    else:  # pragma: no cover
        return summarize_freq(mylist)


def extract_ref_tags(gdf: gpd.GeoDataFrame, pattern: str) -> dict[str, list[str]]:
    """Extract all values where the column name matches the pattern and return a dict of the result. If multiple tag values are included in one entry and separated by a semicolon, these are split out into individual tags."""

    # get all instances of osm city ref tags and split out if needed
    id_lists: dict[str, list[str]] = {}
    id_cols = gdf.filter(regex=pattern, axis=1).dropna(how="all")
    for ref_type, tags in id_cols.items():
        id_list = []
        for tag_str in tags.dropna():
            tags = str(tag_str).split(";")
            id_list.extend([tag.strip() for tag in tags])

        id_lists.setdefault(str(ref_type), [])
        id_lists[str(ref_type)].extend(id_list)

    return id_lists


clustering_schema = pa.DataFrameSchema(
    {
        "geometry": pa.Column(Geometry(crs="EPSG:32617")),  # UTM 17 N
    }
)

# City of Toronto source reference id columns, in lookup priority order.
# `ring_ref_columns` is a subset since bollards only ever come from one dataset.
ring_ref_columns = ["ref:open.toronto.ca:street-furniture-bicycle-parking:id"]
rack_ref_columns = [
    "ref:open.toronto.ca:street-furniture-bicycle-parking:id",
    "ref:open.toronto.ca:bicycle-parking-high-capacity-outdoor:id",
    "ref:open.toronto.ca:bicycle-parking-racks:objectid",
]


def get_member_ref_id(row: pd.Series, ref_columns: list[str]) -> str:
    """Return a stable identifier for an individual (pre-cluster) parking feature row.

    Checks `ref_columns` in priority order and returns the first non-null source reference
    id found; if none of the row's source datasets provide one, falls back to a key derived
    from its rounded coordinates. This mirrors the two-tier priority the frontend's
    `parkingFeatureKey()` (bikespace_frontend/src/utils/map-utils/matchSubmissionsToParking.ts)
    already uses, so the pipeline and the UI identify the same row the same way.
    """
    for col in ref_columns:
        if col in row.index and pd.notna(row[col]):
            return str(row[col])
    x, y = row.geometry.x, row.geometry.y
    return f"{round(x, 6)},{round(y, 6)}"


def _assign_cluster_ids(
    gdf: gpd.GeoDataFrame,
    ref_columns: list[str],
    cluster_col: str = "cluster",
) -> tuple[gpd.GeoDataFrame, dict[str, str]]:
    """Assign a `meta_cluster_id` to every row belonging to a DBSCAN cluster label with 2+ members.

    The id is a short hash of the sorted member reference ids (see `get_member_ref_id`), so it's
    deterministic and stable across pipeline re-runs as long as cluster membership doesn't change.
    Rows whose cluster label only has 1 member (not an actual merge) get `pd.NA`.

    Returns
    -------
    gdf: GeoDataFrame, same rows/order as input, with a new `meta_cluster_id` column added
    ref_id_to_cluster_id: dict mapping each clustered member's own reference id (from
      `get_member_ref_id`) to its `meta_cluster_id`, so pre-dissolve individual records elsewhere
      (e.g. `open_toronto_ca_unclustered.geojson`) can be tagged with the same id.
    """
    ref_ids = gdf.apply(lambda row: get_member_ref_id(row, ref_columns), axis=1)
    group_sizes = gdf.groupby(cluster_col)[cluster_col].transform("size")

    cluster_ids_by_label = {
        label: hashlib.md5(
            "|".join(sorted(ref_ids[gdf[cluster_col] == label])).encode()
        ).hexdigest()[:12]
        for label in gdf.loc[group_sizes >= 2, cluster_col].unique()
    }

    gdf = gdf.assign(meta_cluster_id=gdf[cluster_col].map(cluster_ids_by_label))

    ref_id_to_cluster_id = {
        ref_id: cluster_ids_by_label[label]
        for ref_id, label, size in zip(ref_ids, gdf[cluster_col], group_sizes)
        if size >= 2
    }

    return gdf, ref_id_to_cluster_id


@pa.check_input(clustering_schema, "rings")
def group_proximate_rings(
    rings: gpd.GeoDataFrame,
    radius: float = 5.0,
) -> tuple[gpd.GeoDataFrame, dict[str, str]]:
    """Converts geodataframe of bollards (ring and post) from the "street-furniture-bicycle-parking" dataset and aggregates (dissolves) by proximity if bollards are within 5m of each other.

    Parameters
    ----------
    rings: geopandas.GeoDataFrame
      Should only include bollards. CRS must be EPSG:32617 (UTM 17 N) to allow for DBSCAN clustering in metres.

    Returns
    -------
    gdf: geopandas.GeoDataFrame
    member_cluster_ids: dict mapping each clustered member's reference id (see `get_member_ref_id`)
      to its `meta_cluster_id`, for tagging the pre-dissolve individual records elsewhere.
    """

    # do not process if input dataframe is empty
    if len(rings) == 0:
        return rings, {}

    # PART 1 - CALCULATE CLUSTERS

    # add quantity column (will be summed later)
    rings = rings.assign(quantity=1)

    # DBSCAN clustering
    coordinates = rings["geometry"].get_coordinates().values
    clusters = DBSCAN(eps=radius, min_samples=1).fit(coordinates)

    # Assign clusters back to GeoDataFrame
    rings = rings.assign(cluster=clusters.labels_)

    # tag rows that are part of an actual (2+ member) cluster with a shared meta_cluster_id
    rings, member_cluster_ids = _assign_cluster_ids(
        rings, ring_ref_columns, cluster_col="cluster"
    )

    # PART 2 - AGGREGATE (DISSOLVE) BY CLUSTER

    aggregations = {
        "amenity": "first",  # does not vary
        "bicycle_parking": "first",  # does not vary among subset
        "capacity": "sum",
        "operator": "first",  # does not vary
        "covered": summarize_boolean,
        "access": summarize_freq,
        "fee": "first",  # does not vary
        "ref:open.toronto.ca:street-furniture-bicycle-parking:id": combine_list,
        "meta_status": "first",  # does not vary
        "meta_business_improvement_area": summarize_freq,
        "meta_ward_name": summarize_freq,
        "meta_ward_number": summarize_freq,
        "meta_source": "first",  # does not vary
        "meta_source_dataset": "first",  # does not vary
        "meta_source_url": "first",  # does not vary
        "meta_source_license": "first",  # does not vary
        "meta_source_license_url": "first",  # does not vary
        "meta_source_last_updated": "first",  # does not vary
        "quantity": "sum",
        "meta_cluster_id": "first",  # constant within a cluster
    }

    applied_aggregations = {
        k: v for (k, v) in aggregations.items() if k in rings.columns
    }

    # dissolve clusters
    rings = rings.dissolve(by="cluster", aggfunc=applied_aggregations)

    # set "null" values back to pd.NA
    rings = rings.replace("null", pd.NA)

    # get centroid and set as geometry
    rings["cluster_centroid"] = rings.centroid
    rings = rings.drop("geometry", axis=1).rename(
        columns={"cluster_centroid": "geometry"}
    )

    # convert quantity to string
    out_rings = rings.astype({"quantity": "Int64"}).astype(
        {"quantity": "str"}
    )  # prevent float in string output
    return out_rings, member_cluster_ids


def combine_descriptions(mylist: list[str]) -> str:
    mylist = [str(x) for x in mylist]
    blurb = f"MULTIPLE RACKS\nThis point is a combination of {len(mylist)} bicycle racks from multiple City of Toronto datasets. In many cases, these may be duplicate entries and there will be fewer than {len(mylist)} racks present."
    return "\n---\n".join([blurb, *mylist])


@pa.check_input(clustering_schema, "racks")
def group_proximate_racks(
    racks: gpd.GeoDataFrame,
    radius: float = 30.0,
) -> tuple[gpd.GeoDataFrame, dict[str, str]]:
    """Takes geodataframe of bicycle racks from multiple city datasets and aggregates (dissolves) by proximity if racks are within 30m of each other.

    Parameters
    ----------
    racks: geopandas.GeoDataFrame
      Should only include racks. CRS must be EPSG:32617 (UTM 17 N) to allow for DBSCAN clustering in metres.

    Returns
    -------
    gdf: geopandas.GeoDataFrame
    member_cluster_ids: dict mapping each clustered member's reference id (see `get_member_ref_id`)
      to its `meta_cluster_id`, for tagging the pre-dissolve individual records elsewhere.
    """

    # do not process if input dataframe is empty
    if len(racks) == 0:
        return racks, {}

    # PART 1 - DEFINE CLUSTERS

    # cluster points
    coordinates = racks["geometry"].get_coordinates().values
    clusters = DBSCAN(eps=radius, min_samples=2).fit(coordinates)
    racks = racks.assign(cluster=clusters.labels_)

    # split clusters from singles
    racks_clusters = racks[racks["cluster"] >= 0]
    racks_singles = racks[racks["cluster"] < 0]

    # remove clusters with only one data source
    sources_per_cluster = dict(
        racks_clusters[["cluster", "meta_source_dataset"]]
        .groupby("cluster")["meta_source_dataset"]
        .unique()
        .apply(lambda r: len(r))
    )
    sources_per_cluster_test = racks_clusters["cluster"].apply(
        lambda c: sources_per_cluster[c] > 1
    )
    return_to_singles = racks_clusters[~sources_per_cluster_test]
    racks_clusters = racks_clusters[sources_per_cluster_test]
    racks_singles = gpd.GeoDataFrame(pd.concat([racks_singles, return_to_singles]))

    # PART 2 - AGGREGATE (DISSOLVE) CLUSTERS

    # skip if no clusters were found
    member_cluster_ids: dict[str, str] = {}
    if len(racks_clusters) > 0:
        # tag rows that are part of an actual (2+ member) cluster with a shared meta_cluster_id
        racks_clusters, member_cluster_ids = _assign_cluster_ids(
            racks_clusters, rack_ref_columns, cluster_col="cluster"
        )

        aggregations = {
            "amenity": "first",  # unique in dataset
            "bicycle_parking": "first",  # unique in subset
            "capacity": "min",  # most conservative number
            "operator": "first",  # unique in subset
            "covered": summarize_boolean,  # debug
            "access": "first",  # unique in subset
            "fee": "first",  # unique in subset
            "start_date": summarize_freq,  # debug
            "length": summarize_freq,  # debug
            "description": combine_descriptions,  # debug
            "ref:open.toronto.ca:bicycle-parking-high-capacity-outdoor:id": combine_list,
            "ref:open.toronto.ca:bicycle-parking-racks:objectid": combine_list,
            "ref:open.toronto.ca:street-furniture-bicycle-parking:id": combine_list,
            "meta_borough": "first",  # unique per point
            "meta_ward_name": "first",  # unique per point
            "meta_ward_number": "first",  # unique per point
            "meta_source": "first",  # unique per point
            "meta_source_dataset": summarize_freq,
            "meta_source_url": summarize_freq,
            "meta_source_license": "first",  # does not vary
            "meta_source_license_url": "first",  # does not vary
            "meta_source_last_updated": summarize_freq,  # debug
            "seasonal": summarize_freq,  # debug
            "meta_status": summarize_freq,  # debug
            "meta_business_improvement_area": summarize_freq,  # debug
            "meta_cluster_id": "first",  # constant within a cluster
        }

        applied_aggregations = {
            k: v for (k, v) in aggregations.items() if k in racks_clusters.columns
        }

        # dissolve clusters
        racks_clusters = racks_clusters.dissolve(
            by="cluster",
            aggfunc=applied_aggregations,
        )

        # get centroid and set as geometry
        racks_clusters["geometry"] = racks_clusters.centroid

    # ensure singles carry the same column (as pd.NA) so concat doesn't lose it
    racks_singles = racks_singles.assign(meta_cluster_id=pd.NA)

    # combine racks
    racks_recombined = gpd.GeoDataFrame(
        pd.concat([racks_clusters, racks_singles])
    ).drop("cluster", axis=1)

    return racks_recombined, member_cluster_ids
