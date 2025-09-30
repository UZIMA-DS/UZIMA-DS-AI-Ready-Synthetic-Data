*************************************************
*** CHECK ALPHA SPEC VA FOR OBVIOUS ERRORS  ***
*************************************************
clear all
set mem 1000m
set more off,permanently

//cd "~/OneDrive - University of Witwatersrand/DataDistribution/HDSSExcessMortality/DataFromSites/Kaloleni_Rabai/August2022"
cd "~/OneDrive - University of Witwatersrand/DataDistribution/HDSSExcessMortality/DataFromSites/Kaloleni_Rabai/September2022"

//cd "C:\Users\User\University of Witwatersrand\Chodziwadziwa Kabudula - AnalyticsTeam\ExcessMortalityUpdated\Kaloleni_Rabai\August2022"
//cd "F:\AKU\Surveillance\Inspire\Cleaning\13082022\shared\copy"

*--------read dob file --------
import delimited "individuals_DOB.csv", varnames(1) clear
gen dob2 = date(dob, "YMD")
format dob2 %td
drop dob
collapse (min) dob2, by(individualid)
save dates_of_birth, replace

use "individuals_r1", clear
cap confirm variable individualid 
if _rc !=0 { 
//rename individual individualid
}
keep individualid hhno dob sex doi event event_date
gen round = 1
save observed_by_round, replace

foreach i of numlist 2 3 4 5 6 8 10  {
	use "individuals_r`i'", clear
	cap confirm variable individualid 
	if _rc !=0 { 
	rename individual individualid
	}
	keep individualid hhno dob sex doi event event_date
	gen round = `i'
	/*if `i' == 3	{
		gen doi2 = date(doi, "YMD")
		//format doi2 %td
		drop doi
		rename doi2 doi
		}*/
	append using observed_by_round, force
	save observed_by_round, replace
}

use observed_by_round, clear
bys individualid: egen min_hhno = min(hhno)
sort individualid round
bys individualid: gen n = _n
keep if n == 1
foreach var of varlist doi dob sex event round {
rename `var' `var'_s
}
save indiv_start_events, replace

use observed_by_round, clear
bys individualid: egen min_hhno = min(hhno)
gsort individualid -round
bys individualid: gen n = _n
keep if n == 1
save indiv_end_events, replace

use observed_by_round, clear
keep if inlist(event, "OMG", "DTH")
bys individualid: gen N = _N

use observed_by_round, clear
collapse (min) start_round2 = round ///
	(max) end_round2 = round ///
	(min) start_obs_date2 = doi ///
	(max) end_obs_date2 = doi ///
	, by(individualid) 
format start_obs_date2 %td
format end_obs_date2 %td
save indiv_start_end_round, replace

use "./individuals_r1", clear
destring event_date, replace
format event_date %td
replace event_date = doi
rename  event_date start_date
format start_date %td
rename event start_event
gen start_round = 1
//rename individual individualid
gen HDSSName = "Kaloleni Rabai"
gen end_event =""
gen end_date = .
format end_date %td
gen end_round = 1
rename doi start_obs_date
gen end_obs_date = start_obs_date
save individual_residence_episodes, replace

//-------------------------------------extract new individuals added in round 2

use "./individuals_r2", clear
keep if inlist(event,"BTH", "IMG")
gen start_date = .
format start_date %td
replace start_date = dob if event == "BTH"

gen event_d = substr(event_date,1,2)
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"

foreach var of varlist event_d - event_y {
 destring `var', replace	
}

/*
gen d = mdy(event_m, event_d, event_y)
format d %td
*/

replace start_date = mdy(event_m, event_d, event_y) if event == "IMG"

rename event start_event
gen start_round = 2
gen HDSSName = "Kaloleni Rabai"
gen end_event =""
gen end_date = .
format end_date %td
gen end_round = 2
rename doi start_obs_date
gen end_obs_date = start_obs_date
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
append using individual_residence_episodes
save individual_residence_episodes, replace

//check for dups
bys individualid: gen N =_N

//extract individuals with OMG or DTH events from round 2
use "./individuals_r2", clear
keep if inlist(event,"DTH", "OMG")

//create event date
gen event_d = substr(event_date,1,2)
replace event_d=substr(event_date,9,2) if substr(event_date,1,4) == "2017"
replace event_d = "" if event_d == "99"

gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
replace event_m =substr(event_date,6,2) if substr(event_date,1,4) == "2017"

gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"
replace event_y=substr(event_date,1,4) if substr(event_date,1,4) == "2017"

foreach var of varlist event_d - event_y {
 destring `var', replace	
}

rename event end_event2
gen end_date2 = .
format end_date2 %td
replace end_date2 = mdy(event_m, event_d, event_y)
rename doi end_obs_date2
rename sex sex2
rename dob dob2
gen end_round2 = 2
keep individualid dob2 sex2 end_event2 end_date2 end_round2 end_obs_date2
merge 1:m individualid using individual_residence_episodes
replace dob = dob2 if missing(dob)
replace end_event = end_event2 if _merge == 3
replace end_date = end_date2 if _merge == 3
replace end_round = end_round2 if _merge == 3
replace end_obs_date = end_obs_date2 if _merge == 3
drop if _merge == 1
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
save individual_residence_episodes, replace


//----------------------------extract new individuals added in round 3
use "./individuals_r3", clear
keep if inlist(event,"BTH", "IMG")
gen start_date = .
format start_date %td

//gen DOB = date( dob ,"ymd" )
replace start_date = dob if event == "BTH"

gen event_d = substr(event_date,1,2)
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"

foreach var of varlist event_d - event_y {
 destring `var', replace	
}


replace start_date = mdy(event_m, event_d, event_y) if event == "IMG"

rename event start_event
gen start_round = 3
gen HDSSName = "Kaloleni Rabai"
gen end_event =""
gen end_date = .
format end_date %td
gen end_round = 3
rename doi start_obs_date

gen end_obs_date = start_obs_date
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
append using individual_residence_episodes
save individual_residence_episodes, replace

// check for dups
bys individualid: gen N =_N

//extract individuals with OMG or DTH events from round 3
use "./individuals_r3", clear
keep if inlist(event,"DTH", "OMG")

//create event date
gen event_d = substr(event_date,1,2)
replace event_d=substr(event_date,9,2) if substr(event_date,1,4) == "2017"
replace event_d = "" if event_d == "99"

gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
replace event_m=substr(event_date,6,2) if substr(event_date,1,4) == "2017"

gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"
replace event_y=substr(event_date,1,4) if substr(event_date,1,4) == "2017"

foreach var of varlist event_d - event_y {
 destring `var', replace	
}

rename event end_event2
gen end_date2 = .
format end_date2 %td
replace end_date2 = mdy(event_m, event_d, event_y)
rename doi end_obs_date2

rename sex sex2
rename dob dob2
gen end_round2 = 3
keep individualid dob2 sex2 end_event2 end_date2 end_round2 end_obs_date2
merge 1:m individualid using individual_residence_episodes
replace dob = dob2 if missing(dob)
replace end_event = end_event2 if _merge == 3
replace end_date = end_date2 if _merge == 3
replace end_round = end_round2 if _merge == 3
replace end_obs_date = end_obs_date2 if _merge == 3
drop if _merge == 1
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
save individual_residence_episodes, replace



//-----------------------------------extract new individuals added in round 4
use "./individuals_r4", clear
keep if inlist(event,"BTH", "IMG")
gen start_date = .
format start_date %td

replace start_date = dob if event == "BTH"

gen event_d = substr(event_date,1,2)
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"

foreach var of varlist event_d - event_y {
 destring `var', replace	
}
 gen event_d1= real( event_d)
 gen event_m1= real( event_m)
 gen event_y1= real( event_y)
replace start_date = mdy(event_m1, event_d1, event_y1) if event == "IMG"

rename event start_event
gen start_round = 4
gen HDSSName = "Kaloleni Rabai"
gen end_event =""
gen end_date = .
format end_date %td
gen end_round = 4
rename doi start_obs_date
gen end_obs_date = start_obs_date
 
gen hhno1 = real( hhno)
drop hhno
rename hhno1 hhno
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
append using individual_residence_episodes
save individual_residence_episodes, replace

// check for dups
bys individualid: gen N =_N

//extract individuals with OMG or DTH events from round 4
use "./individuals_r4", clear
keep if inlist(event,"DTH", "OMG")

//create event date
gen event_d = substr(event_date,1,2)
replace event_d=substr(event_date,9,2) if substr(event_date,1,4) == "2017"
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
replace event_m=substr(event_date,6,2) if substr(event_date,1,4) == "2017"

gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"
replace event_y=substr(event_date,1,4) if substr(event_date,1,4) == "2017"

foreach var of varlist event_d - event_y {
 destring `var', replace	
}

rename event end_event2
gen end_date2 = .
format end_date2 %td

gen event_d1= real( event_d)
 gen event_m1= real( event_m)
 

replace end_date2 = mdy(event_m1, event_d1, event_y)

rename doi end_obs_date2

rename sex sex2
rename dob dob2
gen end_round2 = 4
keep individualid dob2 sex2 end_event2 end_date2 end_round2 end_obs_date2
merge 1:m individualid using individual_residence_episodes
replace dob = dob2 if missing(dob)
replace end_event = end_event2 if _merge == 3
replace end_date = end_date2 if _merge == 3
replace end_round = end_round2 if _merge == 3
replace end_obs_date = end_obs_date2 if _merge == 3
drop if _merge == 1
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
save individual_residence_episodes, replace


//-----------------------------------extract new individuals added in round 5
use "./individuals_r5", clear
keep if inlist(event,"BTH", "IMG")
gen start_date = .
format start_date %td

replace start_date = dob if event == "BTH"

gen event_d = substr(event_date,1,2)
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"

 gen event_d1= real( event_d)
 gen event_m1= real( event_m)
 gen event_y1= real( event_y)
replace start_date = mdy(event_m1, event_d1, event_y1) if event == "IMG"

rename event start_event
gen start_round = 5
gen HDSSName = "Kaloleni Rabai"
gen end_event =""
gen end_date = .
format end_date %td
gen end_round = 5
rename doi start_obs_date
gen end_obs_date = start_obs_date
 
gen hhno1 = real( hhno)
drop hhno
rename hhno1 hhno
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
append using individual_residence_episodes
save individual_residence_episodes, replace

// check for dups
bys individualid: gen N =_N

//extract individuals with OMG or DTH events from round 5
use "./individuals_r5", clear
keep if inlist(event,"DTH", "OMG")

//create event date
gen event_d = substr(event_date,1,2)
replace event_d=substr(event_date,9,2) if substr(event_date,1,4) == "2017"
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
replace event_m=substr(event_date,6,2) if substr(event_date,1,4) == "2017"

gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"
replace event_y=substr(event_date,1,4) if substr(event_date,1,4) == "2017"


rename event end_event2
gen end_date2 = .
format end_date2 %td

 gen event_d1= real( event_d)
 gen event_m1= real( event_m)
 gen event_y1= real( event_y)
 

replace end_date2 = mdy(event_m1, event_d1, event_y1)

rename doi end_obs_date2

rename sex sex2
rename dob dob2
gen end_round2 = 5
keep individualid dob2 sex2 end_event2 end_date2 end_round2 end_obs_date2
merge 1:m individualid using individual_residence_episodes
replace dob = dob2 if missing(dob)
replace end_event = end_event2 if _merge == 3
replace end_date = end_date2 if _merge == 3
replace end_round = end_round2 if _merge == 3
replace end_obs_date = end_obs_date2 if _merge == 3
drop if _merge == 1
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
save individual_residence_episodes, replace


//-----------------------------------extract new individuals added in round 6
use "./individuals_r6", clear
keep if inlist(event,"BTH", "IMG")
gen start_date = .
format start_date %td

replace start_date = dob if event == "BTH"

gen event_d = substr(event_date,1,2)
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"

 gen event_d1= real( event_d)
 gen event_m1= real( event_m)
 gen event_y1= real( event_y)
replace start_date = mdy(event_m1, event_d1, event_y1) if event == "IMG"

rename event start_event
gen start_round = 6
gen HDSSName = "Kaloleni Rabai"
gen end_event =""
gen end_date = .
format end_date %td
gen end_round = 6
rename doi start_obs_date
gen end_obs_date = start_obs_date
 
/*gen hhno1 = real( hhno)
drop hhno
rename hhno1 hhno
*/

keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
append using individual_residence_episodes
save individual_residence_episodes, replace

// check for dups
bys individualid: gen N =_N

//extract individuals with OMG or DTH events from round 6
use "./individuals_r6", clear
keep if inlist(event,"DTH", "OMG")

//create event date
gen event_d = substr(event_date,1,2)
replace event_d=substr(event_date,9,2) if substr(event_date,1,4) == "2017"
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
replace event_m=substr(event_date,6,2) if substr(event_date,1,4) == "2017"

gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"
replace event_y=substr(event_date,1,4) if substr(event_date,1,4) == "2017"


rename event end_event2
gen end_date2 = .
format end_date2 %td

 gen event_d1= real( event_d)
 gen event_m1= real( event_m)
 gen event_y1= real( event_y)
 

replace end_date2 = mdy(event_m1, event_d1, event_y1)

rename doi end_obs_date2

rename sex sex2
rename dob dob2
gen end_round2 = 6
keep individualid dob2 sex2 end_event2 end_date2 end_round2 end_obs_date2
merge 1:m individualid using individual_residence_episodes
replace dob = dob2 if missing(dob)
replace end_event = end_event2 if _merge == 3
replace end_date = end_date2 if _merge == 3
replace end_round = end_round2 if _merge == 3
replace end_obs_date = end_obs_date2 if _merge == 3
drop if _merge == 1
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
save individual_residence_episodes, replace


//-----------------------------------extract new individuals added in round 8
use "./individuals_r8", clear
keep if inlist(event,"BTH", "IMG")
gen start_date = .
format start_date %td

replace start_date = dob if event == "BTH"

gen event_d = substr(event_date,1,2)
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"

 gen event_d1= real( event_d)
 gen event_m1= real( event_m)
 gen event_y1= real( event_y)
replace start_date = mdy(event_m1, event_d1, event_y1) if event == "IMG"

rename event start_event
gen start_round = 8
gen HDSSName = "Kaloleni Rabai"
gen end_event =""
gen end_date = .
format end_date %td
gen end_round = 8
rename doi start_obs_date
gen end_obs_date = start_obs_date
//rename individual individualid 
/*gen hhno1 = real( hhno)
drop hhno
rename hhno1 hhno
*/

keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
append using individual_residence_episodes
save individual_residence_episodes, replace

// check for dups
bys individualid: gen N =_N

//extract individuals with OMG or DTH events from round 8
use "./individuals_r8", clear
keep if inlist(event,"DTH", "OMG")

//create event date
gen event_d = substr(event_date,1,2)
replace event_d=substr(event_date,9,2) if substr(event_date,1,4) == "2017"
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
replace event_m=substr(event_date,6,2) if substr(event_date,1,4) == "2017"

gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"
replace event_y=substr(event_date,1,4) if substr(event_date,1,4) == "2017"


rename event end_event2
gen end_date2 = .
format end_date2 %td

 gen event_d1= real( event_d)
 gen event_m1= real( event_m)
 gen event_y1= real( event_y)
 
replace end_date2 = mdy(event_m1, event_d1, event_y1)

rename doi end_obs_date2

rename sex sex2
rename dob dob2
gen end_round2 = 8
//rename individual individualid 
keep individualid dob2 sex2 end_event2 end_date2 end_round2 end_obs_date2
merge 1:m individualid using individual_residence_episodes
replace dob = dob2 if missing(dob)
replace end_event = end_event2 if _merge == 3
replace end_date = end_date2 if _merge == 3
replace end_round = end_round2 if _merge == 3
replace end_obs_date = end_obs_date2 if _merge == 3
drop if _merge == 1
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
save individual_residence_episodes, replace


//-----------------------------------extract new individuals added in round 10
use "./individuals_r10", clear
keep if inlist(event,"BTH", "IMG")
gen start_date = .
format start_date %td

replace start_date = dob if event == "BTH"

gen event_d = substr(event_date,1,2)
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"

 gen event_d1= real( event_d)
 gen event_m1= real( event_m)
 gen event_y1= real( event_y)
replace start_date = mdy(event_m1, event_d1, event_y1) if event == "IMG"

rename event start_event
gen start_round = 10
gen HDSSName = "Kaloleni Rabai"
gen end_event =""
gen end_date = .
format end_date %td
gen end_round = 10
rename doi start_obs_date
gen end_obs_date = start_obs_date
 
/*gen hhno1 = real( hhno)
drop hhno
rename hhno1 hhno
*/

keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
append using individual_residence_episodes
save individual_residence_episodes, replace

// check for dups
bys individualid: gen N =_N

//extract individuals with OMG or DTH events from round 10
use "./individuals_r10", clear
keep if inlist(event,"DTH", "OMG")

//create event date
gen event_d = substr(event_date,1,2)
replace event_d=substr(event_date,9,2) if substr(event_date,1,4) == "2017"
replace event_d = "" if event_d == "99"
gen event_m = substr(event_date,4,2)
replace event_m = "0"+ substr(event_m,1,1) if substr(event_m,2,1) == "/"
replace event_m = "" if event_m == "99"
replace event_m = "08" if event_m == "/0"
replace event_m = "11" if event_m == "/1"
replace event_m=substr(event_date,6,2) if substr(event_date,1,4) == "2017"

gen event_y = substr(event_date,7,10)
replace event_y = "" if event_m == "9999"
replace event_y = "2"+ event_y if length(event_y) == 3
replace event_y = "" if substr(event_y,1,1) == "/"
replace event_y=substr(event_date,1,4) if substr(event_date,1,4) == "2017"


rename event end_event2
gen end_date2 = .
format end_date2 %td

 gen event_d1= real( event_d)
 gen event_m1= real( event_m)
 gen event_y1= real( event_y)
 

replace end_date2 = mdy(event_m1, event_d1, event_y1)

rename doi end_obs_date2

rename sex sex2
rename dob dob2
gen end_round2 = 10
keep individualid dob2 sex2 end_event2 end_date2 end_round2 end_obs_date2
merge 1:m individualid using individual_residence_episodes
replace dob = dob2 if missing(dob)
replace end_event = end_event2 if _merge == 3
replace end_date = end_date2 if _merge == 3
replace end_round = end_round2 if _merge == 3
replace end_obs_date = end_obs_date2 if _merge == 3
drop if _merge == 1
keep individualid hhno village_na start_obs_date dob sex relation ///
start_event start_date start_round HDSSName end_event end_date end_round end_obs_date
format end_obs_date %td
save individual_residence_episodes, replace
merge m:1 individualid using indiv_start_end_round
replace end_round = end_round2
replace end_obs_date = end_obs_date2
//drop individual_residence_episodes
save individual_residence_episodes, replace

use individual_residence_episodes, clear
drop _merge
merge m:1 individualid using indiv_start_events
replace dob = dob_s if start_event=="" & inlist(event_s, "ENU", "IMG", "BTH")
replace sex = sex_s if start_event=="" & inlist(event_s, "ENU", "IMG", "BTH")
replace start_date = start_obs_date2 if start_event=="" & inlist(event_s, "ENU", "IMG", "BTH")
replace start_obs_date = start_obs_date2 if start_event=="" & inlist(event_s, "ENU", "IMG", "BTH")
replace start_round = start_round2 if start_event=="" & inlist(event_s, "ENU", "IMG", "BTH")
replace start_event = event_s if start_event=="" & inlist(event_s, "ENU", "IMG", "BTH")
tab start_round2 if start_event==""
keep individualid- village_na
//bring in missing dobs
merge m:1 individualid using dates_of_birth
replace dob = dob2 if dob ==.
drop dob2
replace start_date = start_obs_date if start_date == . & inlist(start_event,"ENU", "IMG") 
replace start_date = dob if start_date == . & start_event == "BTH"

replace end_date = end_obs_date if end_date == . & end_event == "OMG"
replace end_event = "OBS" if end_event == "" 
replace end_date = end_obs_date if end_date == . & end_event == "OBS"
replace end_date = end_obs_date if end_date == . & end_event == "DTH"
save individual_residence_episodes_clean, replace

/* checks
gen start_year = year(start_date)
tab start_year start_event 

gen end_year = year(end_date)
tab end_year end_event 

br if start_event==""

use individual_residence_episodes_clean, clear
br if end_date == . & end_event == "DTH" 
gen end_obs_yr = year(end_obs_date)
tab end_obs_yr if end_date == . & end_event == "DTH"
*/

rename start_event startevent
rename start_date startdate
rename end_date enddate
rename end_event endevent
gen dod = enddate if endevent == "DTH"
format dod %td
gen died = 1 if endevent == "DTH"
save "KE081_Raw_CensoredEpisodesV2", replace


* STSET the data
use "KE081_Raw_CensoredEpisodesV2", clear
replace enddate = enddate+0.01 if startdate == startdate
stset enddate, id(individualid) fail(died) time(startdate) enter(startdate) scale(365.25)
save "KE081_Raw_CensoredEpisodes_st_ready", replace

/* look at death rates all ages */
use "KE081_Raw_CensoredEpisodes_st_ready", clear
stsplit year, at(1(1)max)

strate year, output(py_mx_KE081,replace) nolist
use py_mx_KE081, clear
format _Y %9.0g
* correct for DAYS time scale
replace _Y = _Y 
replace _Rate = _Rate
replace _Lower = _Lower
replace _Upper = _Upper
rename _D Deaths
rename _Y PersonYears
rename _Rate Mx
rename _Lower Lower95Mx
rename _Upper Upper95Mx
egen TotD = sum(Deaths)
egen TotPY = sum(PersonYears)
gen mx_1000 = (Deaths/PersonYears)*1000
gen lb_mx_1000 = Lower95Mx *1000
gen ub_mx_1000 = Upper95Mx *1000
replace year = year+ 1960
gen centreid = "KE081"
save "py_mx_KE081",replace

drop if year >= 2022 | year < 2017
twoway (rspike ub_mx_1000 lb_mx_1000 year, lcolor(gs7)lwidth() xaxis(1)) ///
	(scatter mx_1000 year,mfcolor(gs7) mlcolor(gs7)) ///
	,xlabel(2015 (1) 2021, grid angle(0)) ///
	ylabel(0 (2) 10,grid angle(0)) ///
	ytitle("Overall Mortality",height(3) ) ///
	xtitle("Year",height(3) ) ///
	legend(off) ///
	title("Overall Mortality:KE081 ") ///
	graphregion(color(white)) name(KE081,replace) 
graph save "KE081Mx.gph", replace
graph export "KE081Mx.pdf", replace
	


 
 



