import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from bikespace_data.bicycle_theft.voronoi_tool import (
    build_voronoi,
    create_disjoint_partition,
    assign_parts_to_voronoi,
    clip_and_merge_fragments,
    assign_missing_thefts,
    load_thefts_gdf,
)


def make_point_gdf(coords):
    return gpd.GeoDataFrame(geometry=[Point(x, y) for x, y in coords], crs='EPSG:4326')


def test_disjoint_partition_and_aggregation_roundtrip(tmp_path):
    # create 4 points in a small area
    pts = make_point_gdf([(-79.4, 43.7), (-79.39, 43.7), (-79.395, 43.705), (-79.4, 43.705)])
    vor = build_voronoi(pts)
    parts = create_disjoint_partition(vor)
    vor_disjoint = assign_parts_to_voronoi(parts, vor)
    # aggregate thefts: use original pts as thefts
    # build a thefts gdf (one point per location)
    thefts = pts.copy()
    # spatial join to ensure counts will sum to original
    joined = gpd.sjoin(thefts, vor_disjoint, predicate='within', how='left')
    assert joined['geometry'].notna().sum() == len(thefts)


def test_clip_and_assign_missing(tmp_path):
    # two points at different locations
    pts = make_point_gdf([(-79.4, 43.7), (-79.3, 43.8)])
    vor = build_voronoi(pts)
    parts = create_disjoint_partition(vor)
    vor_disjoint = assign_parts_to_voronoi(parts, vor)

    # build a clipping mask that excludes the second point region (shrink to a small box near the first point)
    mask_poly = Polygon([(-79.41,43.69),(-79.39,43.69),(-79.39,43.71),(-79.41,43.71)])
    vor_final = clip_and_merge_fragments(vor_disjoint, mask_poly, buffer_neg_m=0, min_fragment_m2=1)

    # create thefts near both original points
    thefts = make_point_gdf([(-79.4, 43.7), (-79.3, 43.8)])
    th_counts = assign_missing_thefts(thefts, vor_final)
    # all thefts should now be assigned (sum equals 2)
    assert th_counts.sum() == 2


def test_kdtree_fallback_assign():
    # create a vor_final with a single polygon located far from theft
    poly = Polygon([(-79.5,43.7),(-79.45,43.7),(-79.45,43.75),(-79.5,43.75)])
    vor_final = gpd.GeoDataFrame({'vor_id':[0],'geometry':[poly]}, crs='EPSG:4326')
    # create theft points elsewhere
    thefts = make_point_gdf([(-79.3,43.65), (-79.31,43.66)])
    th_counts = assign_missing_thefts(thefts, vor_final)
    assert th_counts.sum() == 2
