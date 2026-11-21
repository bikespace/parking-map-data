## tts_tools: Data Utilities for the Transportation Tomorrow Survey

Purpose: simplify using exports from the Transportation Tomorrow Survey data portal.

The API should enable:

- Load an export txt file
- Provide a pandas dataframe of the data
- Provide a geopandas geodataframe of the data with the geometries automatically added
- Provide a metadata record

## Dev

```sh
# run pytest
uv run pytest -s src/tts_tools --cov-reset --cov=src/tts_tools
```

## Options Covered

Output Type:

- [x] Cross Tabulation
- [ ] Record Count
- [ ] Frequency Distribution

Metric:

- [ ] Household
- [ ] Person
- [x] Trip
- [ ] Transit

Year:

- [ ] 1986
- [ ] 1991
- [ ] 1996
- [ ] 2001
- [ ] 2006
- [ ] 2011
- [ ] 2016
- [x] 2022

Cross Tabulation Features

- [x] Row and Column Attributes
- [ ] Row, Column, AND Table Attributes
- [ ] Row, Column, and Table groupings
- [ ] Filters
- [x] Comma-defined table output
- [x] Column format output
- [ ] Expansion factor on or off (this one is tricky)


## Description to code conversions

### Geographies

"accs", "dest", "egrs", "emp", "hhld", "orig", "sch"

- [ ] `region`: Regional municipality
- [x] `pd`: Planning district
- [ ] `ward`: Ward number
- [ ] `gta06`: 2006 GTA zone
- [x] `tts22`: 2022 TTS zone
- [ ] `ggh4`: GGHM V4 zone
- [ ] `ggh5`: GGHM V5 zone

### Household Attributes

#### Survey Info

- [ ] `sampletype`: Type of sample
- [ ] `surveymethod`: Survey method
- [ ] `rec_mail`: Receipt of advance letter

#### Household Characteristics

- [ ] `n_person`: No. of persons in household
- [ ] `dwell_type`: Type of dwelling unit
- [ ] `income`: Income range of household
- [ ] `hhbornincanada`: Household born in Canada
- [ ] `hhstructure`: Household structure
- [ ] `n_vehicle`: No. of vehicles in household
- [ ] `n_adult`: No. of adults (aged 18+) in household
- [ ] `n_child`: No. of children (aged 0-17) in household
- [ ] `n_senior`: No. of seniors (aged 65+) in household (65+ y.o.)
- [ ] `n_licence`: No. of drivers in household
- [ ] `n_tranpass`: No. of persons with transit pass
- [ ] `n_emp_tot`: No. of employed in household
- [ ] `n_emp_ft`: No. of F/T employed people in household
- [ ] `n_emp_pt`: No. of P/T employed people in household
- [ ] `n_emp_home`: No. of employed people in household who exclusively work from home
- [ ] `n_emp_hft`: No. of F/T employed people in household who exclusively work from home
- [ ] `n_emp_hpt`: No. of P/T employed people in household who exclusively work from home
- [ ] `n_student`: No. of students in household
- [ ] `n_stu_k12`: No. of students in K12 schools in household
- [ ] `n_stu_pse`: No. of students in post-secondary schools in household

#### Travel Day

- [ ] `trip_day`: Day of the week trips were made
- [ ] `trip_week`: Weeks into the survey when trips were made
- [ ] `trip_period`: Trip period
- [ ] `n_pers11up`: No. of people aged 11+
- [ ] `n_hh11_trip`: No. of trips made by people aged 11+
- [ ] `n_hhld_trip2016`: No. of trips made by household based on 2016 criteria
- [ ] `n_pers5up`: No. of people aged 5+
- [ ] `n_hhld_trip`: No. of trips made by household
- [ ] `n_hdrvr_trip`: No. of driver trips made by household
- [ ] `n_hpsgr_trip`: No. of passenger trips made by household
- [ ] `n_htran_trip`: No. of transit trips made by household
- [ ] `n_hgotr_trip`: No. of GO train only trips made by household
- [ ] `n_hjgot_trip`: No. of joint GO train and other transit trips made by household
- [ ] `n_hloct_trip`: No. of local transit only trips made by household
- [ ] `n_hbike_trip`: No. of cycling or electric micromobility trips made by household
- [ ] `n_hwalk_trip`: No. of walking trips made by household
- [ ] `n_hothm_trip`: No. of trips of other mode made by household

### Person Attributes

#### Demographics

- [ ] `respond`: Respondent
- [ ] `sex`: Gender of person
- [ ] `sex_orig`: Survey response to the Gender question
- [ ] `age`: Age of person
- [ ] `age_range`: Age range of person

#### Transport-Related

- [ ] `driver_lic`: Possess driver's licence
- [ ] `tran_pass`: Possess a transit pass

#### Occupation Status

- [ ] `occstat`: Occupation status
- [ ] `emp_stat`: Employment status of person
- [ ] `stu_stat`: Student status of person

#### Work Information

- [ ] `occupation2022`: 2022 Occupation type
- [ ] `occupation`: Occupation type
- [ ] `workplace`: Workplace location type
- [ ] `free_park`: Free Parking at work

#### School Information

- [ ] `sch_code`: School code

### Equity Demographics

- [ ] `immigration`: Immigration year if applicable
- [ ] `ethnicity`: Ethnicity of person

#### Work Commute

- [ ] `workcommute`: Commuted for work last week
- [ ] `wrkcmon`: Commuted for work last Monday
- [ ] `wrkctue`: Commuted for work last Tuesday
- [ ] `wrkcwed`: Commuted for work last Wednesday
- [ ] `wrkcthu`: Commuted for work last Thursday
- [ ] `wrkcfri`: Commuted for work last Friday
- [ ] `n_wcommdays`: Number of weekdays commuted for work last week
- [ ] `wcomm_lastwk`: Days which commuted for work last week

#### Travel on Travel Day

- [ ] `madetrips`: Made any trips on survey day
- [ ] `sch_trip`: Made school trip on survey day
- [ ] `work_trip`: Made work trip on survey day
- [ ] `no_work`: Worked from home on survey day
- [ ] `n_pers_trip`: No. of trips made by person
- [ ] `n_tran_trip`: No. of transit trips made by person
- [ ] `n_gotr_trip`: No. of GO train only trips made by person
- [ ] `n_jgot_trip`: No. of joint GO train and other transit trips made by person
- [ ] `n_loct_trip`: No. of local transit only trips made by person
- [ ] `n_drvr_trip`: No. of driver trips made by person
- [ ] `n_psgr_trip`: No. of passenger trips made by person
- [ ] `n_bike_trip`: No. of cycling or electric micromobility trips made by person
- [ ] `n_walk_trip`: No. of walking trips made by person
- [ ] `n_othm_trip`: No. of trips of other mode made by person
- [ ] `n_pers_trip2016`: Number of Trips made by the Person that would have been collected under 2016 parameters
- [ ] `n_walk_trip2016`: Number of walking trips made by the Person that would have been collected under 2016 TTS parameters

### Trip Attributes

#### Identifiers

- [ ] `lasttrip`: Last trip made by person

#### Trip Details

- [ ] `start_time`: Start time of trip
- [x] `mode_prime`: Primary travel mode of trip
- [ ] `trip_purp`: Trip purpose
- [ ] `purp_orig2022`: 2022 Trip Purpose of Origin
- [ ] `purp_orig`: Trip Purpose of Origin
- [ ] `purp_dest2022`: 2022 Trip purpose of destination
- [ ] `purp_dest`: Trip Purpose of Destination
- [ ] `firstwork`: First work related trip of the day
- [ ] `firstsch`: First school related trip of the day

#### Other Details, Distances

- [ ] `car_pool`: Car pool
- [ ] `hwy407`: Use of Hwy 407
- [ ] `trip_km`: Straight line trip length in KM
- [ ] `trip_m`: Straight line trip length in metre
- [ ] `trip_man_km`: Manhattan distance of trip in KM
- [ ] `trip_man_m`: Manhattan distance of trip in metre

#### Trip Flags

- [ ] `excl2016`: Exclude for comparisons with 2016 or earlier TTS

### Transit Attributes

#### Transit Access Modes

- [ ] `mode_accs`: Access mode to transit
- [ ] `mode_egrs`: Egress mode from transit
- [ ] `tran_grp`: Combination of access, primary and egress modes
- [ ] `tran_type`: Access/egress to transit

#### Access/Egress Points

- [ ] `first_accs_stn`: First boarding station if TTC subway or GO Train was used in Route 1
- [ ] `accs_m`: Distance from origin to access pt.
- [ ] `accs_man_m`: Manhattan distance from origin to access pt.
- [ ] `last_egrs_stn`: Last alighting station if TTC subway or GO Train was used in the last route
- [ ] `egrs_m`: Distance from egress pt. to destination
- [ ] `egrs_man_m`: Manhattan distance from egress pt. to destination

#### Transit Routes

- [ ] `n_route`: Number of transit links used
- [ ] `route_1..6`: Route used on link #1 through #6
- [ ] `last_route`: Route used on last link

#### Subway, GO Stations

- [ ] `sub_on`: TTC subway boarding station
- [ ] `sub_off`: TTC subway alighting station
- [ ] `go_on`: GO rail boarding station
- [ ] `go_off`: GO rail alighting station

#### Route Counts

- [ ] `n_go_rail`: No. of links on GO rail
- [ ] `n_go_bus`: No. of links on GO bus
- [ ] `n_subway`: No. of links on TTC subway/RT
- [ ] `n_ttc_bus`: No. of links on TTC bus/streetcar
- [ ] `n_local`: No. of links other local transit
- [ ] `n_other`: No. of links on non-local transit
- [ ] `oper_code`: Transit operator on last non-TTC/GO link
- [ ] `use_ttc`: TTC trip

### Station Codes

In data guide PDF

### Transit Operator Codes

In data guide PDF

### Transit Route Codes

In data guide PDF
