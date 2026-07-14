-- =============================================================================
-- 02_time_to_fill.sql
-- Time-to-fill analysis: how long roles take from opening to first placement.
-- Uses pipeline_stages date for 'Placed' rather than roles.date_closed, since
-- date_closed also includes cancelled/unfilled roles.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Time-to-fill per role (days from role opened to first placement)
-- -----------------------------------------------------------------------------
SELECT
    r.role_id,
    r.role_title,
    cl.client_name,
    cl.industry,
    r.date_opened,
    MIN(ps.stage_date)                                                     AS date_filled,
    CAST(JULIANDAY(MIN(ps.stage_date)) - JULIANDAY(r.date_opened) AS INTEGER) AS days_to_fill
FROM roles r
JOIN clients cl ON r.client_id = cl.client_id
JOIN pipeline_stages ps ON r.role_id = ps.role_id
WHERE ps.stage = 'Placed'
GROUP BY r.role_id
ORDER BY days_to_fill DESC;


-- -----------------------------------------------------------------------------
-- 2. Average time-to-fill by role title (which job types take longest?)
-- -----------------------------------------------------------------------------
WITH filled_roles AS (
    SELECT
        r.role_id,
        r.role_title,
        CAST(JULIANDAY(MIN(ps.stage_date)) - JULIANDAY(r.date_opened) AS INTEGER) AS days_to_fill
    FROM roles r
    JOIN pipeline_stages ps ON r.role_id = ps.role_id
    WHERE ps.stage = 'Placed'
    GROUP BY r.role_id
)
SELECT
    role_title,
    COUNT(*)                        AS roles_filled,
    ROUND(AVG(days_to_fill), 1)    AS avg_days_to_fill,
    MIN(days_to_fill)              AS min_days,
    MAX(days_to_fill)              AS max_days
FROM filled_roles
GROUP BY role_title
ORDER BY avg_days_to_fill DESC;


-- -----------------------------------------------------------------------------
-- 3. Average time-to-fill by client industry
-- -----------------------------------------------------------------------------
WITH filled_roles AS (
    SELECT
        r.role_id,
        cl.industry,
        CAST(JULIANDAY(MIN(ps.stage_date)) - JULIANDAY(r.date_opened) AS INTEGER) AS days_to_fill
    FROM roles r
    JOIN clients cl ON r.client_id = cl.client_id
    JOIN pipeline_stages ps ON r.role_id = ps.role_id
    WHERE ps.stage = 'Placed'
    GROUP BY r.role_id
)
SELECT
    industry,
    COUNT(*)                        AS roles_filled,
    ROUND(AVG(days_to_fill), 1)    AS avg_days_to_fill,
    MIN(days_to_fill)              AS min_days,
    MAX(days_to_fill)              AS max_days
FROM filled_roles
GROUP BY industry
ORDER BY avg_days_to_fill DESC;


-- -----------------------------------------------------------------------------
-- 4. Monthly trend: average time-to-fill for roles placed each month
-- Useful for spotting seasonal slowdowns or hiring-market changes.
-- -----------------------------------------------------------------------------
WITH placements AS (
    SELECT
        r.role_id,
        MIN(ps.stage_date)                                                     AS placed_date,
        CAST(JULIANDAY(MIN(ps.stage_date)) - JULIANDAY(r.date_opened) AS INTEGER) AS days_to_fill
    FROM roles r
    JOIN pipeline_stages ps ON r.role_id = ps.role_id
    WHERE ps.stage = 'Placed'
    GROUP BY r.role_id
)
SELECT
    STRFTIME('%Y-%m', placed_date)  AS month,
    COUNT(*)                        AS placements,
    ROUND(AVG(days_to_fill), 1)    AS avg_days_to_fill
FROM placements
GROUP BY month
ORDER BY month;


-- -----------------------------------------------------------------------------
-- 5. Roles still open (no placement yet) — flag for pipeline risk
-- -----------------------------------------------------------------------------
SELECT
    r.role_id,
    r.role_title,
    cl.client_name,
    cl.industry,
    r.date_opened,
    CAST(JULIANDAY('2025-06-30') - JULIANDAY(r.date_opened) AS INTEGER) AS days_open_so_far
FROM roles r
JOIN clients cl ON r.client_id = cl.client_id
WHERE r.role_id NOT IN (
    SELECT DISTINCT role_id FROM pipeline_stages WHERE stage = 'Placed'
)
AND r.date_closed IS NULL
ORDER BY days_open_so_far DESC;
