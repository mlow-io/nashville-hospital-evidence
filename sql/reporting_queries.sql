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
