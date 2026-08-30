import urllib.request
import os

# Script to download the latest bike theft data from the City of Toronto's open data portal and save it as a GeoJSON file.
URL = "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/c7d34d9b-23d2-44fe-8b3b-cd82c8b38978/resource/e7fe6133-17d8-4a39-88af-352440dec684/download/bicycle-thefts%20-%204326.geojson"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "bicycle-thefts.geojson")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Downloading bike theft data from {URL}...")
    urllib.request.urlretrieve(URL, OUTPUT_FILE)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()