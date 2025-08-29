"""Function for loading dataset info from JSON sources and related types."""

import json
from pathlib import Path
from typing import Required, TypedDict


class SourceDataset(TypedDict, total=False):
    dataset_name: Required[str]


class SourceDatasetTorontoOpenData(SourceDataset, total=False):
    resource_name: Required[str]


class SourceDatasetOpenStreetMap(SourceDataset, total=False):
    overpass_query: Required[str]


class SourceDatasetTorontoWeb(SourceDataset, total=False):
    url: Required[str]


class SourceProperties(TypedDict):
    url: str
    datasets: list[SourceDataset]


def load_paths(paths: dict[str, Path]) -> dict[str, SourceProperties]:
    data = {}
    for label, path in paths.items():
        with path.open() as f:
            item_data: SourceProperties = json.load(f)

        data: dict[str, SourceProperties] = data | {label: item_data}

    return data
