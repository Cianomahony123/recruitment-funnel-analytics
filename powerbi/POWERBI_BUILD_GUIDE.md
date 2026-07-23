# Power BI Build Guide — Recruitment Funnel & Sourcing ROI

## Step 1 — Generate the data workbook

```bash
python powerbi/export_for_powerbi.py
```

This produces `powerbi/RecruitmentFunnel_PowerBI.xlsx` with six sheets.

---

## Step 2 — Import into Power BI Desktop

1. Open Power BI Desktop → **Get Data → Excel Workbook**
2. Select `RecruitmentFunnel_PowerBI.xlsx`
3. In the Navigator, tick **all six sheets** → Load

---

## Step 3 — Set up relationships (Model view)

| From table | From column | To table | To column | Cardinality |
|---|---|---|---|---|
| Pipeline_Stages | candidate_id | Candidates | candidate_id | Many → One |
| Channel_ROI | source_channel | Candidates | source_channel | One → Many |
| Recruiter_Performance | recruiter | Pipeline_Stages | recruiter | One → Many |
| Monthly_Trends | year_month | Pipeline_Stages | stage_date *(date)* | One → Many |

---

## Step 4 — Add DAX measures

Open `measures.dax`. For each block:
1. Click the target table in the Fields pane
2. **New Measure** → paste the formula → Enter

Add all measures to the **Pipeline_Stages** table unless noted.

---

## Step 5 — Build the report pages

### Page 1 — Executive Summary (4 KPI cards)
| Card | Measure |
|---|---|
| Total Placements | `Total Placed` |
| Overall Placement Rate | `Placement Rate Label` |
| Avg Days to Fill | `Avg Days to Fill` |
| Best Sourcing Channel | `Best Channel` |

### Page 2 — Funnel Drop-off
- **Visual:** Funnel chart
- **Category:** `Funnel_Summary[stage]` (sort by `stage_order`)
- **Values:** `Funnel_Summary[candidate_count]`
- Add a **Table** below showing `stage`, `candidate_count`, `drop_off_pct`

### Page 3 — Sourcing Channel ROI
- **Visual 1:** Clustered bar chart
  - Axis: `Channel_ROI[source_channel]`
  - Values: `Channel_ROI[cost_per_hire]` (sort ascending)
  - Title: *Cost per Hire by Channel*
- **Visual 2:** Clustered bar chart
  - Axis: `Channel_ROI[source_channel]`
  - Values: `Channel_ROI[placement_rate]`
  - Title: *Placement Rate % by Channel*
- **Visual 3:** Scatter chart
  - X-axis: `Channel_ROI[cost_per_hire]`
  - Y-axis: `Channel_ROI[placement_rate]`
  - Details: `Channel_ROI[source_channel]`
  - Title: *Cost vs Quality quadrant*

### Page 4 — Funnel Conversion Heatmap
- **Visual:** Matrix
  - Rows: `Pipeline_Stages[source_channel]`
  - Columns: `Pipeline_Stages[stage]` (sort by `stage_order`)
  - Values: `Total Sourced` (count)
- Enable **Conditional formatting → Background colour** on values
- This reproduces the channel × stage heatmap from the Plotly dashboard

### Page 5 — Recruiter Performance
- **Visual 1:** Bar chart
  - Axis: `Recruiter_Performance[recruiter]`
  - Values: `Recruiter_Performance[placements]`
- **Visual 2:** Bar chart
  - Axis: `Recruiter_Performance[recruiter]`
  - Values: `Recruiter_Performance[placement_rate_pct]`
- **Visual 3:** Table with all columns from `Recruiter_Performance`

### Page 6 — Monthly Trends
- **Visual:** Line chart
  - X-axis: `Monthly_Trends[year_month]`
  - Values: `Monthly_Trends[Sourced]`, `Monthly_Trends[Placed]`
  - Title: *Sourced vs Placed over 18 Months*

---

## Step 6 — Slicers (add to every page)

| Slicer | Field |
|---|---|
| Source Channel | `Candidates[source_channel]` |
| Recruiter | `Pipeline_Stages[recruiter]` |
| Date Range | `Pipeline_Stages[stage_date]` |

---

## Step 7 — Save as .pbix

File → Save As → `RecruitmentFunnel.pbix`

Add the `.pbix` file to this repo so reviewers can open it directly in Power BI Desktop.
