-- Recruitment Funnel & Sourcing ROI Analytics
-- Schema for SQLite database

DROP TABLE IF EXISTS pipeline_stages;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS clients;
DROP TABLE IF EXISTS candidates;

CREATE TABLE clients (
    client_id INTEGER PRIMARY KEY,
    client_name TEXT NOT NULL,
    industry TEXT NOT NULL
);

CREATE TABLE roles (
    role_id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL,
    role_title TEXT NOT NULL,
    salary_band_min INTEGER NOT NULL,
    salary_band_max INTEGER NOT NULL,
    date_opened DATE NOT NULL,
    date_closed DATE,
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

CREATE TABLE candidates (
    candidate_id INTEGER PRIMARY KEY,
    source_channel TEXT NOT NULL,
    role_applied TEXT,
    years_experience INTEGER,
    expected_salary INTEGER,
    date_sourced DATE NOT NULL
);

CREATE TABLE pipeline_stages (
    stage_id INTEGER PRIMARY KEY,
    candidate_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    recruiter TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN ('Sourced', 'Screened', 'Interviewed', 'Offered', 'Placed', 'Rejected')),
    stage_date DATE NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id),
    FOREIGN KEY (role_id) REFERENCES roles(role_id)
);

CREATE INDEX idx_pipeline_candidate ON pipeline_stages(candidate_id);
CREATE INDEX idx_pipeline_role ON pipeline_stages(role_id);
CREATE INDEX idx_pipeline_stage ON pipeline_stages(stage);
