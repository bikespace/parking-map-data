"""Functions for downstream processing of bicycle_parking data, e.g. data clustering and extracting city ref tags from OpenStreetMap features."""

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
        return ", ".join([f"{value} (n={count})" for value, count in items])
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
    else:
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


@pa.check_input(clustering_schema, "rings")
def group_proximate_rings(rings: gpd.GeoDataFrame, radius=5.0):
    """Converts geodataframe of bollards (ring and post) from the "street-furniture-bicycle-parking" dataset and aggregates (dissolves) by proximity if bollards are within 5m of each other.

    Parameters
    ----------
    rings: geopandas.GeoDataFrame
      Should only include bollards. CRS must be EPSG:32617 (UTM 17 N) to allow for DBSCAN clustering in metres.

    Returns
    -------
    gdf: geopandas.GeoDataFrame
    """

    # PART 1 - CALCULATE CLUSTERS

    # add quantity column (will be summed later)
    rings = rings.assign(quantity=1)

    # DBSCAN clustering
    coordinates = rings["geometry"].get_coordinates().values
    clusters = DBSCAN(eps=radius, min_samples=1).fit(coordinates)

    # Assign clusters back to GeoDataFrame
    rings = rings.assign(cluster=clusters.labels_)

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
    }

    # dissolve clusters
    rings = rings.dissolve(by="cluster", aggfunc=aggregations)

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
    return out_rings


@pa.check_input(clustering_schema, "racks")
def group_proximate_racks(racks, radius=30.0):
    """Takes geodataframe of bicycle racks from multiple city datasets and aggregates (dissolves) by proximity if racks are within 30m of each other.

    Parameters
    ----------
    racks: geopandas.GeoDataFrame
      Should only include racks. CRS must be EPSG:32617 (UTM 17 N) to allow for DBSCAN clustering in metres.

    Returns
    -------
    gdf: geopandas.GeoDataFrame
    """

    # PART 1 - DEFINE CLUSTERS

    # cluster points
    coordinates = racks["geometry"].get_coordinates().values
    clusters = DBSCAN(eps=30.0, min_samples=2).fit(coordinates)
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

    def combine_descriptions(mylist):
        mylist = [str(x) for x in mylist]
        blurb = f"MULTIPLE RACKS\nThis point is a combination of {len(mylist)} bicycle racks from multiple City of Toronto datasets. In many cases, these may be duplicate entries and there will be fewer than {len(mylist)} racks present."
        return "\n---\n".join([blurb, *mylist])

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
    }

    # dissolve clusters
    racks_clusters = racks_clusters.dissolve(by="cluster", aggfunc=aggregations)

    # get centroid and set as geometry
    racks_clusters["geometry"] = racks_clusters.centroid

    # combine racks
    racks_recombined = gpd.GeoDataFrame(
        pd.concat([racks_clusters, racks_singles])
    ).drop("cluster", axis=1)

    # convert back to WGS 84 lat/long and convert quantity to string
    out_racks = racks_recombined.astype({"quantity": "Int64"}).astype(
        {"quantity": "str"}
    )  # prevent float in string output
    return out_racks
