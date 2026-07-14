-- =============================================================================
-- 01_conversion_rates.sql
-- Funnel conversion rates: overall and broken down by source channel.
-- Channels are normalised (TRIM + UPPER) to account for messy source data.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Overall funnel: candidates at each stage and % of all sourced candidates
-- -----------------------------------------------------------------------------
WITH stage_counts AS (
    SELECT
        stage,
        COUNT(DISTINCT candidate_id) AS n_candidates
    FROM pipeline_stages
    GROUP BY stage
),
sourced_total AS (
    SELECT n_candidates AS total FROM stage_counts WHERE stage = 'Sourced'
)
SELECT
    sc.stage,
    sc.n_candidates,
    ROUND(100.0 * sc.n_candidates / st.total, 1) AS pct_of_sourced
FROM stage_counts sc, sourced_total st
ORDER BY
    CASE sc.stage
        WHEN 'Sourced'     THEN 1
        WHEN 'Screened'    THEN 2
        WHEN 'Interviewed' THEN 3
        WHEN 'Offered'     THEN 4
        WHEN 'Placed'      THEN 5
        WHEN 'Rejected'    THEN 6
    END;


-- -----------------------------------------------------------------------------
-- 2. Stage-to-stage conversion rates (sequential drop-off at each step)
-- -----------------------------------------------------------------------------
WITH stage_counts AS (
    SELECT
        stage,
        COUNT(DISTINCT candidate_id) AS n
    FROM pipeline_stages
    GROUP BY stage
)
SELECT
    curr.stage                                          AS from_stage,
    next_stage.stage                                    AS to_stage,
    curr.n                                              AS from_count,
    next_stage.n                                        AS to_count,
    ROUND(100.0 * next_stage.n / curr.n, 1)            AS step_conversion_pct
FROM stage_counts curr
JOIN stage_counts next_stage ON (
    (curr.stage = 'Sourced'     AND next_stage.stage = 'Screened')    OR
    (curr.stage = 'Screened'    AND next_stage.stage = 'Interviewed')  OR
    (curr.stage = 'Interviewed' AND next_stage.stage = 'Offered')      OR
    (curr.stage = 'Offered'     AND next_stage.stage = 'Placed')
)
ORDER BY
    CASE curr.stage
        WHEN 'Sourced'     THEN 1
        WHEN 'Screened'    THEN 2
        WHEN 'Interviewed' THEN 3
        WHEN 'Offered'     THEN 4
    END;


-- -----------------------------------------------------------------------------
-- 3. Placement rate by source channel (normalised for messy casing/whitespace)
-- -----------------------------------------------------------------------------
WITH normalised AS (
    SELECT
        ps.candidate_id,
        ps.stage,
        TRIM(UPPER(c.source_channel)) AS channel
    FROM pipeline_stages ps
    JOIN candidates c ON ps.candidate_id = c.candidate_id
),
sourced_per_channel AS (
    SELECT channel, COUNT(DISTINCT candidate_id) AS total_sourced
    FROM normalised
    WHERE stage = 'Sourced'
    GROUP BY channel
),
placed_per_channel AS (
    SELECT channel, COUNT(DISTINCT candidate_id) AS total_placed
    FROM normalised
    WHERE stage = 'Placed'
    GROUP BY channel
)
SELECT
    s.channel,
    s.total_sourced,
    COALESCE(p.total_placed, 0)                                AS total_placed,
    ROUND(100.0 * COALESCE(p.total_placed, 0) / s.total_sourced, 1) AS placement_rate_pct
FROM sourced_per_channel s
LEFT JOIN placed_per_channel p ON s.channel = p.channel
ORDER BY placement_rate_pct DESC;


-- -----------------------------------------------------------------------------
-- 4. Conversion rates at every stage, by source channel (heat-map style)
-- -----------------------------------------------------------------------------
WITH normalised AS (
    SELECT
        ps.candidate_id,
        ps.stage,
        TRIM(UPPER(c.source_channel)) AS channel
    FROM pipeline_stages ps
    JOIN candidates c ON ps.candidate_id = c.candidate_id
),
pivot AS (
    SELECT
        channel,
        COUNT(DISTINCT CASE WHEN stage = 'Sourced'     THEN candidate_id END) AS sourced,
        COUNT(DISTINCT CASE WHEN stage = 'Screened'    THEN candidate_id END) AS screened,
        COUNT(DISTINCT CASE WHEN stage = 'Interviewed' THEN candidate_id END) AS interviewed,
        COUNT(DISTINCT CASE WHEN stage = 'Offered'     THEN candidate_id END) AS offered,
        COUNT(DISTINCT CASE WHEN stage = 'Placed'      THEN candidate_id END) AS placed
    FROM normalised
    GROUP BY channel
)
SELECT
    channel,
    sourced,
    ROUND(100.0 * screened    / sourced, 1) AS pct_screened,
    ROUND(100.0 * interviewed / sourced, 1) AS pct_interviewed,
    ROUND(100.0 * offered     / sourced, 1) AS pct_offered,
    ROUND(100.0 * placed      / sourced, 1) AS pct_placed
FROM pivot
ORDER BY pct_placed DESC;
