-- Analytical queries backing Reconciliation #4 (M1 + sparse archives) and #5 (Inpatient Charge vs Payment)

-- name: m1_observations
SELECT
    o.facility_id,
    f.facility_name,
    f.city_town,
    f.state,
    f.zip_code,
    o.measure_id,
    m.short_label,
    m.unit,
    o.start_date,
    o.end_date,
    o.raw_score,
    o.parsed_score,
    o.raw_sample,
    o.parsed_sample,
    o.raw_footnote,
    o.footnote_text,
    o.source_row_number
FROM observations o
JOIN facility_attributes f ON f.facility_id = o.facility_id
JOIN measure_definitions m ON m.measure_id = o.measure_id
ORDER BY o.facility_id, o.measure_id;

-- name: sparse_archive_diffs
SELECT
    d.facility_id,
    f.facility_name,
    d.measure_id,
    d.from_release,
    d.to_release,
    d.from_score,
    d.to_score,
    d.from_period,
    d.to_period,
    d.change_category,
    d.overlap_months,
    d.interpretation_guardrail
FROM archive_diffs d
JOIN facility_attributes f ON f.facility_id = d.facility_id
ORDER BY d.facility_id, d.measure_id;

-- name: inpatient_weighted_hospital_summary
-- Discharge-weighted totals (never unweighted mean of DRG averages)
SELECT
    d.ccn AS facility_id,
    f.facility_name,
    f.hospital_ownership,
    COUNT(*) AS drg_count,
    SUM(d.tot_dschrgs) AS total_medicare_discharges,
    ROUND(SUM(d.tot_dschrgs * d.avg_submtd_cvrd_chrg) / SUM(d.tot_dschrgs), 2) AS weighted_avg_submitted_charge,
    ROUND(SUM(d.tot_dschrgs * d.avg_tot_pymt_amt) / SUM(d.tot_dschrgs), 2) AS weighted_avg_total_payment,
    ROUND(SUM(d.tot_dschrgs * d.avg_mdcr_pymt_amt) / SUM(d.tot_dschrgs), 2) AS weighted_avg_medicare_payment,
    ROUND(AVG(d.avg_submtd_cvrd_chrg), 2) AS naive_unweighted_charge_do_not_use,
    ROUND(SUM(d.tot_dschrgs * d.avg_tot_pymt_amt) / SUM(d.tot_dschrgs * d.avg_submtd_cvrd_chrg) * 100.0, 1) AS total_payment_pct_of_charge
FROM inpatient_drg_2024 d
JOIN facility_attributes f ON f.facility_id = d.ccn
GROUP BY d.ccn, f.facility_name, f.hospital_ownership
ORDER BY total_medicare_discharges DESC;

-- name: shared_drg_comparison
-- Shared MS-DRGs billed across all 5 hospitals, ordered by total discharges across the 5 facilities
WITH shared AS (
    SELECT drg_cd, SUM(tot_dschrgs) AS cohort_discharges
    FROM inpatient_drg_2024
    GROUP BY drg_cd
    HAVING COUNT(DISTINCT ccn) = 5
)
SELECT
    d.drg_cd,
    d.drg_desc,
    d.ccn AS facility_id,
    f.facility_name,
    d.tot_dschrgs,
    ROUND(d.avg_submtd_cvrd_chrg, 2) AS avg_submitted_charge,
    ROUND(d.avg_tot_pymt_amt, 2) AS avg_total_payment,
    ROUND(d.avg_mdcr_pymt_amt, 2) AS avg_medicare_payment,
    ROUND(d.avg_tot_pymt_amt / d.avg_submtd_cvrd_chrg * 100.0, 1) AS payment_pct_of_charge
FROM inpatient_drg_2024 d
JOIN shared s ON s.drg_cd = d.drg_cd
JOIN facility_attributes f ON f.facility_id = d.ccn
ORDER BY s.cohort_discharges DESC, d.drg_cd, d.avg_tot_pymt_amt DESC;

-- name: hcris_hospital_summary
-- All-payer, inpatient + outpatient Hospital Cost Reports (FY begin/end explicit; never mix with CY DRG denominator)
SELECT
    h.hcris_release_year,
    h.ccn,
    h.hospital_name,
    h.rpt_rec_num,
    h.fy_begin,
    h.fy_end,
    h.period_alignment_status,
    h.report_count_in_year,
    h.rural_versus_urban,
    h.beds,
    h.total_discharges,
    h.medicare_discharges,
    h.medicaid_discharges,
    ROUND(h.total_patient_revenue, 2) AS total_patient_revenue,
    ROUND(h.contractual_allowance, 2) AS contractual_allowance,
    ROUND(h.net_patient_revenue, 2) AS net_patient_revenue,
    ROUND(h.total_costs, 2) AS total_costs,
    ROUND(h.operating_expense, 2) AS operating_expense,
    ROUND(h.net_income_patient_service, 2) AS net_income_patient_service,
    ROUND(h.total_other_income, 2) AS total_other_income,
    ROUND(h.net_income, 2) AS net_income,
    ROUND(h.cost_to_charge_ratio, 6) AS cost_to_charge_ratio,
    ROUND(h.uncompensated_care_cost, 2) AS uncompensated_care_cost,
    ROUND(h.contractual_allowance / NULLIF(h.total_patient_revenue, 0) * 100.0, 1) AS contractual_discount_pct,
    ROUND(h.net_patient_revenue / NULLIF(h.total_patient_revenue, 0) * 100.0, 1) AS net_to_gross_pct,
    ROUND(h.net_income_patient_service / NULLIF(h.net_patient_revenue, 0) * 100.0, 1) AS patient_operating_margin_pct
FROM hcris_cost_reports h
ORDER BY h.hcris_release_year DESC, h.ccn, h.rpt_rec_num;

-- name: cert_2025_error_breakdown
-- Unweighted RY 2025 CERT PUF sample claim lines & distinct claims (NOT national weighted dollar rates; improper payment != fraud)
SELECT
    part,
    review_decision,
    error_code,
    error_category,
    unweighted_claim_line_count,
    unweighted_distinct_claim_count,
    part_total_lines,
    part_total_distinct_claims,
    ROUND(unweighted_line_share_pct, 2) AS unweighted_line_share_pct,
    measurement_scope_note
FROM cert_2025_summary
ORDER BY part, unweighted_claim_line_count DESC, error_code;

-- name: hsa_2025_hospital_catchment
-- 2025 Medicare FFS Inpatient Hospital Service Area summary (suppressed '<11' ZIP rows kept NULL, counted explicitly)
SELECT
    h.ccn,
    f.facility_name,
    f.zip_code AS hospital_zip,
    COUNT(*) AS total_zip_rows,
    SUM(CASE WHEN h.is_suppressed = 0 THEN 1 ELSE 0 END) AS visible_zip_rows,
    SUM(CASE WHEN h.is_suppressed = 1 THEN 1 ELSE 0 END) AS suppressed_zip_rows,
    SUM(COALESCE(h.parsed_total_cases, 0)) AS visible_medicare_cases,
    SUM(CASE WHEN SUBSTR(h.zip_cd_of_residence, 1, 2) IN ('37', '38') AND h.is_suppressed = 0 THEN h.parsed_total_cases ELSE 0 END) AS visible_tn_zip_cases,
    ROUND(
        100.0 * SUM(CASE WHEN SUBSTR(h.zip_cd_of_residence, 1, 2) IN ('37', '38') AND h.is_suppressed = 0 THEN h.parsed_total_cases ELSE 0 END)
        / NULLIF(SUM(COALESCE(h.parsed_total_cases, 0)), 0),
        1
    ) AS pct_visible_cases_tn_zips
FROM hospital_service_area_2025 h
JOIN facility_attributes f ON f.facility_id = h.ccn
GROUP BY h.ccn, f.facility_name, f.zip_code
ORDER BY visible_medicare_cases DESC;

-- name: hsa_2025_top_feeder_zips
-- Top visible feeder ZIPs per Nashville hospital (excludes suppressed '*' rows without coercing to zero)
WITH ranked AS (
    SELECT
        h.ccn,
        f.facility_name,
        h.zip_cd_of_residence,
        h.parsed_total_cases,
        h.parsed_total_days_of_care,
        ROUND(h.parsed_total_charges, 2) AS parsed_total_charges,
        ROW_NUMBER() OVER (PARTITION BY h.ccn ORDER BY h.parsed_total_cases DESC, h.zip_cd_of_residence) AS rn
    FROM hospital_service_area_2025 h
    JOIN facility_attributes f ON f.facility_id = h.ccn
    WHERE h.is_suppressed = 0 AND h.parsed_total_cases IS NOT NULL
)
SELECT ccn, facility_name, rn AS zip_rank, zip_cd_of_residence, parsed_total_cases, parsed_total_days_of_care, parsed_total_charges
FROM ranked
WHERE rn <= 5
ORDER BY ccn, zip_rank;
