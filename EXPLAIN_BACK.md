# Five-Minute Explain-Back Guide (`S1`)

Review these questions out loud without looking at the code before any analyst or operations interview:

### 1. Why are there 10 rows in `nashville_ed_observations.csv` when we only selected 5 hospitals?
Because the **grain** of CMS `Timely_and_Effective_Care-Hospital.csv` (`yv7e-xc69`) is **one row per facility + measure + collection period**, not one row per hospital. Five hospitals × two measures (`OP_18b` and `OP_22`) equals 10 observations.

### 2. Why can’t you compare `OP_18b` and `OP_22` as if they happened in the same year?
Inside the exact same November 2026 CMS release CSV:
- **`OP_18b`** (median ED arrival-to-departure minutes for discharged patients) was collected over **01/01/2025 – 12/31/2025**.
- **`OP_22`** (% who left before being seen) was collected over **01/01/2024 – 12/31/2024**.
Always check `Start Date` and `End Date` per measure—never assume one release file shares one calendar period.

### 3. Why doesn’t Ascension Saint Thomas show `0%` for `OP_22`?
CMS published `"Not Available"` with **Footnote 5** (*"Results are not available for this reporting period."*). Turning unavailable strings into `0` makes missing data look like 0% walkouts—one of the classic hospital reporting bugs. Footnote 5 also does **not** explain why data was unavailable.

### 4. What does `OP_18b` actually measure (and what doesn’t it measure)?
It is the **historical 2025 median time** in minutes from ED arrival to departure **for patients who were discharged** (transfers, admitted patients, and psychiatric/mental-health visits are excluded). It is **not** today’s live ER wait time, **not** time until first clinician, and **not** Medicare-only.

### 5. Why do we reconcile `raw_total == retained_in_scope + discarded_out_of_scope`?
So we can prove all 161,313 CMS rows were accounted for—10 retained in scope and 161,303 out-of-scope hospitals/measures explicitly accounted for rather than silently dropped—and so duplicate keys in the hospital dimension fail loudly instead of multiplying rows in joins.
