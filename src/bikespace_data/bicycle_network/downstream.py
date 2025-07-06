from sklearn.cluster import DBSCAN
import geopandas as gpd
import numpy as np
import pandas as pd


def group_proximate_rings(rings, radius=5.0):
    """Converts geodataframe of bollards (ring and post) from the "street-furniture-bicycle-parking" dataset and aggregates (dissolves) by proximity if bollards are within 5m of each other.

    Parameters
    ----------
    rings: geopandas.GeoDataFrame
      Should only include bollards.

    Returns
    -------
    gdf: geopandas.GeoDataFrame
    """

    # PART 1 - CALCULATE CLUSTERS

    # add quantity column (will be summed later)
    rings = rings.assign(quantity=1)

    # reproject to EPSG:32617 (WGS 84 / UTM zone 17N)
    # needed for DBSCAN clustering so unit can be in metres
    rings_UTM17N = rings.to_crs(32617)

    # DBSCAN clustering
    coordinates = rings_UTM17N["geometry"].get_coordinates().values
    clusters = DBSCAN(eps=radius, min_samples=1).fit(coordinates)

    # Assign clusters back to UTM17N GeoDataFrame
    rings_UTM17N = rings_UTM17N.assign(cluster=clusters.labels_)

    # PART 2 - AGGREGATE (DISSOLVE) BY CLUSTER

    # summarize frequency of value if more than one, otherwise return first value
    # replaces np.nan with "null"; np.unique doesn't seem to work otherwise
    def summarize_freq(mylist):
        mylist = mylist.replace("", "null").fillna("null")
        (values, counts) = np.unique(mylist, return_counts=True)
        pairs = list(zip(values, counts))
        if len(pairs) > 1:
            return "\n".join([f"{value} (n={count})" for value, count in pairs])
        else:
            return mylist.iloc[0]

    aggregations = {
        "source": "first",
        "amenity": "first",  # does not vary
        "bicycle_parking": "first",  # does not vary among subset
        "capacity": "sum",
        "operator": "first",  # does not vary
        "covered": summarize_freq,
        "access": summarize_freq,
        "fee": "first",  # does not vary
        "ref:open.toronto.ca:street-furniture-bicycle-parking:id": ";".join,
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
    rings_UTM17N = rings_UTM17N.dissolve(by="cluster", aggfunc=aggregations)

    # set "null" values back to np.nan
    rings_UTM17N = rings_UTM17N.replace("null", np.nan)

    # get centroid and set as geometry
    rings_UTM17N["cluster_centroid"] = rings_UTM17N.centroid
    rings_UTM17N = rings_UTM17N.drop("geometry", axis=1).rename(
        columns={"cluster_centroid": "geometry"}
    )

    # convert back to WGS 84 lat/long and convert quantity to string
    out_rings = (
        rings_UTM17N.to_crs(4326)
        .astype({"quantity": "Int64"})  # prevent float in string output
        .astype({"quantity": "str"})
    )

    return out_rings


def group_proximate_racks(racks, radius=30.0):
    """Takes geodataframe of bicycle racks from multiple city datasets and aggregates (dissolves) by proximity if racks are within 30m of each other.

    Parameters
    ----------
    racks: geopandas.GeoDataFrame
      Should only include racks.

    Returns
    -------
    gdf: geopandas.GeoDataFrame
    """

    # PART 1 - DEFINE CLUSTERS

    # change unit to meters instead of lat/long
    racks_UTM17N = racks.to_crs(32617)

    # cluster points
    coordinates = racks_UTM17N["geometry"].get_coordinates().values
    clusters = DBSCAN(eps=30.0, min_samples=2).fit(coordinates)
    racks_UTM17N = racks_UTM17N.assign(cluster=clusters.labels_)

    # split clusters from singles
    racks_UTM17N_clusters = racks_UTM17N[racks_UTM17N["cluster"] >= 0]
    racks_UTM17N_singles = racks_UTM17N[racks_UTM17N["cluster"] < 0]

    # remove clusters with only one data source
    sources_per_cluster = dict(
        racks_UTM17N_clusters[["cluster", "source"]]
        .groupby("cluster")["source"]
        .unique()
        .apply(lambda r: len(r))
    )
    sources_per_cluster_test = racks_UTM17N_clusters["cluster"].apply(
        lambda c: sources_per_cluster[c] > 1
    )
    return_to_singles = racks_UTM17N_clusters[~sources_per_cluster_test]
    racks_UTM17N_clusters = racks_UTM17N_clusters[sources_per_cluster_test]
    racks_UTM17N_singles = pd.concat([racks_UTM17N_singles, return_to_singles])

    # PART 2 - AGGREGATE (DISSOLVE) CLUSTERS

    def combine_descriptions(l):
        l = [str(x) for x in l]
        blurb = f"MULTIPLE RACKS\nThis point is a combination of {len(l)} bicycle racks from multiple City of Toronto datasets. In many cases, these may be duplicate entries and there will be fewer than {len(l)} racks present."
        return "\n---\n".join([blurb, *l])

    # format list: convert to text if needed, drop na's
    def flist(l):
        return " | ".join([str(x) for x in l.dropna().values])

    aggregations = {
        "source": lambda _: "city-multi",
        "amenity": "first",  # unique in dataset
        "bicycle_parking": "first",  # unique in subset
        "capacity": "min",  # most conservative number
        "operator": "first",  # unique in subset
        "covered": flist,  # debug
        "access": "first",  # unique in subset
        "fee": "first",  # unique in subset
        "start_date": flist,  # debug
        "length": flist,  # debug
        "description": combine_descriptions,  # debug
        "ref:open.toronto.ca:bicycle-parking-high-capacity-outdoor:id": flist,
        "ref:open.toronto.ca:bicycle-parking-racks:objectid": flist,
        "ref:open.toronto.ca:street-furniture-bicycle-parking:id": flist,
        "meta_borough": "first",  # unique per point
        "meta_ward_name": "first",  # unique per point
        "meta_ward_number": "first",  # unique per point
        "meta_source": "first",  # unique per point
        "meta_source_dataset": flist,
        "meta_source_url": flist,
        "meta_source_license": "first",  # does not vary
        "meta_source_license_url": "first",  # does not vary
        "meta_source_last_updated": flist,  # debug
        "seasonal": flist,  # debug
        "meta_status": flist,  # debug
        "meta_business_improvement_area": flist,  # debug
        "tmu": "first",  # unique per point
    }

    # dissolve clusters
    racks_UTM17N_clusters = racks_UTM17N_clusters.dissolve(
        by="cluster", aggfunc=aggregations
    )

    # get centroid and set as geometry
    racks_UTM17N_clusters["geometry"] = racks_UTM17N_clusters.centroid

    # combine racks
    racks_UTM17N_recombined = pd.concat(
        [racks_UTM17N_clusters, racks_UTM17N_singles]
    ).drop("cluster", axis=1)

    # convert back to WGS 84 lat/long and convert quantity to string
    out_racks = (
        racks_UTM17N_recombined.to_crs(4326)
        .astype({"quantity": "Int64"})  # prevent float in string output
        .astype({"quantity": "str"})
    )
    return out_racks


def drop_mapped_city_lockers(
    lockers: gpd.GeoDataFrame, osm: gpd.GeoDataFrame, radius: int = 200
) -> gpd.GeoDataFrame:
    """Radius is quite large because the City locations are not very precise"""
    osm_city_lockers = osm[
        osm["operator"].str.contains(r"city\s*?of\s*?toronto", case=False, regex=True)
        & (osm["bicycle_parking"] == "lockers")
    ][["geometry"]]
    osm_city_lockers_utm17n = osm_city_lockers.to_crs("EPSG:32617")
    osm_city_lockers_utm17n = osm_city_lockers_utm17n.set_geometry(
        osm_city_lockers_utm17n.centroid
    )
    lockers_utm17n = lockers.to_crs("EPSG:32617")
    joined = lockers_utm17n.sjoin_nearest(
        osm_city_lockers_utm17n,
        how="left",
        max_distance=radius,
    )
    lockers_unmapped_utm17n = joined[joined["index_right"].isna()].drop(
        columns=["index_right"]
    )
    lockers_unmapped = lockers_unmapped_utm17n.to_crs("EPSG:4326")
    return lockers_unmapped
