-- =============================================================================
-- 03_sourcing_roi.sql
-- Sourcing ROI: cost-per-hire proxy by channel.
--
-- ASSUMPTION (illustrative figures — replace with real data if available):
--   LinkedIn        £45 per candidate sourced
--   Referral        £10 per candidate sourced
--   Job Board       £60 per candidate sourced
--   Agency Database £15 per candidate sourced
--   Cold Outreach   £25 per candidate sourced
--
-- Cost-per-hire = (n_sourced × cost_per_sourced) / n_placed
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Core ROI table: spend, placements, and cost-per-hire by channel
-- -----------------------------------------------------------------------------
WITH channel_costs(channel, cost_per_sourced) AS (
    -- ASSUMPTION: nominal cost per candidate sourced per channel (£)
    VALUES
        ('LINKEDIN',         45),
        ('REFERRAL',         10),
        ('JOB BOARD',        60),
        ('AGENCY DATABASE',  15),
        ('COLD OUTREACH',    25)
),
normalised AS (
    SELECT
        ps.candidate_id,
        ps.stage,
        TRIM(UPPER(c.source_channel)) AS channel
    FROM pipeline_stages ps
    JOIN candidates c ON ps.candidate_id = c.candidate_id
),
channel_stats AS (
    SELECT
        channel,
        COUNT(DISTINCT CASE WHEN stage = 'Sourced' THEN candidate_id END) AS n_sourced,
        COUNT(DISTINCT CASE WHEN stage = 'Placed'  THEN candidate_id END) AS n_placed
    FROM normalised
    GROUP BY channel
)
SELECT
    cs.channel,
    cs.n_sourced,
    cs.n_placed,
    ROUND(100.0 * cs.n_placed / cs.n_sourced, 1)                              AS placement_rate_pct,
    cc.cost_per_sourced                                                        AS cost_per_sourced_gbp,
    cs.n_sourced * cc.cost_per_sourced                                         AS total_spend_gbp,
    CASE WHEN cs.n_placed = 0 THEN NULL
         ELSE ROUND(1.0 * cs.n_sourced * cc.cost_per_sourced / cs.n_placed, 0)
    END                                                                        AS cost_per_hire_gbp
FROM channel_stats cs
JOIN channel_costs cc ON cs.channel = cc.channel
ORDER BY cost_per_hire_gbp ASC;


-- -----------------------------------------------------------------------------
-- 2. ROI ranking: channels ranked by cost-per-hire (lower = better)
-- Adds a rank column for easy comparison.
-- -----------------------------------------------------------------------------
WITH channel_costs(channel, cost_per_sourced) AS (
    VALUES
        ('LINKEDIN',         45),
        ('REFERRAL',         10),
        ('JOB BOARD',        60),
        ('AGENCY DATABASE',  15),
        ('COLD OUTREACH',    25)
),
normalised AS (
    SELECT
        ps.candidate_id,
        ps.stage,
        TRIM(UPPER(c.source_channel)) AS channel
    FROM pipeline_stages ps
    JOIN candidates c ON ps.candidate_id = c.candidate_id
),
channel_stats AS (
    SELECT
        channel,
        COUNT(DISTINCT CASE WHEN stage = 'Sourced' THEN candidate_id END) AS n_sourced,
        COUNT(DISTINCT CASE WHEN stage = 'Placed'  THEN candidate_id END) AS n_placed
    FROM normalised
    GROUP BY channel
),
roi AS (
    SELECT
        cs.channel,
        cs.n_sourced,
        cs.n_placed,
        cc.cost_per_sourced * cs.n_sourced                                      AS total_spend_gbp,
        CASE WHEN cs.n_placed = 0 THEN NULL
             ELSE ROUND(1.0 * cc.cost_per_sourced * cs.n_sourced / cs.n_placed, 0)
        END                                                                     AS cost_per_hire_gbp
    FROM channel_stats cs
    JOIN channel_costs cc ON cs.channel = cc.channel
)
SELECT
    ROW_NUMBER() OVER (ORDER BY cost_per_hire_gbp ASC) AS roi_rank,
    channel,
    n_sourced,
    n_placed,
    total_spend_gbp,
    cost_per_hire_gbp
FROM roi
ORDER BY roi_rank;


-- -----------------------------------------------------------------------------
-- 3. Channel ROI by industry — does channel effectiveness vary by sector?
-- -----------------------------------------------------------------------------
WITH channel_costs(channel, cost_per_sourced) AS (
    VALUES
        ('LINKEDIN',         45),
        ('REFERRAL',         10),
        ('JOB BOARD',        60),
        ('AGENCY DATABASE',  15),
        ('COLD OUTREACH',    25)
),
normalised AS (
    SELECT
        ps.candidate_id,
        ps.stage,
        ps.role_id,
        TRIM(UPPER(c.source_channel)) AS channel
    FROM pipeline_stages ps
    JOIN candidates c ON ps.candidate_id = c.candidate_id
),
with_industry AS (
    SELECT
        n.candidate_id,
        n.stage,
        n.channel,
        cl.industry
    FROM normalised n
    JOIN roles r ON n.role_id = r.role_id
    JOIN clients cl ON r.client_id = cl.client_id
),
stats AS (
    SELECT
        industry,
        channel,
        COUNT(DISTINCT CASE WHEN stage = 'Sourced' THEN candidate_id END) AS n_sourced,
        COUNT(DISTINCT CASE WHEN stage = 'Placed'  THEN candidate_id END) AS n_placed
    FROM with_industry
    GROUP BY industry, channel
)
SELECT
    s.industry,
    s.channel,
    s.n_sourced,
    s.n_placed,
    ROUND(100.0 * s.n_placed / NULLIF(s.n_sourced, 0), 1) AS placement_rate_pct,
    ROUND(1.0 * cc.cost_per_sourced * s.n_sourced / NULLIF(s.n_placed, 0), 0) AS cost_per_hire_gbp
FROM stats s
JOIN channel_costs cc ON s.channel = cc.channel
ORDER BY s.industry, cost_per_hire_gbp ASC;
