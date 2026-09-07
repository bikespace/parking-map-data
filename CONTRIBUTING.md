# Contributing

## General notes

BikeSpace is primarily a project by volunteers from [Civic Tech Toronto](https://civictech.ca/) (CTTO). You can find us at CTTO meetups or in the CTTO Slack in #proj-bikeparking (the Slack join link is on the [CTTO homepage](https://civictech.ca/)). We expect contributors to follow the [CTTO code of conduct](https://civictech.ca/code-of-conduct).

You do not have to attend Civic Tech Toronto to contribute. However, if you have not discussed your intended change with us at a Civic Tech Toronto meetup or via our Slack channel, please create or comment on an issue _first_ before submitting a PR.

Development contributions should be made as a PR, approved by a reviewer, and then squash merged into `main`. 

You are welcome to use AI tools to help with development. However, we believe that successful changes involve discussion to ensure consensus on the project direction as well as human time spent to review ideas, plans, and PRs. Please ensure that you have tested your contributions and that you can explain any changes you would like to make. If needed, the volunteer maintainers may ask you to only submit one PR at a time or may close unsolicited PRs without comment.

## General how-to

You will need [uv installed](https://docs.astral.sh/uv/getting-started/installation/) to run the scripts.

Each dataset has a folder of scripts in `src/bikespace_data/` and a main script usually named `update_DATASET_NAME.py`. Dataset-specific tests are kept within each dataset folder, and tests for shared code are kept in `src/bikespace_data/tests/`. See section below for a more detailed explanation of common folder structures.

Other `src/bikespace_data/` folders are as follows:

- `resources/` for helper code to fetch data from external services (e.g. City of Toronto Open Data Portal)
- `utilities` for other tools used by multiple datasets, e.g. StatusManager and helper functions for working with GeoDataFrames.

The scripts are run on a schedule using the workflows in `.github/workflows`. The general flow is that the scripts will generate updated data files and then commit them to the `data` branch. This keeps a clear separation between production code (`main`) and the data outputs (`data`).

How to run tests (options are pre-configured in pyproject.toml):
```bash
# run all tests
$ uv run pytest

# show print output
$ uv run pytest -s

# run long-running tests
$ uv run pytest -m long -s
```


## Project structure and how it works

This repo functions as a [git scraper](https://simonwillison.net/2021/Mar/5/git-scraping/):

- The scripts to extract and transform data are saved in the `main` branch under `src/<dataset_name>`
- The scripts are run every day by a github action
- The scripts output is committed (saved) in the `data` branch into a `<dataset_name>/` output folder

Because of the way this set-up works, the scripts on the `main` branch generate an output folder that should not be committed to `main` but that cannot be gitignored (since the github action needs to make a temporary commit of the output data to cherry-pick it over to the `data` branch and save it there). See the section below for how to gitignore output folders locally.

There is also a [blog post with some additional explanation and tips](https://bikespacetoblog.wordpress.com/2025/12/10/tips-on-using-a-git-scraper-as-an-easy-data-pipeline/).

Having two main branches, `main` and `data`, helps with a couple things:

- Enable the right branch protection for each use case (e.g. approved PRs only to update `main` but the script is free to update `data` each day)
- Cleaner git history: commits on `main` only show source code changes and do not include data commits
- Documentation focused on each use case: `main` documentation is about how to work with the source code, and `data` branch documentation explains each dataset


## Ignoring output folders during development

To be able to run the scripts during development without having the output folder tracked by git, [add the output folder to your local `.git/info/exclude`](https://stackoverflow.com/questions/1753070/how-do-i-configure-git-to-ignore-some-files-locally).

You can also set up a test to run your main data update function using the [pytest tmp_path fixture](https://docs.pytest.org/en/stable/how-to/tmp_path.html) to test a script run without generating the output files into the working directory.


## Recommended structure

### `main` branch:

```
src/
  └── <dataset_name>/
      ├── README.md  # source code documentation
      ├── update_<dataset_name>.py
      └── tests/
```

You can add additional files and organization to your source code as needed.

### `data` branch:

In the existing datasets, you will generally encounter six types of files:

- Data user documentation (usually a README.md).
- Status files: these are used by `StatusManager` to record metadata and help with checking when the data was last updated.
- Source data files: the "raw" files received from e.g. an open data portal, though they may be sorted to improve git diffing. Saving source files ensures that the transformation output is reproducible and allows for transformations to be re-run later with improvements.
- Output files: an intermediate or end output intended for visibility or debugging.
- Display files: final output intended for users or another application. "Working" or extraneous columns are often excluded from these files for performance or to reduce confusion for users.
- Archive folders: these are point in time snapshots, usually in a highly compressed format like parquet. Archive folders allow for historical analysis without traversing the git history.

A simple file structure example for the `data` branch might look like:

```
<dataset_name>/
├── archive/  # saves weekly copies in YYYY-MM-DD named folders
├── README.md  # data user documentation
├── useful-data-source.geojson  # source file
├── useful-data-debug.geojson  # output file (often not needed for simple cases)
├── useful-data-display.geojson  # display file
└── useful-data-status.csv  # status file, can also go in a /statuses folder
```

For more complex cases (e.g. where there are multiple source, output, display, or status files), you can use directories instead:

```
<dataset_name>/
├── archive/  # saves weekly copies in YYYY-MM-DD named folders
├── README.md  # data user documentation
├── source_files/  
├── output_files/    # e.g. multiple source files
├── display_files/
├── statuses/
```


