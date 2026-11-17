attributes = {
    "tts22_dest": "2022 TTS zone of destination",
    "mode_prime": "Primary travel mode of trip",
}

# code: description
code_table = {
    "tts22_dest": {
        "1001 - 1659": "Toronto",
        "2001 - 2334": "Durham",
        "3001 - 3565": "York",
        "4001 - 4753": "Peel",
        "5001 - 5488": "Halton",
        "6001 - 6265": "Hamilton",
        "11001 - 11503": "Niagara",
        "12001 - 12578": "Waterloo",
        "13001 - 13207": "Guelph",
        "14001 - 14080": "Wellington",
        "15001 - 15005": "Orangeville",
        "22001 - 22007": "Dufferin",
        "16001 - 16245": "Barrie",
        "17001 - 17313": "Simcoe",
        "21001 - 21008": "Orillia",
        "18001 - 18016": "Kawartha Lakes",
        "19001 - 19250": "Peterborough City",
        "20001 - 20116": "Peterborough",
        "23001 - 23050": "Brantford",
        "24001 - 24010": "Brant",
        "25001 - 25264": "Northumberland",
        "26001 - 26006": "Blue Mountains",
        "27001 - 27069": "Grey",
        "90001 - 90010": "External",
        "99998": "External Undefined",
        "99999": "Unknown",
    },
    "mode_prime": {
        "B": "Transit excluding GO rail",
        "C": "Cycle",
        "D": "Auto driver",
        "E": "E-scooter (2022)",
        "G": "GO rail only",
        "J": "Joint GO rail and local transit",
        "M": "Motorcycle",
        "O": "Other",
        "P": "Auto passenger",
        "S": "School bus",
        "T": "Taxi passenger",
        "U": "Paid rideshare (2016)",
        "W": "Walk",
        "9": "Unknown",
    },
}

_geometry_types = ["accs", "dest", "egrs", "emp", "hhld", "orig", "sch"]


geometry_match = {
    *{
        k: {"file": "2022_tts2006", "key": "tts2006"}
        for k in [f"gta06_{type}" for type in _geometry_types]
    },
    # mun_ TODO - extract from 2022_tts2022
    *{
        k: {"file": "2022_pd", "key": "pd_no"}
        for k in [f"pd_{type}" for type in _geometry_types]
    },
    # region_ TODO - extract from 2022_pd
    *{
        k: {"file": "2022_tts2022", "key": "tts2022"}
        for k in [f"tts22_{type}" for type in _geometry_types]
    },
    # ward_ TODO - extract from PDF
}
