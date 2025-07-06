from wrappers import BikeLockersToronto


def init_live_url():
    blt = BikeLockersToronto(
        "toronto_lockers",
        "https://www.toronto.ca/services-payments/streets-parking-transportation/cycling-in-toronto/bicycle-parking/bicycle-lockers/locker-locations/",
    )
    last_updated = blt.last_updated
    gdf = blt.response_gdf

    print(last_updated)
    print(gdf.describe())
    breakpoint()


if __name__ == "__main__":
    init_live_url()
