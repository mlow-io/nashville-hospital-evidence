-- Relational schema for five-hospital Nashville ED, sparse CMS archives, and Inpatient RCM (M1 + S2)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_versions (
    version_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    release_date TEXT NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    bytes INTEGER NOT NULL,
    raw_rows_scanned INTEGER NOT NULL,
    retained_rows INTEGER NOT NULL,
    discarded_rows INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS facility_attributes (
    facility_id TEXT PRIMARY KEY,
    facility_name TEXT NOT NULL,
    address TEXT NOT NULL,
    city_town TEXT NOT NULL,
    state TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    county_parish TEXT NOT NULL,
    hospital_type TEXT NOT NULL,
    hospital_ownership TEXT NOT NULL,
    emergency_services TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS measure_definitions (
    measure_id TEXT PRIMARY KEY,
    short_label TEXT NOT NULL,
    cms_measure_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    cohort_note TEXT NOT NULL,
    comparable_notes TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observations (
    facility_id TEXT NOT NULL REFERENCES facility_attributes(facility_id),
    measure_id TEXT NOT NULL REFERENCES measure_definitions(measure_id),
    version_id TEXT NOT NULL REFERENCES source_versions(version_id),
    period_label TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    raw_score TEXT NOT NULL,
    parsed_score INTEGER,
    raw_sample TEXT NOT NULL,
    parsed_sample INTEGER,
    raw_footnote TEXT NOT NULL,
    footnote_text TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    PRIMARY KEY (facility_id, measure_id, version_id)
);

CREATE TABLE IF NOT EXISTS archive_events (
    archive_date TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    has_timely_care INTEGER NOT NULL,
    timely_care_entry TEXT,
    serving_release_date TEXT,
    rejected_trap_entries TEXT NOT NULL,
    status_note TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS archive_observations (
    archive_release_date TEXT NOT NULL,
    facility_id TEXT NOT NULL REFERENCES facility_attributes(facility_id),
    measure_id TEXT NOT NULL REFERENCES measure_definitions(measure_id),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    raw_score TEXT NOT NULL,
    parsed_score INTEGER,
    raw_sample TEXT NOT NULL,
    parsed_sample INTEGER,
    raw_footnote TEXT NOT NULL,
    footnote_text TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    PRIMARY KEY (archive_release_date, facility_id, measure_id)
);

CREATE TABLE IF NOT EXISTS archive_diffs (
    facility_id TEXT NOT NULL REFERENCES facility_attributes(facility_id),
    measure_id TEXT NOT NULL REFERENCES measure_definitions(measure_id),
    from_release TEXT NOT NULL,
    to_release TEXT NOT NULL,
    from_score TEXT NOT NULL,
    to_score TEXT NOT NULL,
    from_period TEXT NOT NULL,
    to_period TEXT NOT NULL,
    change_category TEXT NOT NULL,
    overlap_months INTEGER NOT NULL,
    interpretation_guardrail TEXT NOT NULL,
    PRIMARY KEY (facility_id, measure_id, from_release, to_release)
);

CREATE TABLE IF NOT EXISTS inpatient_drg_2024 (
    ccn TEXT NOT NULL REFERENCES facility_attributes(facility_id),
    drg_cd TEXT NOT NULL,
    drg_desc TEXT NOT NULL,
    tot_dschrgs INTEGER NOT NULL,
    avg_submtd_cvrd_chrg REAL NOT NULL,
    avg_tot_pymt_amt REAL NOT NULL,
    avg_mdcr_pymt_amt REAL NOT NULL,
    PRIMARY KEY (ccn, drg_cd)
);

CREATE TABLE IF NOT EXISTS hcris_cost_reports (
    rpt_rec_num TEXT NOT NULL,
    hcris_release_year TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    ccn TEXT NOT NULL REFERENCES facility_attributes(facility_id),
    hospital_name TEXT NOT NULL,
    fy_begin TEXT NOT NULL,
    fy_end TEXT NOT NULL,
    period_alignment_status TEXT NOT NULL,
    report_count_in_year INTEGER NOT NULL,
    rural_versus_urban TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    type_of_control TEXT NOT NULL,
    beds INTEGER,
    medicare_discharges INTEGER,
    medicaid_discharges INTEGER,
    total_discharges INTEGER,
    inpatient_charges REAL,
    outpatient_charges REAL,
    total_patient_revenue REAL,
    contractual_allowance REAL,
    net_patient_revenue REAL,
    total_costs REAL,
    operating_expense REAL,
    net_income_patient_service REAL,
    total_other_income REAL,
    net_income REAL,
    cost_to_charge_ratio REAL,
    charity_care_cost REAL,
    bad_debt_expense REAL,
    uncompensated_care_cost REAL,
    medicaid_charges REAL,
    medicaid_net_revenue REAL,
    PRIMARY KEY (rpt_rec_num, hcris_release_year)
);

CREATE TABLE IF NOT EXISTS cert_2025_summary (
    part TEXT NOT NULL,
    review_decision TEXT NOT NULL,
    error_code TEXT NOT NULL,
    error_category TEXT NOT NULL,
    unweighted_claim_line_count INTEGER NOT NULL,
    unweighted_distinct_claim_count INTEGER NOT NULL,
    part_total_lines INTEGER NOT NULL,
    part_total_distinct_claims INTEGER NOT NULL,
    unweighted_line_share_pct REAL NOT NULL,
    measurement_scope_note TEXT NOT NULL,
    PRIMARY KEY (part, review_decision, error_code)
);

CREATE TABLE IF NOT EXISTS hospital_service_area_2025 (
    ccn TEXT NOT NULL REFERENCES facility_attributes(facility_id),
    zip_cd_of_residence TEXT NOT NULL,
    raw_total_cases TEXT NOT NULL,
    parsed_total_cases INTEGER,
    raw_total_days_of_care TEXT NOT NULL,
    parsed_total_days_of_care INTEGER,
    raw_total_charges TEXT NOT NULL,
    parsed_total_charges REAL,
    is_suppressed INTEGER NOT NULL,
    PRIMARY KEY (ccn, zip_cd_of_residence)
);
