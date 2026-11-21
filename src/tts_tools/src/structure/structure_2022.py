from pathlib import Path
from typing import cast

from tts_tools.src.types import CodeLookupDirect

from .code_table_2022 import code_table

_geometry_types = ["accs", "dest", "egrs", "emp", "hhld", "orig", "sch"]


# TODO convert this to a function instead?
geometry_match = {
    # gta06
    **{
        k: {
            "file": Path("src/tts_tools/src/boundaries/processed/2022_tts2006.geojson"),
            "key": "tts2006",
        }
        for k in [f"gta06_{type}" for type in _geometry_types]
    },
    # mun_ TODO - extract from 2022_tts2022
    # pd
    **{
        k: {
            "file": Path("src/tts_tools/src/boundaries/processed/2022_pd.geojson"),
            "key": "pd_no",
        }
        for k in [f"pd_{type}" for type in _geometry_types]
    },
    # region_ TODO - extract from 2022_pd
    # tts
    **{
        k: {
            "file": Path("src/tts_tools/src/boundaries/processed/2022_tts2022.geojson"),
            "key": "tts2022",
        }
        for k in [f"tts22_{type}" for type in _geometry_types]
    },
    # ward_ TODO - extract from PDF
}


# ward - this is not an available query output


# TODO should this return a closure?
def description_to_code(column, description):
    """Docstring TODO"""

    if column in [f"gta06_{type}" for type in _geometry_types]:
        raise ValueError("gta06 is not yet implemented")

    elif column in [f"mun_{type}" for type in _geometry_types]:
        raise ValueError("mun is not yet implemented")

    elif column in [f"pd_{type}" for type in _geometry_types]:
        # direct lookup
        raise ValueError("pd is not yet implemented")

    elif column in [f"region_{type}" for type in _geometry_types]:
        raise ValueError("region is not yet implemented")

    elif column in [f"tts22_{type}" for type in _geometry_types]:
        try:
            code = int(description)
            return code
        except ValueError, TypeError:
            if description == "External Undefined":
                return 99998
            elif description == "Unknown":
                return 99999
            else:
                raise ValueError(
                    f"Unable to convert {description} to a tts 2022 zone number"
                )

    elif column == "mode_prime":
        lookup = code_table.get(column)
        if lookup:
            lookup_results = [l for l in lookup if l["description"] == description]
            if not lookup_results:
                raise ValueError(
                    f"Unable to find description to code conversion for mode_prime: {description}"
                )
            if len(lookup_results) > 1:
                raise ValueError(
                    f"Found multiple description to code conversions for mode_prime: {description}"
                )
            lookup_result = cast(CodeLookupDirect, lookup_results[0])
            return lookup_result["code"]
        else:
            raise ValueError(
                f"Unable to find description to code conversion lookup table for {column}."
            )


def code_to_description(column, code):
    """Docstring TODO"""

    pass


attributes = {
    "region_hhld": "Regional municipality of household",
    "pd_hhld": "Planning district of household",
    "ward_hhld": "Ward number of household",
    "gta06_hhld": "2006 GTA zone of household",
    "tts22_hhld": "2022 TTS zone of household",
    "ggh4_hhld": "GGHM V4 zone of household",
    "ggh5_hhld": "GGHM V5 zone of household",
    "sampletype": "Type of sample",
    "surveymethod": "Survey method",
    "rec_mail": "Receipt of advance letter",
    "dwell_type": "Type of dwelling unit",
    "income": "Income range of household",
    "hhbornincanada": "Household born in Canada",
    "hhstructure": "Household structure",
    "n_person": "No. of persons in household",
    "n_adult": "No. of adults (aged 18+) in household",
    "n_child": "No. of children (aged 0-17) in household",
    "n_senior": "No. of seniors (aged 65+) in household (65+ y.o.)",
    "n_vehicle": "No. of vehicles in household",
    "n_licence": "No. of drivers in household",
    "n_tranpass": "No. of persons with transit pass",
    "n_emp_tot": "No. of employed in household",
    "n_emp_ft": "No. of F/T employed people in household",
    "n_emp_pt": "No. of P/T employed people in household",
    "n_emp_home": "No. of employed people in household who exclusively work from home",
    "n_emp_hft": "No. of F/T employed people in household who exclusively work from home",
    "n_emp_hpt": "No. of P/T employed people in household who exclusively work from home",
    "n_student": "No. of students in household",
    "n_stu_k12": "No. of students in K12 schools in household",
    "n_stu_pse": "No. of students in post-secondary schools in household",
    "trip_day": "Day of the week trips were made",
    "trip_week": "Weeks into the survey when trips were made",
    "trip_period": "Trip period",
    "n_pers11up": "No. of people aged 11+",
    "n_hh11_trip": "No. of trips made by people aged 11+",
    "n_hhld_trip2016": "No. of trips made by household based on 2016 criteria",
    "n_pers5up": "No. of people aged 5+",
    "n_hhld_trip": "No. of trips made by household",
    "n_hdrvr_trip": "No. of driver trips made by household",
    "n_hpsgr_trip": "No. of passenger trips made by household",
    "n_htran_trip": "No. of transit trips made by household",
    "n_hgotr_trip": "No. of GO train only trips made by household",
    "n_hjgot_trip": "No. of joint GO train and other transit trips made by household",
    "n_hloct_trip": "No. of local transit only trips made by household",
    "n_hbike_trip": "No. of cycling or electric micromobility trips made by household",
    "n_hwalk_trip": "No. of walking trips made by household",
    "n_hothm_trip": "No. of trips of other mode made by household",
    "respond": "Respondent",
    "age": "Age of person",
    "age_range": "Age range of person",
    "sex": "Gender of person",
    "sex_orig": "Survey response to the Gender question",
    "ethnicity": "Ethnicity of person",
    "immigration": "Immigration year if applicable",
    "driver_lic": "Possess driver's licence",
    "tran_pass": "Possess a transit pass",
    "emp_stat": "Employment status of person",
    "occstat": "Occupation status",
    "occupation2022": "2022 Occupation type",
    "occupation": "Occupation type",
    "workplace": "Workplace location type",
    "free_park": "Free Parking at work",
    "no_work": "Worked from home on survey day",
    "region_emp": "Regional municipality of employment",
    "pd_emp": "Planning district of employment",
    "ward_emp": "Ward number of employment",
    "gta06_emp": "2006 GTA zone of employment",
    "tts22_emp": "2022 TTS zone of employment",
    "ggh4_emp": "GGHM V4 zone of employment",
    "ggh5_emp": "GGHM V5 zone of employment",
    "stu_stat": "Student status of person",
    "sch_code": "School code",
    "region_sch": "Regional municipality of school",
    "pd_sch": "Planning district of school",
    "ward_sch": "Ward number of school",
    "gta06_sch": "2006 GTA zone of school",
    "tts22_sch": "2022 TTS zone of school",
    "ggh4_sch": "GGHM V4 zone of school",
    "ggh5_sch": "GGHM V5 zone of school",
    "workcommute": "Commuted for work last week",
    "n_wcommdays": "Number of weekdays commuted for work last week",
    "wrkcmon": "Commuted for work last Monday",
    "wrkctue": "Commuted for work last Tuesday",
    "wrkcwed": "Commuted for work last Wednesday",
    "wrkcthu": "Commuted for work last Thursday",
    "wrkcfri": "Commuted for work last Friday",
    "wcomm_lastwk": "Days which commuted for work last week",
    "madetrips": "Made any trips on survey day",
    "work_trip": "Made work trip on survey day",
    "sch_trip": "Made school trip on survey day",
    "n_pers_trip": "No. of trips made by person",
    "n_drvr_trip": "No. of driver trips made by person",
    "n_psgr_trip": "No. of passenger trips made by person",
    "n_tran_trip": "No. of transit trips made by person",
    "n_gotr_trip": "No. of GO train only trips made by person",
    "n_jgot_trip": "No. of joint GO train and other transit trips made by person",
    "n_loct_trip": "No. of local transit only trips made by person",
    "n_bike_trip": "No. of cycling or electric micromobility trips made by person",
    "n_walk_trip": "No. of walking trips made by person",
    "n_othm_trip": "No. of trips of other mode made by person",
    "n_pers_trip2016": "Number of Trips made by the Person that would have been collected under 2016 parameters",
    "n_walk_trip2016": "Number of walking trips made by the Person that would have been collected under 2016 TTS parameters",
    "lasttrip": "Last trip made by person",
    "start_time": "Start time of trip",
    "mode_prime": "Primary travel mode of trip",
    "trip_purp": "Trip purpose",
    "purp_orig2022": "2022 Trip Purpose of Origin",
    "purp_orig": "Trip purpose of Origin",
    "purp_dest2022": "2022 Trip purpose of destination",
    "purp_dest": "Trip purpose of Destination",
    "firstwork": "First work related trip of the day",
    "firstsch": "First school related trip of the day",
    "region_orig": "Regional municipality of origin",
    "pd_orig": "Planning district of origin",
    "ward_orig": "Ward number of origin",
    "gta06_orig": "2006 GTA zone of origin",
    "tts22_orig": "2022 TTS zone of origin",
    "ggh4_orig": "GGHM V4 zone of origin",
    "ggh5_orig": "GGHM V5 zone of origin",
    "region_dest": "Regional municipality of destination",
    "pd_dest": "Planning district of destination",
    "ward_dest": "Ward number of destination",
    "gta06_dest": "2006 GTA zone of destination",
    "tts22_dest": "2022 TTS zone of destination",
    "ggh4_dest": "GGHM V4 zone of destination",
    "ggh5_dest": "GGHM V5 zone of destination",
    "car_pool": "Car pool",
    "hwy407": "Use of Hwy 407",
    "trip_km": "Straight line trip length in KM",
    "trip_m": "Straight line trip length in metre",
    "trip_man_km": "Manhattan distance of trip in KM",
    "trip_man_m": "Manhattan distance of trip in metre",
    "excl2016": "Exclude for comparisons with 2016 or earlier TTS",
    "mode_accs": "Access mode to transit",
    "mode_egrs": "Egress mode from transit",
    "tran_grp": "Combination of access, primary and egress modes",
    "tran_type": "Access/egress to transit",
    "first_accs_stn": "First boarding station if TTC subway or GO Train was used in Route 1",
    "region_accs": "Regional municipality of transit access pt.",
    "pd_accs": "Planning District of transit access pt.",
    "gta06_accs": "2006 GTA zone of transit access pt.",
    "tts22_accs": "2022 TTS zone of transit access pt.",
    "ggh4_accs": "GGHM V4 zone of access",
    "ggh5_accs": "GGHM V5 zone of access",
    "accs_m": "Distance from origin to access pt.",
    "accs_man_m": "Manhattan distance from origin to access pt.",
    "last_egrs_stn": "Last alighting station if TTC subway or GO Train was used in the last route",
    "region_egrs": "Regional municipality of transit egress pt.",
    "pd_egrs": "Planning district of transit egress pt.",
    "gta06_egrs": "2006 GTA zone of transit egress pt.",
    "tts22_egrs": "2022 TTS zone of transit egress pt.",
    "ggh4_egrs": "GGHM V4 zone of egress",
    "ggh5_egrs": "GGHM V5 zone of egress",
    "egrs_m": "Distance from egress pt. to destination",
    "egrs_man_m": "Manhattan distance from egress pt. to destination",
    "n_route": "Number of transit links used",
    "route_1": "Route used on link #1",
    "route_2": "Route used on link #2",
    "route_3": "Route used on link #3",
    "route_4": "Route used on link #4",
    "route_5": "Route used on link #5",
    "route_6": "Route used on link #6",
    "last_route": "Route used on last link",
    "sub_on": "TTC subway boarding station",
    "sub_off": "TTC subway alighting station",
    "go_on": "GO rail boarding station",
    "go_off": "GO rail alighting station",
    "n_go_rail": "No. of links on GO rail",
    "n_go_bus": "No. of links on GO bus",
    "n_subway": "No. of links on TTC subway/RT",
    "n_ttc_bus": "No. of links on TTC bus/streetcar",
    "n_local": "No. of links other local transit",
    "n_other": "No. of links on non-local transit",
    "oper_code": "Transit operator on last non-TTC/GO link",
    "use_ttc": "TTC trip",
}
