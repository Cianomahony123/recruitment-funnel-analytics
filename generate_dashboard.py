"""
generate_dashboard.py

Generates a standalone interactive Plotly dashboard from any SQLite database
that follows the recruitment funnel schema (clients, roles, candidates,
pipeline_stages tables).

Usage:
    python generate_dashboard.py
    python generate_dashboard.py --db path/to/other.db
    python generate_dashboard.py --db other.db --costs "LinkedIn=45,Referral=10,JobBoard=60"
    python generate_dashboard.py --title "Acme Recruitment" --author "Jane Smith"
    python generate_dashboard.py --out path/to/output.html
"""

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# ── CLI ───────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Generate recruitment funnel dashboard")
parser.add_argument("--db",     default="database/recruitment.db",
                    help="Path to SQLite database (default: database/recruitment.db)")
parser.add_argument("--out",    default="outputs/dashboard.html",
                    help="Output HTML path (default: outputs/dashboard.html)")
parser.add_argument("--title",  default="Recruitment Funnel & Sourcing ROI",
                    help="Dashboard title shown in header")
parser.add_argument("--author", default="Cian O'Mahony",
                    help="Author name shown in header subtitle")
parser.add_argument("--costs",  default="",
                    help="Override channel costs: 'LinkedIn=45,Referral=10,...'")
args = parser.parse_args()

OUT_PATH = Path(args.out)
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── default cost assumptions (overridable via --costs) ────────────────────────

DEFAULT_COST_PER_CHANNEL = {
    "LinkedIn": 45, "Referral": 10, "Job Board": 60,
    "Agency Database": 15, "Cold Outreach": 25,
}
DEFAULT_FALLBACK_COST = 30  # for any channel not in the table above

if args.costs:
    for pair in args.costs.split(","):
        k, v = pair.strip().split("=")
        DEFAULT_COST_PER_CHANNEL[k.strip()] = int(v.strip())

# ── load data ─────────────────────────────────────────────────────────────────

conn = sqlite3.connect(args.db)

# Use cleaned table if available; otherwise normalise on the fly
CANONICAL = {
    "linkedin": "LinkedIn", "referral": "Referral",
    "job board": "Job Board", "agency database": "Agency Database",
    "cold outreach": "Cold Outreach",
}
try:
    candidates = pd.read_sql("SELECT * FROM candidates_clean", conn)
except Exception:
    candidates = pd.read_sql("SELECT * FROM candidates", conn)
    candidates["source_channel"] = (
        candidates["source_channel"].str.strip().str.lower()
        .map(CANONICAL)
        .fillna(candidates["source_channel"].str.strip())
    )
    dup_cols = ["source_channel", "role_applied", "years_experience",
                "expected_salary", "date_sourced"]
    candidates = candidates.drop_duplicates(subset=dup_cols, keep="first")

pipeline = pd.read_sql("SELECT * FROM pipeline_stages", conn)
roles    = pd.read_sql("SELECT * FROM roles",           conn)
clients  = pd.read_sql("SELECT * FROM clients",         conn)
conn.close()

pipeline["stage_date"] = pd.to_datetime(pipeline["stage_date"])
roles["date_opened"]   = pd.to_datetime(roles["date_opened"])

pipeline  = pipeline.merge(candidates[["candidate_id", "source_channel"]],
                           on="candidate_id", how="left")
roles_ext = roles.merge(clients[["client_id", "industry", "client_name"]], on="client_id")
pipeline  = pipeline.merge(
    roles_ext[["role_id", "industry", "date_opened", "role_title"]],
    on="role_id", how="left"
)

# ── detect stages and date range from the data ────────────────────────────────

STAGE_PREFERRED = ["Sourced", "Screened", "Interviewed", "Offered", "Placed"]
stages_in_db    = pipeline["stage"].dropna().unique().tolist()
STAGE_ORDER     = [s for s in STAGE_PREFERRED if s in stages_in_db]
if not STAGE_ORDER:
    STAGE_ORDER = sorted(stages_in_db)

date_min = pipeline["stage_date"].min()
date_max = pipeline["stage_date"].max()
date_subtitle = f"{date_min.strftime('%b %Y')} – {date_max.strftime('%b %Y')}"

# ── summary stats ─────────────────────────────────────────────────────────────

n_sourced  = pipeline[pipeline["stage"] == "Sourced"]["candidate_id"].nunique()
n_placed   = pipeline[pipeline["stage"] == "Placed"]["candidate_id"].nunique()
n_roles    = roles_ext["role_id"].nunique()
n_clients  = clients["client_id"].nunique()
place_rate = round(n_placed / n_sourced * 100, 1) if n_sourced else 0

placed_df = pipeline[pipeline["stage"] == "Placed"].copy()
first_pl  = (
    placed_df.sort_values("stage_date")
    .groupby("role_id")
    .agg(date_placed=("stage_date", "first"), date_opened=("date_opened", "first"))
    .reset_index()
)
first_pl["days_to_fill"] = (
    (first_pl["date_placed"] - first_pl["date_opened"]).dt.days.clip(lower=1)
)
avg_ttf = round(first_pl["days_to_fill"].mean(), 1) if len(first_pl) else 0

# ── branding ──────────────────────────────────────────────────────────────────

BLUE   = "#2563EB"
DARK   = "#1E3A5F"
GREY   = "#94A3B8"
LGREY  = "#E2E8F0"
AMBER  = "#F59E0B"

BASE_LAYOUT = dict(
    font=dict(family="system-ui, -apple-system, sans-serif", size=12, color="#334155"),
    paper_bgcolor="white",
    plot_bgcolor="white",
    hoverlabel=dict(bgcolor="white", bordercolor=LGREY,
                    font=dict(size=12, color="#1E293B")),
)
DEFAULT_MARGIN = dict(l=16, r=16, t=52, b=44)


def title_style(text):
    return dict(text=text, font=dict(size=14, color=DARK, weight="bold"), pad=dict(b=8))


def colour_scale(series, high_is_good=True):
    """Return a list of colours with the best value highlighted in BLUE."""
    best = series.max() if high_is_good else series.min()
    return [BLUE if v == best else GREY for v in series]


# ── FIG 1: funnel drop-off ────────────────────────────────────────────────────

stage_counts = (
    pipeline[pipeline["stage"].isin(STAGE_ORDER)]
    .groupby("stage")["candidate_id"].nunique()
    .reindex(STAGE_ORDER)
    .fillna(0).astype(int)
)
pct = (stage_counts / max(stage_counts.get("Sourced", 1), 1) * 100).round(1)

fig_funnel = go.Figure(go.Bar(
    x=stage_counts.values,
    y=STAGE_ORDER,
    orientation="h",
    marker_color=[BLUE if s == "Placed" else "#93C5FD" for s in STAGE_ORDER],
    # labels inside the bar — no outside clipping
    text=[f"<b>{int(v):,}</b>  {p}%" for v, p in zip(stage_counts.values, pct)],
    textposition="inside",
    insidetextanchor="start",
    textfont=dict(color="white", size=12),
    hovertemplate="<b>%{y}</b><br>%{x:,} candidates (%{customdata}%)<extra></extra>",
    customdata=pct.values,
    cliponaxis=False,
))
fig_funnel.update_layout(
    **BASE_LAYOUT,
    margin=DEFAULT_MARGIN,
    title=title_style("Funnel Drop-off by Stage"),
    xaxis=dict(title="Candidates", showgrid=True, gridcolor="#F1F5F9",
               zeroline=False, automargin=True),
    yaxis=dict(autorange="reversed", showgrid=False, automargin=True),
    showlegend=False,
)

# ── FIG 2: time-to-fill trend ─────────────────────────────────────────────────

first_pl["month"] = first_pl["date_placed"].dt.to_period("M")
monthly = (
    first_pl.groupby("month")
    .agg(avg_days=("days_to_fill", "mean"), placements=("role_id", "count"))
    .reset_index()
)
monthly["month_dt"] = monthly["month"].dt.to_timestamp()
monthly["avg_days"] = monthly["avg_days"].round(1)

fig_ttf = go.Figure()
fig_ttf.add_trace(go.Bar(
    x=monthly["month_dt"], y=monthly["placements"],
    name="Placements", marker_color=LGREY,
    yaxis="y2",
    hovertemplate="<b>%{x|%b %Y}</b><br>%{y} placements<extra></extra>",
))
fig_ttf.add_trace(go.Scatter(
    x=monthly["month_dt"], y=monthly["avg_days"],
    name="Avg days to fill", mode="lines+markers",
    line=dict(color=BLUE, width=2.5), marker=dict(size=6, color=BLUE),
    hovertemplate="<b>%{x|%b %Y}</b><br>%{y:.0f} days to fill<extra></extra>",
))
fig_ttf.update_layout(
    **BASE_LAYOUT,
    title=title_style("Time-to-Fill Trend"),
    margin=dict(l=16, r=60, t=52, b=44),  # extra right for second y-axis label
    xaxis=dict(
        showgrid=False, zeroline=False, automargin=True,
        tickformat="%b %y",   # "Jan 24" style — half the width of full dates
        nticks=10,            # at most 10 ticks across 18 months
        tickangle=-30,
    ),
    yaxis=dict(title="Avg Days to Fill", color=BLUE,
               showgrid=True, gridcolor="#F1F5F9", rangemode="tozero"),
    yaxis2=dict(title="Placements", overlaying="y", side="right",
                showgrid=False, rangemode="tozero", color=GREY),
    legend=dict(orientation="h", y=-0.18, x=0, xanchor="left",
                font=dict(size=11)),
)

# ── FIG 3: sourcing ROI ───────────────────────────────────────────────────────

ch = (
    pipeline[pipeline["stage"].isin(["Sourced", "Placed"])]
    .groupby(["source_channel", "stage"])["candidate_id"]
    .nunique().unstack(fill_value=0)
)
if "Sourced" not in ch.columns:
    ch["Sourced"] = 0
if "Placed" not in ch.columns:
    ch["Placed"] = 0

ch["cost_per_sourced"] = ch.index.map(DEFAULT_COST_PER_CHANNEL).fillna(DEFAULT_FALLBACK_COST)
ch["total_spend"]      = ch["Sourced"] * ch["cost_per_sourced"]
ch["cost_per_hire"]    = (ch["total_spend"] / ch["Placed"].replace(0, np.nan)).round(0)
ch["placement_rate"]   = (ch["Placed"] / ch["Sourced"].replace(0, np.nan) * 100).round(1)
ch = ch.dropna(subset=["cost_per_hire"]).sort_values("cost_per_hire")

fig_roi = go.Figure()
fig_roi.add_trace(go.Bar(
    name="Cost Per Hire",
    x=ch.index,
    y=ch["cost_per_hire"],
    marker_color=colour_scale(ch["cost_per_hire"], high_is_good=False),
    hovertemplate="<b>%{x}</b><br>£%{y:,.0f} per hire<extra></extra>",
    yaxis="y",
))
fig_roi.add_trace(go.Scatter(
    name="Placement Rate",
    x=ch.index,
    y=ch["placement_rate"],
    mode="markers",
    marker=dict(size=13, color=AMBER, symbol="diamond",
                line=dict(width=1.5, color="white")),
    hovertemplate="<b>%{x}</b><br>%{y:.1f}% placement rate<extra></extra>",
    yaxis="y2",
))
fig_roi.update_layout(
    **BASE_LAYOUT,
    title=title_style("Sourcing ROI — Cost Per Hire & Placement Rate"),
    margin=dict(l=16, r=60, t=52, b=56),
    xaxis=dict(showgrid=False, automargin=True, tickangle=-20),
    yaxis=dict(title="Cost Per Hire (£)", showgrid=True, gridcolor="#F1F5F9",
               rangemode="tozero", automargin=True),
    yaxis2=dict(title="Placement Rate (%)", overlaying="y", side="right",
                showgrid=False, rangemode="tozero", color=AMBER, automargin=True),
    legend=dict(orientation="h", y=-0.22, x=0, xanchor="left", font=dict(size=11)),
    # disclaimer as a proper subtitle, not a clipped annotation
    title_text=(
        "Sourcing ROI — Cost Per Hire & Placement Rate"
        "<br><sup style='color:#94A3B8'>Cost figures are illustrative assumptions "
        "(£10–£60 per candidate sourced)</sup>"
    ),
)

# ── FIG 4: channel heatmap ────────────────────────────────────────────────────

hm = (
    pipeline[pipeline["stage"].isin(STAGE_ORDER)]
    .groupby(["source_channel", "stage"])["candidate_id"]
    .nunique().unstack(fill_value=0)
    .reindex(columns=STAGE_ORDER, fill_value=0)
)
hm_pct = (hm.div(hm["Sourced"].replace(0, np.nan), axis=0) * 100).round(1).fillna(0)

fig_heatmap = go.Figure(go.Heatmap(
    z=hm_pct.values,
    x=STAGE_ORDER,
    y=hm_pct.index.tolist(),
    colorscale="Blues",
    text=hm_pct.values,
    texttemplate="%{text:.0f}%",
    textfont=dict(size=12),
    hovertemplate="<b>%{y}</b> → <b>%{x}</b><br>%{z:.1f}% of sourced<extra></extra>",
    showscale=True,
    colorbar=dict(title=dict(text="% sourced", side="right"), thickness=14),
    zmin=0, zmax=100,
))
fig_heatmap.update_layout(
    **BASE_LAYOUT,
    margin=DEFAULT_MARGIN,
    title=title_style("Conversion Rates by Channel & Stage"),
    xaxis=dict(side="bottom", showgrid=False, automargin=True),
    yaxis=dict(showgrid=False, automargin=True),
)

# ── FIG 5 & 6: recruiter leaderboard ─────────────────────────────────────────

r_src = (
    pipeline[pipeline["stage"] == "Sourced"]
    .groupby("recruiter")["candidate_id"].nunique().rename("sourced")
)
r_pl = (
    pipeline[pipeline["stage"] == "Placed"]
    .groupby("recruiter")["candidate_id"].nunique().rename("placed")
)
sc = pd.concat([r_src, r_pl], axis=1).fillna(0)
sc["placement_rate"] = (sc["placed"] / sc["sourced"].replace(0, np.nan) * 100).round(1)

# time-to-fill per recruiter using date_opened already in placed_df
placed_ttf = placed_df.copy()
placed_ttf["days_to_fill"] = (
    (placed_ttf["stage_date"] - placed_ttf["date_opened"]).dt.days.clip(lower=1)
)
r_ttf = (
    placed_ttf.groupby("recruiter")["days_to_fill"].mean().round(1).rename("avg_ttf")
)
sc = sc.join(r_ttf)

# ── fig 5: grouped bar — placements + placement rate on one chart ─────────────

sc_sorted = sc.sort_values("placed", ascending=True)

fig_rec = go.Figure()
fig_rec.add_trace(go.Bar(
    name="Placements",
    x=sc_sorted["placed"],
    y=sc_sorted.index,
    orientation="h",
    marker_color=colour_scale(sc_sorted["placed"], high_is_good=True),
    hovertemplate="<b>%{y}</b><br>%{x} placements<extra></extra>",
    xaxis="x",
))
fig_rec.add_trace(go.Scatter(
    name="Placement Rate",
    x=sc_sorted["placement_rate"],
    y=sc_sorted.index,
    mode="markers",
    marker=dict(size=13, color=AMBER, symbol="diamond",
                line=dict(width=1.5, color="white")),
    hovertemplate="<b>%{y}</b><br>%{x:.1f}% placement rate<extra></extra>",
    xaxis="x2",
))
fig_rec.update_layout(
    **BASE_LAYOUT,
    title=title_style("Recruiter Performance"),
    margin=dict(l=16, r=16, t=52, b=56),
    xaxis=dict(title="Placements", showgrid=True, gridcolor="#F1F5F9",
               rangemode="tozero", domain=[0, 0.56]),
    xaxis2=dict(title="Placement Rate (%)", overlaying="x", side="top",
                showgrid=False, rangemode="tozero", color=AMBER),
    yaxis=dict(showgrid=False, automargin=True),
    legend=dict(orientation="h", y=-0.20, x=0, font=dict(size=11)),
)

# ── fig 6: avg time-to-fill per recruiter ─────────────────────────────────────

sc_ttf = sc.dropna(subset=["avg_ttf"]).sort_values("avg_ttf", ascending=True)

fig_rec_ttf = go.Figure(go.Bar(
    x=sc_ttf["avg_ttf"],
    y=sc_ttf.index,
    orientation="h",
    marker_color=colour_scale(sc_ttf["avg_ttf"], high_is_good=False),
    hovertemplate="<b>%{y}</b><br>%{x:.0f} avg days to fill<extra></extra>",
))
fig_rec_ttf.update_layout(
    **BASE_LAYOUT,
    margin=DEFAULT_MARGIN,
    title=title_style("Avg Days to Fill by Recruiter"),
    xaxis=dict(title="Avg Days to Fill", showgrid=True,
               gridcolor="#F1F5F9", rangemode="tozero", automargin=True),
    yaxis=dict(showgrid=False, automargin=True),
    showlegend=False,
)

# ── assemble HTML ─────────────────────────────────────────────────────────────

def fig_div(fig, height=370):
    return pio.to_html(
        fig, full_html=False, include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
        default_height=height,
    )


html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{args.title}</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js" charset="utf-8"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: system-ui, -apple-system, sans-serif;
      background: #F8FAFC;
      color: #1E293B;
      min-width: 900px;
    }}

    /* ── header ── */
    header {{
      background: {DARK};
      color: white;
      padding: 24px 40px;
    }}
    header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
    header p  {{ font-size: 13px; opacity: 0.70; }}

    /* ── stat cards ── */
    .stats {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 12px;
      padding: 20px 40px;
      background: white;
      border-bottom: 1px solid {LGREY};
    }}
    .stat {{
      background: #F8FAFC;
      border-radius: 10px;
      padding: 14px 18px;
      border-left: 3px solid {BLUE};
    }}
    .stat .val  {{ font-size: 26px; font-weight: 700; color: {DARK}; line-height: 1.1; }}
    .stat .lbl  {{ font-size: 12px; color: {GREY}; margin-top: 4px; }}

    /* ── content grid ── */
    main {{ padding: 24px 40px 8px; }}

    .section {{
      font-size: 11px; font-weight: 700;
      letter-spacing: .08em; text-transform: uppercase;
      color: {GREY}; margin: 24px 0 10px;
    }}
    .row {{
      display: grid;
      gap: 16px;
      margin-bottom: 16px;
    }}
    .col-2 {{ grid-template-columns: 1fr 1fr; }}
    .col-1 {{ grid-template-columns: 1fr; }}

    .card {{
      background: white;
      border-radius: 10px;
      border: 1px solid {LGREY};
      padding: 6px 10px 2px;
      box-shadow: 0 1px 3px rgba(0,0,0,.04);
      overflow: hidden;
    }}

    footer {{
      text-align: center;
      padding: 20px 40px;
      font-size: 11px;
      color: {GREY};
      border-top: 1px solid {LGREY};
      margin-top: 8px;
    }}
  </style>
</head>
<body>

<header>
  <h1>{args.title}</h1>
  <p>{date_subtitle} &nbsp;&bull;&nbsp; {args.author}</p>
</header>

<div class="stats">
  <div class="stat"><div class="val">{n_sourced:,}</div><div class="lbl">Candidates Sourced</div></div>
  <div class="stat"><div class="val">{n_placed:,}</div><div class="lbl">Total Placements</div></div>
  <div class="stat"><div class="val">{place_rate}%</div><div class="lbl">Placement Rate</div></div>
  <div class="stat"><div class="val">{n_roles}</div><div class="lbl">Roles Worked</div></div>
  <div class="stat"><div class="val">{avg_ttf:.0f}d</div><div class="lbl">Avg Time-to-Fill</div></div>
</div>

<main>
  <div class="section">Funnel &amp; Time-to-Fill</div>
  <div class="row col-2">
    <div class="card">{fig_div(fig_funnel)}</div>
    <div class="card">{fig_div(fig_ttf)}</div>
  </div>

  <div class="section">Sourcing ROI</div>
  <div class="row col-2">
    <div class="card">{fig_div(fig_roi)}</div>
    <div class="card">{fig_div(fig_heatmap)}</div>
  </div>

  <div class="section">Recruiter Performance</div>
  <div class="row col-2">
    <div class="card">{fig_div(fig_rec)}</div>
    <div class="card">{fig_div(fig_rec_ttf)}</div>
  </div>
</main>

<footer>
  {args.title} &bull; Data is synthetic &bull;
  Cost-per-hire figures are illustrative assumptions
</footer>

</body>
</html>"""

OUT_PATH.write_text(html_content, encoding="utf-8")
size_kb = OUT_PATH.stat().st_size // 1024
print(f"Dashboard written: {OUT_PATH.resolve()}  ({size_kb} KB)")
print(f"Open:  file:///{OUT_PATH.resolve()}")
