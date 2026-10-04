# R1 rules audit (outputs/rules_engine.json, 50 rules, as of 2026-10-01)

Not legal advice. Every rule was checked against its source doc; all 50 quoted_spans exist (44 single-line, 6 only after newline joining). Machine-readable fixes: `work/review/rules_findings.json` (18 items, quotes verified by `work/review/build_rules_findings.py`). Tally: **OK 19, FIX 9, RISK 22**.

| id | cell | verdict | reason |
|---|---|---|---|
| r-0001 | CA rent | RISK | Text supports 2024-04-01 (subd. (n)); key may hold 2020-01-01 (AB 1482) or 2024-01-01 (SB 567 effective). CO "within 15 years" proxied by age<15: year_built 2011 should be unknown, not covered. |
| r-0002 | CA JC | RISK | 2026-01-01 is the AB 1529 amendment, but r-0001 uses the operative date; same structure (subd. (m) "operative on April 1, 2024"). Alternatives 2024-04-01, 2020-01-01. Pick one convention for both. |
| r-0003 | CA deposit | OK | 2024-07-01 = subd. (c)(6) and brief "AB 12, eff. 7/1/2024". |
| r-0004 | CA fee | RISK | 2026-01-01 comes from AB 1170 (Stats. 2025 ch. 67, a code-maintenance bill); key may hold null. $30 cap correct. |
| r-0005 | CA screening | FIX | Brief ties this cell to "FEHA (SB 329)"; X021: source of income covers vouchers "as of Jan. 1, 2020". Propose 2020-01-01 (conf 0.5; 2024-01-01 is SB 267). |
| r-0006 | CA algo | FIX | Low: interaction cites "Cal. Const. art. IV s.8(c)(1)" (in no source) and misreads subd. (c) as protecting local bans. Citation parenthetical "(AB 325; SB 763)" is a match RISK. $1 million is supported by X024. |
| r-0007 | NJ JC | FIX | quoted_span fails the CONTRACTS newline rule (raw "renew a ␠\nlease" gives a double space); use single-line "No residential landlord may evict or fail to renew a". Brief/D062 cite is "N.J.S.A. 2A:18-61.1" (drop "et seq."). |
| r-0008 | NJ deposit | FIX | Organizer sample record (data/schema/sample_rule_record.json) for this exact rule: key_value "1.5 months' rent", effective null. Trim key_value. |
| r-0009 | NJ fee | FIX | Brief: "$50 cap, eff. 5/1/2026"; drop penalty numbers from key_value. Date check: approved 2026-01-20 + "first day of the fourth month next following" = 2026-05-01, correct. |
| r-0010 | NJ screening | FIX | Low: supplied link D061 is "section-10-5-12"; use "N.J.S.A. 10:5-12". Second record in the cell is legitimate (D061 and D065 both supplied). |
| r-0011 | NJ screening | RISK | Content verified (6/4/1 yr lookbacks, $1k/5k/10k, owner-occupied <=4 units, 2021-06-18 + 7th month = 2022-01-01). Key may cite N.J.S.A. 46:8-52 et seq. |
| r-0012 | NJ algo | OK | P.L.2026 c.43, approved 2026-07-20, sec. 9 gives 2027-07-01; conflicts_with JC/Hoboken matches T3; sec. 6.b quoted correctly. |
| r-0013 | MA rent | RISK | effective null; X023 says voters passed the ban in 1994 ("the same year voters passed the original rent control ban"): key may hold 1994. |
| r-0014 | MA rent | RISK | change_tests T5 calls it "IP 25-21"; ours "Mass. Initiative Petition 25-21". Date null vs 2026-06-23 (struck). |
| r-0015 | MA deposit | RISK | 2025-08-01 is the 2025 c.9 amendment of (1)(b); brief gives no date for 15B, key may hold null. |
| r-0016 | MA fee | RISK | Same date question as r-0015; content verified. |
| r-0017 | MA fee | RISK | Date 2025-08-01 matches brief. Brief writes "87DDD½", source writes "87DDD1/2": glyph mismatch risk. |
| r-0018 | MA screening | OK | c.151B s.4 quote verified; null date right. |
| r-0019 | MA algo | OK | Pending, referred to Senate W&M 3/12/2026 (D046). Suffix "(194th Gen. Ct.)" is a minor cite risk. |
| r-0020 | MA algo | OK | Pending, House W&M 3/12/2026 (D045). Same suffix note. |
| r-0021 | LA rent | RISK | key_value "3% for 2025-07-01 to 2026-06-30" is stale on 2026-10-01; corpus has no 2026-27 rate. Date 2026-02-02 vs 2026-01-24 (README open question). co_date 1978-10-01 matches README. |
| r-0022 | LA JC | FIX | Low: D043 chart lowest is $10,550 (mom-and-pop) and one month's rent (JCO single-family); "§ 165.00" appears in no source (corpus only has 165.05.B.5): outside knowledge. |
| r-0023 | LA deposit | RISK | 4.320% is the 2025 rate (stale); span is a 38-char heading; date null vs 1990-11-01 (X020 "Interest shall begin accruing on November 1, 1990"). |
| r-0024 | LA screening | OK | X017 sec. 45.69 "take effect on January 1, 2020". X source, no citation credit (D038 link-only). |
| r-0025 | SF rent | RISK | 1.6% verified (D080, D083); date 2026-03-01 is the rate year, key may hold null. |
| r-0026 | SF JC | OK | 17 causes, $8,245 / $24,733 / $5,497 for 3/01/26 to 2/28/27 verified in D083. |
| r-0027 | SF deposit | RISK | Citation is a page title, not an instrument (official cite not in any source). Cell may be a key no_rule. |
| r-0028 | SF screening | FIX | New gap-fill X031 (Police Code sec. 4906) gives the instrument, 7-year lookback and history "Eff. 8/10/2026" (Oper. 8/13/2014). Keep D078 span for credit. |
| r-0029 | SF algo | OK | D081 "went into effect on October 14, 2024". |
| r-0030 | SD JC | RISK | 2023-06-24 is the O-21647 adoption; sections 98.0702, .0704, .0709, .0710 amended "effective 3-28-2024". Alternative 2024-03-28. |
| r-0031 | SD screening | OK | X028 "effective 10-18-2018"; owner shared kitchen/bath exception correct. |
| r-0032 | SD algo | OK | D076 span, X015 "effective 6-21-2025", $1,000 in both. |
| r-0033 | Berkeley rent | RISK | 1.0% AGA verified (D008). Date alternatives (1980, Measure BB 2024-11). applies_if year<1980 and units>=2: D009 cutoff is CO after June 1980 (1980 should be unknown) and pre-1996 single-family tenancies are fully covered. No Berkeley facts exist, so low impact. |
| r-0034 | Berkeley JC | OK | D006 span; $19,413 / $6,471 in D004. |
| r-0035 | Berkeley deposit | RISK | Interest rule real (D007, D009) but "ch. 13.76" is inferred from "Rent Ordinance"; cell may be a key no_rule. |
| r-0036 | Berkeley fee | OK | BMC 13.78.010 / .016 in D005; $68.96 is in D005. |
| r-0037 | Berkeley screening | OK | BMC 13.106, fines, 1 to 3 unit owner-occupied exemption verified; passed 2020-04-14, no effective date. |
| r-0038 | Berkeley algo | RISK | D001 states no date (passed to print 2025-11-18); README says March 1, 2026; X018 says "effective January 2026". |
| r-0039 | Santa Ana rent | RISK | Content verified (D084, D085); citation is a descriptive name, not an official cite. |
| r-0040 | Santa Ana JC | RISK | Same citation issue; D085 calls it a separate "Just Cause Eviction Ordinance". |
| r-0041 | Santa Ana algo | OK | X018 "NS-3090 (effective April 2, 2026)", brief "Apr 2026". |
| r-0042 | JC rent | RISK | key_value states no number ("cap formula not stated"); no JC formula exists in any source. 5+ units and 30-year exemption verified. |
| r-0043 | JC algo | OK | New X030 (Ord. 25-057): adopted 2025-05-21, mayor 2025-05-22, real-estate-agent carve-out, $100 to $2,000 per day. "2025-06" consistent. Note: X030 extract calls the FAIR Act "P.L.2025, c.405" (wrong; it is P.L.2026, c.43). |
| r-0044 | Hoboken rent | FIX | Wrong history tag. ecode tags precede their section (X002 line 37 "[Added 9-3-1986]" sits over sec. 155-6.1). The cap (sec. 155-5) sits under "[Amended 2-1-2023 by Ord. No. B-532]"; the B-104 (2019) tag belongs to the tax surcharge. Use 2023-02-01. |
| r-0045 | Hoboken algo | RISK | 2025-07-09 is adoption (B-781); key may hold "2025-07" (brief, X018) or a later effective day. |
| r-0046 | Newark rent | OK | Tag over sec. 19:2-3 is "amended 9-18-2024"; "In no case shall the allowable rent increase exceed 4%" verified. |
| r-0047 | Newark screening | OK | Sec. 2:31-2, 8/5-year lookback, $500/$1,000, two-family exemption verified (X006). |
| r-0048 | Boston screening | RISK | Citation is a page title; content verified (D012). |
| r-0049 | Boston screening | OK | D010 (February 2017) blanket-ban and 5-year rules verified. |
| r-0050 | Cambridge screening | OK | D029 names ch. 14.04 and the owner-occupied 2-family exemption. |

## Cell audit
No-rule claims (16):
- Holding, with evidence: NJ rent (D067 "The State of New Jersey has no laws that establish, govern or control rents"), SD rent, LA algo (D039 is only a motion), Newark algo (T2), Cambridge algo (X026 policy order), Boston and Cambridge rent (c.40P + T5), MA JC (c.186 s.12 at-will termination). Boston and Cambridge deposits, fees, algo, and SF fees are inferences from silence: plausible, not proven.
- Contradicted or doubtful: **Boston JC**. Two supplied docs (D013, D014) cover the HSNA, City of Boston Ordinances sec. 10-11.7, effective 2020-11-06. The category explicitly includes "notice", and stage 1 extracted it as a rule, but consolidation turned it into a no_rule. **Cambridge JC**: same pattern with ch. 8.71 (D031). **Boston rent**: H.3744 (D011, sent to study 9/9/2024) was extracted at stage 1 as a failed rule and dropped.
- MA JC: four supplied c.186 statutes (D050 s.11, D051 s.12, D053 s.18, D058 s.31) are notice-to-quit and retaliation rules. no_rule is legally right, but the key might file one of them here (RISK, low).

Gaps that the corpus can now close or shrink:
- MA screening: new X029 (803 CMR 5.04, supplied link D056) supports a second MA screening rule (CORI only as the final step; eff. 6/11/2021) that is missing. Organizers listed D056 in the corpus, so the key likely has it.
- SF screening: X031 (r-0028 upgrade). JC algo: X030 confirms the date and terms.
- Newark rent: X005 (supplied link D071) contains sec. 2:10-11 "Unconscionable Rent Increase" (added 6-7-2023, amended 8-2-2023), a possible second Newark rule. The capture is cut off after the definitions, so there is no key_value: RISK, do not invent.
- The other 17 gaps (LA fee; SD deposit and fee; Santa Ana deposit, fee, screening; JC, Hoboken, Newark JC, deposit, fee; JC and Hoboken screening): no text in corpus or corpus_extra either way. Keep them as gaps with `unknown`, not no_rule.

Supplied D docs with no record of their own (each line: verdict):
- D004, D009, D042, D043, D082: merged into r-0034/r-0033/r-0021/r-0022/r-0026 (relocation, coverage and rate pages). Right.
- D016: folded into r-0005 (CRD guidance, no section of its own). Right.
- D047: duplicate of S.2983 history. Right.
- D039: motion only, used as LA algo no_rule evidence. Right.
- D011: **wrong to drop.** It is a failed Boston bill; add it with status failed. No lookup impact, possible extraction match.
- D013, D014: **wrong to drop.** HSNA should be a Boston JC rule; D013 line "The Housing Stability Notification Act requires any landlord..." gives a single-line span with citation credit.
- D031: doubtful drop. Cambridge ch. 8.71 is a notice-only rule; D031 says it "does not prevent a landlord from initiating an eviction".
- D050, D051, D053, D058: right as no_rule evidence (no limit on grounds for eviction); low RISK as noted above.

Other checks:
- yields_to and conflicts_with match the texts: 1947.12(d)(3) for LA, SF, Berkeley, Santa Ana rent; 1946.2(i) for the five local JC rules; FAIR Act sec. 6.b for JC and Hoboken.
- Status as of 2026-10-01 is right for all 50 rules.
- Effective-date convention is inconsistent across records. Latest amendment: r-0002, r-0004, r-0005, r-0015 to r-0017, r-0046. Original adoption: r-0030, r-0047. Operative date: r-0001. Wrong tag: r-0044. Decide one rule. Suggested: the date of the version that sets the headline value, which matches the brief's "as amended by AB 12, eff. 7/1/2024" pattern.
- Outside-knowledge tokens: "Cal. Const. art. IV s.8(c)(1)" (r-0006 interaction) and "§ 165.00" (r-0022 citation). "§ 151.00" exists only in CONTRACTS. Every other number in key_value and citation appears somewhere in the sources or the organizer docs (scripted scan).

## Top 10 fixes by expected score impact
1. Add MA screening 803 CMR 5.04 (X029): missing an applying rule costs 2x on about 110 MA addresses, plus an extraction match.
2. Add Boston JC HSNA (sec. 10-11.7, eff. 2020-11-06, span from D013) in place of the no_rule. Optionally add Cambridge ch. 8.71 (D031).
3. r-0044 effective_date 2019-01-16 -> 2023-02-01 (wrong ecode tag).
4. r-0028 citation -> S.F. Police Code art. 49 / sec. 4906, effective 2026-08-10, sharper key_value (X031).
5. r-0007 single-line quoted_span (citation metric) and citation "N.J.S.A. 2A:18-61.1".
6. Trim key_values to the headline: r-0009 "$50 cap, CPI-adjusted yearly", r-0008 "1.5 months' rent" (organizer sample).
7. r-0005 effective_date -> 2020-01-01 (SB 329, brief + X021). Coin flip against 2024-01-01; take the brief's pointer.
8. Pick one effective-date convention and apply it to r-0001/r-0002 (2024-04-01 for both, or the amendment date for both) and to r-0030.
9. Add Boston rent H.3744 as failed (D011): an extraction-only gain.
10. Cite hygiene: r-0010 "N.J.S.A. 10:5-12"; consider "IP 25-21" (r-0014) and "87DDD½" (r-0017) to mirror organizer wording; drop the outside-knowledge interaction text in r-0006.
