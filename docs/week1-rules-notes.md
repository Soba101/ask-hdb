# Week 1 rules notes

Read on 2026-10-20, hdb.gov.sg only. Values are in `rules/2026-10.yaml`.

## Findings (unclear, missing, or disagreeing)

1. **Income ceiling is 16,000 / 24,000, not 14,000 / 21,000.** Current pages show 16,000 (families) and 24,000 (extended). Older sources show 14,000 / 21,000. The revision is in the Annex A press PDF, which I could not read as text; the live pages already show the new numbers.
2. **Singles income ceiling is stated three ways.**
   - Singles main page: resale Plus flat 16,000; Unclassified/Standard none.
   - Singles CPF Housing Grant page: 8,000 if buying alone, 16,000 with family or other singles.
   - HDB loan page: 8,000 for singles (SSC scheme).
   The grant page and loan page agree (8,000 alone). The main page's 16,000 for Plus may be for non-single-alone cases. Not resolved.
3. **Singles EHG ceiling with parents.** The page says household 9,000 for "a resale flat with your parents", but the amount table for that case uses only the single's own income and stops at 4,500. Unclear which test applies. I stored 9,000 under a separate key.
4. **Families page lumps Plus/Prime and Unclassified/Standard resale** in one column pair. "No income ceiling" is written under the Unclassified/Standard column only. For Plus/Prime I assume the BTO ceilings (16,000 / 24,000) apply; the page does not say so outright.
5. **LTV is 75%, not 80%.** The 2022 press release (80%) is superseded. The loan page gives 75% for resale applications from 2024-08-20.
6. **TDSR is not on the HDB loan page.** The page gives only "monthly instalments up to 30% of income" (stored as `msr_pct_of_monthly_income`). TDSR is a MAS rule for bank loans and is left out. The page says "currently" 3.0% for the qualifying floor rate.
7. **Pro-rating formulas are not published.** EHG and LTV are pro-rated when the lease does not cover the youngest buyer to age 95. HDB gives no formula; both need the HFE calculator or a loan page example.
8. **Second-timer rules for families.** Only the first-timer plus second-timer couple case is stored. Two-second-timer couples get no CPF grants (only PHG); this is implied, not stated on one line.
9. **Resale levy:** the pages say it does not apply to resale buyers. Stored as false. No further levy rules recorded.
10. **EHG tables** come from PDFs linked on the EHG pages. The singles PDF also has a "non-resident spouse" table (same bands as the mixed-couple table). Not stored (out of v1 scope).
11. **PHG** has no income ceiling per the families page note. Singles PHG for "near" requires a 2 to 5-room flat; "with" any type.
12. **HDB loan worked example:** none published on the pages I read. The five examples in the YAML are from the two EHG pages. Example E and H quote a Family Grant; example F (5-room, not eligible for EHG) quotes 40,000, which matches the SC/SPR 5-room amount.
13. **Concessionary rate (2.60%)** changes quarterly. Re-check each January, April, July and October.

## Not read
- Annex A PDF (2026 income ceiling change): text could not be extracted.
- Extended-family income ceiling guide PDF.
- Step-Up grant, Top-Up grant detail, seniors, non-resident cases (out of v1 scope).

## URLs used
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families/cpf-housing-grants
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families/enhanced-cpf-housing-grant
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families/proximity-housing-grant
- https://www.hdb.gov.sg/-/media/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families/enhanced-cpf-housing-grant/EHG-amount-Families.pdf
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles/cpf-housing-grant
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles/enhanced-cpf-housing-grant
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles/proximity-housing-grant
- https://www.hdb.gov.sg/-/media/buying-a-flat/flat-grant-and-loan-eligibility/singles/enhanced-cpf-housing-grant/EHG-amount-Singles.pdf
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/housing-loan/housing-loan-from-hdb
- https://www.hdb.gov.sg/managing-my-home/finances/loan-matters/interest-rate

## Resolved 2026-10-20 (re-read on hdb.gov.sg, notes 2, 3 and 4 above)
- **Singles ceilings.** CPF Housing Grant: 8,000 alone, 16,000 with family or other singles. HDB loan: 8,000 (SSC scheme).
  Plus flat: 16,000 to qualify for grants (not PHG) and the HDB loan, so the stricter 8,000 still applies alone.
  Unclassified/Standard with no grant and no HDB loan: no ceiling. 2-room Flexi and 2-room Prime resale: 8,000.
- **Singles EHG is two tests.** Eligibility uses household income (all applicants and occupiers): 4,500 alone,
  9,000 with parents. The amount is looked up from the single's own income only.
- **Plus and Prime resale** share the new-flat ceilings (16,000, or 24,000 extended family). A 3-room flat is
  16,000 or 8,000 depending on project (not modelled; flagged as needs_check).
- Still not checked: the EHG amount PDFs (read by the first pass), and the 3-room project ceiling.
- Data note: 318 raw resale rows are exact duplicates. They are kept, because the data has no unit ID and
  they may be real separate sales.
- **PHG and second-timers (re-read 2026-10-20):** neither PHG page has a first-timer rule; the only condition
  is not having taken the PHG before. Amounts are the same for everyone. So two-second-timer couples can get the PHG.
- **Singles buying with parents:** the CPF Housing Grant ceiling is 16,000 ("with your family"), per the page intro.
