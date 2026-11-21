from pathlib import Path
from typing import Literal, NotRequired, TypedDict

TTSYear = Literal[1986, 1991, 1996, 2001, 2006, 2011, 2016, 2022]
TTSMetric = Literal["household", "person", "trip", "transit"]
TTSBaseAttribute = Literal[
    "region", "mun", "pd", "ward", "gta06", "tts22", "ggh4", "ggh5"
]
TTSAttribute = Literal[
    "region_hhld", "pd_hhld", "ward_hhld", "gta06_hhld", "tts22_hhld",
    "ggh4_hhld", "ggh5_hhld", "sampletype", "surveymethod", "rec_mail",
    "dwell_type", "income", "hhbornincanada", "hhstructure", "n_person",
    "n_adult", "n_child", "n_senior", "n_vehicle", "n_licence", "n_tranpass",
    "n_emp_tot", "n_emp_ft", "n_emp_pt", "n_emp_home", "n_emp_hft", "n_emp_hpt",
    "n_student", "n_stu_k12", "n_stu_pse", "trip_day", "trip_week", 
    "trip_period", "n_pers11up", "n_hh11_trip", "n_hhld_trip2016", "n_pers5up",
    "n_hhld_trip", "n_hdrvr_trip", "n_hpsgr_trip", "n_htran_trip",
    "n_hgotr_trip", "n_hjgot_trip", "n_hloct_trip", "n_hbike_trip",
    "n_hwalk_trip", "n_hothm_trip", "respond", "age", "age_range", "sex",
    "sex_orig", "ethnicity", "immigration", "driver_lic", "tran_pass",
    "emp_stat", "occstat", "occupation2022", "occupation", "workplace",
    "free_park", "no_work", "region_emp", "pd_emp", "ward_emp", "gta06_emp",
    "tts22_emp", "ggh4_emp", "ggh5_emp", "stu_stat", "sch_code", "region_sch",
    "pd_sch", "ward_sch", "gta06_sch", "tts22_sch", "ggh4_sch", "ggh5_sch",
    "workcommute", "n_wcommdays", "wrkcmon", "wrkctue", "wrkcwed", "wrkcthu",
    "wrkcfri", "wcomm_lastwk", "madetrips", "work_trip", "sch_trip",
    "n_pers_trip", "n_drvr_trip", "n_psgr_trip", "n_tran_trip", "n_gotr_trip",
    "n_jgot_trip", "n_loct_trip", "n_bike_trip", "n_walk_trip", "n_othm_trip",
    "n_pers_trip2016", "n_walk_trip2016", "lasttrip", "start_time",
    "mode_prime", "trip_purp", "purp_orig2022", "purp_orig", "purp_dest2022",
    "purp_dest", "firstwork", "firstsch", "region_orig", "pd_orig", "ward_orig",
    "gta06_orig", "tts22_orig", "ggh4_orig", "ggh5_orig", "region_dest",
    "pd_dest", "ward_dest", "gta06_dest", "tts22_dest", "ggh4_dest",
    "ggh5_dest", "car_pool", "hwy407", "trip_km", "trip_m", "trip_man_km",
    "trip_man_m", "excl2016", "mode_accs", "mode_egrs", "tran_grp", "tran_type",
    "first_accs_stn", "region_accs", "pd_accs", "gta06_accs", "tts22_accs",
    "ggh4_accs", "ggh5_accs", "accs_m", "accs_man_m", "last_egrs_stn",
    "region_egrs", "pd_egrs", "gta06_egrs", "tts22_egrs", "ggh4_egrs",
    "ggh5_egrs", "egrs_m", "egrs_man_m", "n_route", "route_1", "route_2",
    "route_3", "route_4", "route_5", "route_6", "last_route", "sub_on",
    "sub_off", "go_on", "go_off", "n_go_rail", "n_go_bus", "n_subway",
    "n_ttc_bus", "n_local", "n_other", "oper_code", "use_ttc",
]  # fmt: skip

CrossTabType = Literal["csv", "col"]


class TTSGeometryRenamingLookup(TypedDict):
    output_name: str
    columns: dict[str, str]


class TTSGeometry(TypedDict):
    file: Path
    key: str


class CodeLookupBase(TypedDict):
    type: Literal["direct", "range", "range_direct"]
    notes: NotRequired[str]
    years_valid: NotRequired[list[TTSYear]]


class CodeLookupDirect(CodeLookupBase):
    type: Literal["direct"]
    code: str | int
    description: str


class CodeLookupRange(CodeLookupBase):
    type: Literal["range"]
    code_min: int
    code_max: int


class CodeLookupRangeDirect(CodeLookupBase):
    type: Literal["range_direct"]
    code_min: int
    code_max: int
    code: int
    description: str


type CodeLookup = CodeLookupDirect | CodeLookupRange | CodeLookupRangeDirect
