-- =============================================================================
-- 04_recruiter_performance.sql
-- Recruiter performance: placements, conversion rate, and average time-to-fill.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Overall recruiter scorecard
-- -----------------------------------------------------------------------------
WITH recruiter_pipeline AS (
    SELECT
        recruiter,
        candidate_id,
        MAX(CASE WHEN stage = 'Placed'  THEN 1 ELSE 0 END) AS was_placed,
        MAX(CASE WHEN stage = 'Sourced' THEN 1 ELSE 0 END) AS was_sourced
    FROM pipeline_stages
    GROUP BY recruiter, candidate_id
),
scorecard AS (
    SELECT
        recruiter,
        SUM(was_sourced)                                    AS total_sourced,
        SUM(was_placed)                                     AS total_placed,
        ROUND(100.0 * SUM(was_placed) / SUM(was_sourced), 1) AS placement_rate_pct
    FROM recruiter_pipeline
    GROUP BY recruiter
),
-- Average time-to-fill per recruiter (days from role opened to placed stage)
recruiter_ttf AS (
    SELECT
        ps_placed.recruiter,
        AVG(
            JULIANDAY(ps_placed.stage_date) - JULIANDAY(r.date_opened)
        )                                                   AS avg_days_to_fill
    FROM pipeline_stages ps_placed
    JOIN roles r ON ps_placed.role_id = r.role_id
    WHERE ps_placed.stage = 'Placed'
    GROUP BY ps_placed.recruiter
)
SELECT
    s.recruiter,
    s.total_sourced,
    s.total_placed,
    s.placement_rate_pct,
    ROUND(t.avg_days_to_fill, 1)    AS avg_days_to_fill
FROM scorecard s
LEFT JOIN recruiter_ttf t ON s.recruiter = t.recruiter
ORDER BY total_placed DESC;


-- -----------------------------------------------------------------------------
-- 2. Recruiter performance by source channel
-- Which channels does each recruiter use most, and how effectively?
-- -----------------------------------------------------------------------------
WITH normalised AS (
    SELECT
        ps.candidate_id,
        ps.recruiter,
        ps.stage,
        TRIM(UPPER(c.source_channel)) AS channel
    FROM pipeline_stages ps
    JOIN candidates c ON ps.candidate_id = c.candidate_id
),
pivot AS (
    SELECT
        recruiter,
        channel,
        COUNT(DISTINCT CASE WHEN stage = 'Sourced' THEN candidate_id END) AS sourced,
        COUNT(DISTINCT CASE WHEN stage = 'Placed'  THEN candidate_id END) AS placed
    FROM normalised
    GROUP BY recruiter, channel
)
SELECT
    recruiter,
    channel,
    sourced,
    placed,
    ROUND(100.0 * placed / NULLIF(sourced, 0), 1) AS placement_rate_pct
FROM pivot
ORDER BY recruiter, placement_rate_pct DESC;


-- -----------------------------------------------------------------------------
-- 3. Recruiter monthly activity — placements per month (trend over 18 months)
-- -----------------------------------------------------------------------------
SELECT
    recruiter,
    STRFTIME('%Y-%m', stage_date) AS month,
    COUNT(DISTINCT candidate_id)  AS placements
FROM pipeline_stages
WHERE stage = 'Placed'
GROUP BY recruiter, month
ORDER BY recruiter, month;


-- -----------------------------------------------------------------------------
-- 4. Recruiter performance by industry — who are the sector specialists?
-- -----------------------------------------------------------------------------
WITH placements AS (
    SELECT
        ps.recruiter,
        ps.candidate_id,
        cl.industry
    FROM pipeline_stages ps
    JOIN roles r ON ps.role_id = r.role_id
    JOIN clients cl ON r.client_id = cl.client_id
    WHERE ps.stage = 'Placed'
)
SELECT
    recruiter,
    industry,
    COUNT(DISTINCT candidate_id) AS placements
FROM placements
GROUP BY recruiter, industry
ORDER BY recruiter, placements DESC;
