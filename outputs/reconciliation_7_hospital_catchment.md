# Reconciliation #7: Five-Hospital Medicare Catchment (`M2` CMS Hospital Service Area 2025)

> [!IMPORTANT]
> **Scope & Suppression Guardrail:** CMS Hospital Service Area (`8708ca8b-8636-44ed-8303-724cbfaf78ad`) covers **Medicare Fee-for-Service inpatient stays only**—not all-payer market share, not outpatient visits, and not driving/travel time. Patient ZIPs with `<11` Medicare cases are masked with `*` by CMS (`is_suppressed=1`); they remain `NULL` in SQLite (never coerced to `0` or `5`) and are counted explicitly.

## Hospital Patient-Origin Summary

| CCN | Hospital | Hospital ZIP | Total ZIP Rows | Visible ZIPs (`>=11` Cases) | Suppressed `<11` ZIP Rows (`*`) | Visible Medicare Cases | TN ZIP (`37x/38x`) Cases | % Visible From TN ZIPs |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `440039` | VANDERBILT UNIVERSITY MEDICAL CENTER | `37232` | 1,717 | 296 | 1,421 | 17,563 | 15,763 | 89.8% |
| `440082` | ASCENSION SAINT THOMAS HOSPITAL | `37205` | 1,043 | 203 | 840 | 17,271 | 16,652 | 96.4% |
| `440161` | TRISTAR CENTENNIAL MEDICAL CENTER | `37203` | 935 | 166 | 769 | 11,775 | 10,912 | 92.7% |
| `440073` | MAURY REGIONAL HOSPITAL | `38401` | 272 | 42 | 230 | 6,922 | 6,911 | 99.8% |
| `440029` | WILLIAMSON MEDICAL CENTER | `37067` | 357 | 33 | 324 | 3,516 | 3,516 | 100.0% |

## Top 5 Visible Feeder Patient ZIPs per Hospital

| CCN | Hospital | Rank | Patient ZIP5 | Visible Cases | Visible Days of Care | Visible Charges |
|---|---|---:|---|---:|---:|---:|
| `440029` | WILLIAMSON MEDICAL CENTER | 1 | `37064` | 924 | 4,220 | $36,324,280 |
| `440029` | WILLIAMSON MEDICAL CENTER | 2 | `37174` | 498 | 2,300 | $21,543,479 |
| `440029` | WILLIAMSON MEDICAL CENTER | 3 | `37027` | 408 | 1,870 | $16,962,939 |
| `440029` | WILLIAMSON MEDICAL CENTER | 4 | `37067` | 391 | 1,993 | $16,456,287 |
| `440029` | WILLIAMSON MEDICAL CENTER | 5 | `38401` | 189 | 894 | $8,830,269 |
| `440039` | VANDERBILT UNIVERSITY MEDICAL CENTER | 1 | `37027` | 438 | 2,679 | $65,639,864 |
| `440039` | VANDERBILT UNIVERSITY MEDICAL CENTER | 2 | `37087` | 419 | 2,850 | $66,092,037 |
| `440039` | VANDERBILT UNIVERSITY MEDICAL CENTER | 3 | `37013` | 409 | 2,788 | $55,404,594 |
| `440039` | VANDERBILT UNIVERSITY MEDICAL CENTER | 4 | `37064` | 372 | 2,094 | $53,442,314 |
| `440039` | VANDERBILT UNIVERSITY MEDICAL CENTER | 5 | `37221` | 349 | 2,109 | $46,360,178 |
| `440073` | MAURY REGIONAL HOSPITAL | 1 | `38401` | 2,093 | 8,608 | $120,694,110 |
| `440073` | MAURY REGIONAL HOSPITAL | 2 | `37091` | 627 | 2,686 | $37,521,803 |
| `440073` | MAURY REGIONAL HOSPITAL | 3 | `38464` | 518 | 2,107 | $31,822,817 |
| `440073` | MAURY REGIONAL HOSPITAL | 4 | `38462` | 490 | 2,011 | $26,870,398 |
| `440073` | MAURY REGIONAL HOSPITAL | 5 | `38474` | 410 | 1,753 | $22,456,812 |
| `440082` | ASCENSION SAINT THOMAS HOSPITAL | 1 | `37221` | 956 | 4,987 | $78,426,641 |
| `440082` | ASCENSION SAINT THOMAS HOSPITAL | 2 | `37205` | 612 | 2,816 | $45,563,659 |
| `440082` | ASCENSION SAINT THOMAS HOSPITAL | 3 | `37207` | 481 | 2,683 | $36,280,239 |
| `440082` | ASCENSION SAINT THOMAS HOSPITAL | 4 | `37218` | 442 | 2,700 | $38,946,347 |
| `440082` | ASCENSION SAINT THOMAS HOSPITAL | 5 | `37027` | 425 | 1,901 | $45,175,664 |
| `440161` | TRISTAR CENTENNIAL MEDICAL CENTER | 1 | `37015` | 432 | 2,193 | $64,838,825 |
| `440161` | TRISTAR CENTENNIAL MEDICAL CENTER | 2 | `37207` | 372 | 2,109 | $66,012,421 |
| `440161` | TRISTAR CENTENNIAL MEDICAL CENTER | 3 | `37075` | 370 | 2,042 | $92,647,494 |
| `440161` | TRISTAR CENTENNIAL MEDICAL CENTER | 4 | `37055` | 300 | 1,679 | $75,875,760 |
| `440161` | TRISTAR CENTENNIAL MEDICAL CENTER | 5 | `37221` | 287 | 1,181 | $39,253,182 |
