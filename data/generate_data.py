"""
generate_data.py

Generates a realistic (and realistically messy) synthetic dataset simulating
an 18-month recruitment agency pipeline, and loads it into a SQLite database.

Run:
    python generate_data.py

Produces:
    ../database/recruitment.db
"""

import sqlite3
import random
from datetime import date, timedelta
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

N_CANDIDATES = 1000
N_CLIENTS = 18
N_ROLES = 50
RECRUITERS = ["Sarah Kelly", "Marcus Chen", "Priya Nair", "Dave O'Sullivan"]

# NOTE: assumed illustrative figures — swap in real numbers if you have them.
SOURCE_CHANNELS = ["LinkedIn", "Referral", "Job Board", "Agency Database", "Cold Outreach"]
# Nominal cost-per-sourced-candidate by channel (ASSUMPTION — placeholder for real data)
CHANNEL_COST = {
    "LinkedIn": 45,
    "Referral": 10,
    "Job Board": 60,
    "Agency Database": 15,
    "Cold Outreach": 25,
}

INDUSTRIES = ["Finance", "Healthcare", "Technology", "Retail", "Manufacturing", "Legal"]

ROLE_TITLES = [
    "Data Analyst", "Financial Analyst", "Software Engineer", "Operations Manager",
    "Marketing Coordinator", "Sales Executive", "HR Business Partner", "Project Manager",
    "Business Analyst", "Customer Success Manager", "Accountant", "Supply Chain Analyst",
]

START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 6, 30)  # 18 months
TOTAL_DAYS = (END_DATE - START_DATE).days

# Funnel drop-off probabilities (probability of ADVANCING to next stage)
P_SOURCED_TO_SCREENED = 0.60
P_SCREENED_TO_INTERVIEWED = 0.50
P_INTERVIEWED_TO_OFFERED = 0.40
P_OFFERED_TO_PLACED = 0.85

STAGE_GAP_DAYS = {
    "Screened": (2, 7),
    "Interviewed": (3, 10),
    "Offered": (5, 14),
    "Placed": (2, 7),
    "Rejected": (1, 5),
}


def random_date(start, end):
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


# ----------------------------------------------------------------------
# Clients
# ----------------------------------------------------------------------

def generate_clients(conn):
    clients = []
    for i in range(1, N_CLIENTS + 1):
        clients.append((i, fake.company(), random.choice(INDUSTRIES)))
    conn.executemany("INSERT INTO clients VALUES (?, ?, ?)", clients)
    return clients


# ----------------------------------------------------------------------
# Roles
# ----------------------------------------------------------------------

def generate_roles(conn, clients):
    roles = []
    for role_id in range(1, N_ROLES + 1):
        client_id = random.choice(clients)[0]
        title = random.choice(ROLE_TITLES)
        salary_min = random.randint(45, 90) * 1000
        salary_max = salary_min + random.randint(10, 30) * 1000
        date_opened = random_date(START_DATE, END_DATE - timedelta(days=30))
        # ~80% of roles eventually close (filled or cancelled); rest still open
        if random.random() < 0.80:
            close_offset = random.randint(20, 120)
            date_closed = date_opened + timedelta(days=close_offset)
            if date_closed > END_DATE:
                date_closed = None
        else:
            date_closed = None
        roles.append((role_id, client_id, title, salary_min, salary_max,
                       date_opened.isoformat(), date_closed.isoformat() if date_closed else None))
    conn.executemany("INSERT INTO roles VALUES (?, ?, ?, ?, ?, ?, ?)", roles)
    return roles


# ----------------------------------------------------------------------
# Candidates + pipeline
# ----------------------------------------------------------------------

def messy_channel(channel):
    """Introduce inconsistent casing/whitespace ~8% of the time."""
    r = random.random()
    if r < 0.04:
        return channel.lower()
    elif r < 0.08:
        return channel.upper()
    elif r < 0.10:
        return f" {channel} "
    return channel


def generate_candidates_and_pipeline(conn, roles):
    candidates = []
    pipeline = []
    stage_id = 1

    for candidate_id in range(1, N_CANDIDATES + 1):
        channel = random.choice(SOURCE_CHANNELS)
        channel_stored = messy_channel(channel)

        years_exp = random.randint(0, 15)
        # ~5% missing years_experience
        if random.random() < 0.05:
            years_exp = None

        expected_salary = random.randint(40, 110) * 1000
        # ~4% missing expected_salary
        if random.random() < 0.04:
            expected_salary = None

        date_sourced = random_date(START_DATE, END_DATE - timedelta(days=10))

        # Only assign roles that were open at the time of sourcing so that
        # time-to-fill (placed_date - date_opened) is always non-negative.
        open_roles = [
            r for r in roles
            if r[5] <= date_sourced.isoformat()
            and (r[6] is None or r[6] >= date_sourced.isoformat())
        ]
        role = random.choice(open_roles if open_roles else roles)
        role_id, client_id, role_title = role[0], role[1], role[2]

        candidates.append((
            candidate_id, channel_stored, role_title, years_exp,
            expected_salary, date_sourced.isoformat()
        ))

        # --- pipeline progression ---
        recruiter = random.choice(RECRUITERS)
        current_date = date_sourced
        pipeline.append((stage_id, candidate_id, role_id, recruiter, "Sourced",
                          current_date.isoformat()))
        stage_id += 1

        # Sourced -> Screened
        if random.random() < P_SOURCED_TO_SCREENED:
            gap = random.randint(*STAGE_GAP_DAYS["Screened"])
            current_date = current_date + timedelta(days=gap)
            pipeline.append((stage_id, candidate_id, role_id, recruiter, "Screened",
                              current_date.isoformat()))
            stage_id += 1

            # Screened -> Interviewed
            if random.random() < P_SCREENED_TO_INTERVIEWED:
                gap = random.randint(*STAGE_GAP_DAYS["Interviewed"])
                current_date = current_date + timedelta(days=gap)
                pipeline.append((stage_id, candidate_id, role_id, recruiter, "Interviewed",
                                  current_date.isoformat()))
                stage_id += 1

                # Interviewed -> Offered
                if random.random() < P_INTERVIEWED_TO_OFFERED:
                    gap = random.randint(*STAGE_GAP_DAYS["Offered"])
                    current_date = current_date + timedelta(days=gap)
                    pipeline.append((stage_id, candidate_id, role_id, recruiter, "Offered",
                                      current_date.isoformat()))
                    stage_id += 1

                    # Offered -> Placed or Rejected
                    gap = random.randint(*STAGE_GAP_DAYS["Placed"])
                    current_date = current_date + timedelta(days=gap)
                    if random.random() < P_OFFERED_TO_PLACED:
                        pipeline.append((stage_id, candidate_id, role_id, recruiter, "Placed",
                                          current_date.isoformat()))
                    else:
                        pipeline.append((stage_id, candidate_id, role_id, recruiter, "Rejected",
                                          current_date.isoformat()))
                    stage_id += 1
                else:
                    gap = random.randint(*STAGE_GAP_DAYS["Rejected"])
                    current_date = current_date + timedelta(days=gap)
                    pipeline.append((stage_id, candidate_id, role_id, recruiter, "Rejected",
                                      current_date.isoformat()))
                    stage_id += 1
            else:
                gap = random.randint(*STAGE_GAP_DAYS["Rejected"])
                current_date = current_date + timedelta(days=gap)
                pipeline.append((stage_id, candidate_id, role_id, recruiter, "Rejected",
                                  current_date.isoformat()))
                stage_id += 1
        else:
            gap = random.randint(*STAGE_GAP_DAYS["Rejected"])
            current_date = current_date + timedelta(days=gap)
            pipeline.append((stage_id, candidate_id, role_id, recruiter, "Rejected",
                              current_date.isoformat()))
            stage_id += 1

    conn.executemany(
        "INSERT INTO candidates VALUES (?, ?, ?, ?, ?, ?)", candidates
    )
    conn.executemany(
        "INSERT INTO pipeline_stages VALUES (?, ?, ?, ?, ?, ?)", pipeline
    )
    return candidates, pipeline


def inject_duplicates(conn):
    """Duplicate ~1.5% of candidates (as a new row with a new id) to simulate
    real-world duplicate entry — a common data cleaning exercise."""
    cur = conn.cursor()
    cur.execute("SELECT MAX(candidate_id) FROM candidates")
    max_id = cur.fetchone()[0]

    cur.execute("SELECT * FROM candidates")
    rows = cur.fetchall()
    n_dupes = int(len(rows) * 0.015)
    dupes_to_make = random.sample(rows, n_dupes)

    new_id = max_id + 1
    for row in dupes_to_make:
        new_row = (new_id,) + row[1:]
        cur.execute("INSERT INTO candidates VALUES (?, ?, ?, ?, ?, ?)", new_row)
        new_id += 1
    conn.commit()


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    import os
    db_path = os.path.join(os.path.dirname(__file__), "..", "database", "recruitment.db")
    schema_path = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")

    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    with open(schema_path) as f:
        conn.executescript(f.read())

    clients = generate_clients(conn)
    roles = generate_roles(conn, clients)
    generate_candidates_and_pipeline(conn, roles)
    inject_duplicates(conn)

    conn.commit()

    # Quick sanity check
    cur = conn.cursor()
    for table in ["clients", "roles", "candidates", "pipeline_stages"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table}: {cur.fetchone()[0]} rows")

    conn.close()
    print(f"\nDatabase written to {os.path.abspath(db_path)}")


if __name__ == "__main__":
    main()
