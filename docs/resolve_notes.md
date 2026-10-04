# Resolver notes (Module B part 1)

Not legal advice. Outputs: work/jurisdictions.json, work/address_facts.json. Rebuild: `python3 -m navigator.resolve` (cached, free).

## Geocoding
Census Geocoder, 4 workers, ~4 req/s, cache per address in work/geocode_cache/. Attempt order: raw street (with ZIP, then without), street variants (range first number, last number, unit suffix stripped, "05TH"->"5TH", "AV"->"AVE"), then onelineaddress. NJ ZIPs are unreliable in the sample (Newark rows with 11219, 08805, ...), so NJ never sends the ZIP. Query city is the dataset city (Dorchester, Van Nuys etc. are not used).
- exact 485, non_exact 8, fallback_postal 7, failed 0. Legal city equals the dataset city for all 500 (no West Hollywood, Oakland, Albany, Somerville case in this sample), so null legal_city count is 0.
- Census city parameter is soft (322 Western Ave, Cambridge matched in Boston). For city-limited datasets (Cambridge, Boston, DataSF) a disagreement is resolved in favour of the dataset (A0009, status non_exact, confidence 0.5, note set).
- fallback_postal (no house number or Census No_Match, confidence 0.4, legal city assumed from dataset): A0098, A0128, A0295, A0376, A0380 (Boston street names without number), A0346 (San Diego), A0384 (SF, 21 Guerrero St). They have no county/lat/lon; stack is [state, legal_city]. Engine should lower confidence on these.

## use_code encodings
- LA County 05xx ("Five or more apartments"): units >= 5. All 80 have it; 77 have assessor units (min 5 observed); 3 have units null.
- SF: A5 = 5 to 14, A15 = 15+, FS5/F5 = flats 5+; TIC = "4 units or less" by label but the single row has assessor units=5 (class and count disagree; units kept as assessor value, note this). Class lower bound goes to units_min only.
- San Diego SANDAG asr_landuse 14-16 = 5+ units (observed units 5 to 152); all 50 have assessor units; no year built.
- Berkeley (Alameda) 7200/7700/7800 labelled "5+ units": no units, no year. units_min=5 from label.
- Cambridge 111 "4-8-UNIT-APT", 112 ">8-UNIT-APT": all rows have units and year. Observed 111 = 5 to 8, 112 = 9+. units_min 4 / 9 from label, exact units from assessor.
- Boston A/112 "APT 7-30 UNITS": units_min 7. A/125 (subsidised, 26 rows), A/120 luxury apt (5), A/118 elderly (1): no count, NO safe minimum (units_min null, units_source none). 32 rows have no unit information at all.
- New Jersey MOD-IV: class 4C = apartments, 5 or more units, units_min=5 for all 140 rows. Building description (e.g. '6B-20U-G', '3S-F-D-6U-NH') looks like stories/basement, "nnU" units, but it could NOT be validated: only 1 NJ row has an assessor count and it contradicts (A0227: units=2 vs '13B-93U-2C-G' and class 4C). So parsed counts are NOT used as units; they appear only as an unvalidated hint in units_note. A0227 units nulled (assessor value 2 conflicts with 4C class).
- No row uses units_source "use_description_parsed" (kept in the vocabulary only).

## Gaps by legal city (n, units exact, units lower bound only, no unit info, year null)
LA 80: 77 / 3 / 0 / 6. SF 80: 80 / 0 / 0 / 2. SD 50: 50 / 0 / 0 / 50. Berkeley 40: 0 / 40 / 0 / 40. JC 50: 0 / 50 / 0 / 22. Hoboken 40: 0 / 40 / 0 / 36. Newark 50: 0 / 50 / 0 / 48. Boston 60: 0 / 28 / 32 / 8. Cambridge 50: 50 / 0 / 0 / 0.
No impossible year values (0, 1800, >2026) found in the sample; the check is in code (year_note "impossible/placeholder", value nulled). Year missing is noted "missing in source".

## Recommendation for the rules engine
- Unit predicates: use units if not null, else compare units_min (units_min >= threshold => TRUE only for ">= threshold" tests; "<=" or "< n" tests with only a lower bound => UNKNOWN, unless units_min already exceeds the cutoff then FALSE). NJ/Berkeley: 5+ is certain, but 6+, 10+ etc. are UNKNOWN.
- Boston A/125, A/120, A/118: treat unit count as unknown even for ">= 5" tests.
- Year/CO tests: null year => UNKNOWN (SD, Berkeley, most NJ). Year == cutoff year => UNKNOWN as per CONTRACTS.
- fallback_postal/non_exact addresses: still resolve to the city rules, but surface the lower confidence and notes.
- Never present a 4C-derived 5+ as an exact unit count.
