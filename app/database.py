import json
import os
from datetime import datetime, date, timedelta

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text,
    select, insert, update, func,
)

DEFAULT_SECTIONS = [
    "ආයතන අංශය",
    "ඉඩම් අංශය",
    "පුද්ගලයින් ලියාපදංචි කිරීමේ අංශය ( හැදුනුම්පත්)",
    "රෙජිස්ටාර් අංශය",
    "විශ්‍රාම වැටුප් අංශය",
    "සමාජසේවා අංශය",
    "බෞද්ධ කටයුතු අංශය",
    "ළමා හා කාන්තා කටයුතු අංශය",
    "ක්‍රමසම්පදාන අංශය",
    "වෙනත් කේෂ්ත්‍ර කටයුතු",
]

# ---------------------------------------------------------------------------
# Database connection
#
# If a DATABASE_URL environment variable is set (e.g. a free Neon.tech or
# Supabase Postgres connection string), that is used — this is what keeps
# data safe on free hosting tiers like Render, where the app's own disk gets
# wiped on redeploy/restart.
#
# If DATABASE_URL is NOT set, we fall back to a local SQLite file, which is
# perfect for running/testing on your own computer.
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Render/Neon/Supabase sometimes give "postgres://" — SQLAlchemy needs "postgresql+psycopg2://"
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "data", "office.db")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

metadata = MetaData()
clients_table = Table(
    "clients", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("token", String(20), nullable=False),
    Column("name", String(200), nullable=False),
    Column("phone", String(50)),
    Column("nic", String(50)),
    Column("gender", String(20)),
    Column("address", Text),
    Column("purpose", Text, nullable=False),
    Column("remarks", Text),
    Column("sections", Text, nullable=False),         # JSON list of required section names
    Column("section_status", Text, nullable=False),   # JSON dict section -> pending/in_progress/done
    Column("overall_status", String(20), nullable=False, default="waiting"),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    Column("completed_at", String(40)),
)

history_table = Table(
    "client_history", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("client_id", Integer, nullable=False),
    Column("note", Text, nullable=False),
    Column("created_at", String(40), nullable=False),
)

feedback_table = Table(
    "feedback", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(200)),                # optional
    Column("section", String(50), nullable=False),
    Column("reason", Text, nullable=False),
    Column("rating", String(20), nullable=False),  # good / average / poor
    Column("created_at", String(40), nullable=False),
)

config_table = Table(
    "config", metadata,
    Column("key", String(50), primary_key=True),
    Column("value", Text, nullable=False),
)


def init_db():
    metadata.create_all(engine)
    with engine.begin() as conn:
        row = conn.execute(select(config_table).where(config_table.c.key == "sections")).fetchone()
        if not row:
            conn.execute(insert(config_table).values(key="sections", value=json.dumps(DEFAULT_SECTIONS)))

def get_sections():
    with engine.connect() as conn:
        row = conn.execute(select(config_table).where(config_table.c.key == "sections")).fetchone()
        if row:
            return json.loads(row.value)
    return DEFAULT_SECTIONS

def save_sections(sections_list):
    with engine.begin() as conn:
        row = conn.execute(select(config_table).where(config_table.c.key == "sections")).fetchone()
        if row:
            conn.execute(update(config_table).where(config_table.c.key == "sections").values(value=json.dumps(sections_list)))
        else:
            conn.execute(insert(config_table).values(key="sections", value=json.dumps(sections_list)))


class _SectionsProxy(list):
    """Live proxy so callers can use db.SECTIONS and always get the
    current value from the database without restarting the server."""
    def _refresh(self):
        data = get_sections()
        list.__init__(self, data)
    def __iter__(self):
        self._refresh(); return super().__iter__()
    def __len__(self):
        self._refresh(); return super().__len__()
    def __getitem__(self, idx):
        self._refresh(); return super().__getitem__(idx)
    def __contains__(self, item):
        self._refresh(); return super().__contains__(item)


SECTIONS: list = _SectionsProxy()

def log_event(client_id, note):
    now = datetime.now().isoformat()
    with engine.begin() as conn:
        conn.execute(
            insert(history_table).values(client_id=client_id, note=note, created_at=now)
        )


def get_history(client_id):
    with engine.connect() as conn:
        rows = conn.execute(
            select(history_table)
            .where(history_table.c.client_id == client_id)
            .order_by(history_table.c.created_at)
        ).fetchall()
    return [{"note": r.note, "at": r.created_at} for r in rows]


def get_history_map(client_ids):
    if not client_ids:
        return {}
    with engine.connect() as conn:
        rows = conn.execute(
            select(history_table)
            .where(history_table.c.client_id.in_(client_ids))
            .order_by(history_table.c.created_at)
        ).fetchall()
    result = {}
    for r in rows:
        result.setdefault(r.client_id, []).append({"note": r.note, "at": r.created_at})
    return result


def next_token():
    """Daily-reset token like T-001, T-002 ..."""
    today_prefix = date.today().isoformat()
    with engine.connect() as conn:
        count = conn.execute(
            select(func.count()).select_from(clients_table)
            .where(clients_table.c.created_at.like(f"{today_prefix}%"))
        ).scalar()
    return f"T-{(count or 0) + 1:03d}"


def create_client(name, phone, purpose, sections, nic="", gender="", address="", remarks=""):
    now = datetime.now().isoformat()
    token = next_token()
    status = {s: "pending" for s in sections}
    with engine.begin() as conn:
        result = conn.execute(
            insert(clients_table).values(
                token=token, name=name, phone=phone, nic=nic, gender=gender,
                address=address, purpose=purpose, remarks=remarks,
                sections=json.dumps(sections), section_status=json.dumps(status),
                overall_status="waiting", created_at=now, updated_at=now,
            )
        )
        new_id = result.inserted_primary_key[0]
    log_event(new_id, f"Registered — needs: {', '.join(sections)}")
    return new_id, token


def row_to_dict(row):
    d = dict(row._mapping)
    d["sections"] = json.loads(d["sections"])
    d["section_status"] = json.loads(d["section_status"])
    total = len(d["sections"])
    done = sum(1 for v in d["section_status"].values() if v == "done")
    d["progress"] = round((done / total) * 100) if total else 0
    d["done_count"] = done
    d["total_count"] = total
    return d


def get_all_clients(active_only=False, section=None):
    with engine.connect() as conn:
        q = select(clients_table)
        if active_only:
            q = q.where(clients_table.c.overall_status != "completed")
        q = q.order_by(clients_table.c.created_at.desc())
        rows = conn.execute(q).fetchall()
    clients = [row_to_dict(r) for r in rows]
    if section:
        clients = [c for c in clients if section in c["sections"]]
    history_map = get_history_map([c["id"] for c in clients])
    for c in clients:
        c["history"] = history_map.get(c["id"], [])
    return clients


def get_client(client_id):
    with engine.connect() as conn:
        row = conn.execute(
            select(clients_table).where(clients_table.c.id == client_id)
        ).fetchone()
    if not row:
        return None
    client = row_to_dict(row)
    client["history"] = get_history(client_id)
    return client


def update_section_status(client_id, section, status):
    client = get_client(client_id)
    if not client or section not in client["section_status"]:
        return None
    client["section_status"][section] = status
    all_done = all(v == "done" for v in client["section_status"].values())
    any_active = any(v in ("in_progress", "done") for v in client["section_status"].values())
    overall = "completed" if all_done else ("in_progress" if any_active else "waiting")
    now = datetime.now().isoformat()
    with engine.begin() as conn:
        conn.execute(
            update(clients_table).where(clients_table.c.id == client_id).values(
                section_status=json.dumps(client["section_status"]),
                overall_status=overall,
                updated_at=now,
                completed_at=now if overall == "completed" else None,
            )
        )
    label = {"pending": "reopened (Pending)", "in_progress": "In Progress", "done": "Done"}[status]
    log_event(client_id, f"{section}: {label}")
    if overall == "completed":
        log_event(client_id, "✅ All sections done — client completed")
    return get_client(client_id)


def get_stats():
    clients = get_all_clients(active_only=False)
    total = len(clients)
    waiting = sum(1 for c in clients if c["overall_status"] == "waiting")
    in_progress = sum(1 for c in clients if c["overall_status"] == "in_progress")
    completed = sum(1 for c in clients if c["overall_status"] == "completed")

    today_prefix = date.today().isoformat()
    today_count = sum(1 for c in clients if c["created_at"].startswith(today_prefix))
    today_completed = sum(
        1 for c in clients
        if c["overall_status"] == "completed" and (c["completed_at"] or "").startswith(today_prefix)
    )

    current_sections = get_sections()
    section_needed = {s: 0 for s in current_sections}
    section_pending = {s: 0 for s in current_sections}
    section_in_progress = {s: 0 for s in current_sections}
    section_done = {s: 0 for s in current_sections}
    for c in clients:
        for s in c["sections"]:
            if s not in current_sections:
                continue
            section_needed[s] += 1
            st = c["section_status"][s]
            if st == "pending":
                section_pending[s] += 1
            elif st == "in_progress":
                section_in_progress[s] += 1
            elif st == "done":
                section_done[s] += 1

    return {
        "total": total,
        "waiting": waiting,
        "in_progress": in_progress,
        "completed": completed,
        "today_count": today_count,
        "today_completed": today_completed,
        "sections": current_sections,
        "section_needed": section_needed,
        "section_pending": section_pending,
        "section_in_progress": section_in_progress,
        "section_done": section_done,
    }


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
def create_feedback(section, reason, rating, name=""):
    now = datetime.now().isoformat()
    with engine.begin() as conn:
        conn.execute(
            insert(feedback_table).values(
                name=name, section=section, reason=reason, rating=rating, created_at=now,
            )
        )


def get_all_feedback():
    with engine.connect() as conn:
        rows = conn.execute(
            select(feedback_table).order_by(feedback_table.c.created_at.desc())
        ).fetchall()
    return [dict(r._mapping) for r in rows]


def get_feedback_stats():
    items = get_all_feedback()
    total = len(items)
    good = sum(1 for f in items if f["rating"] == "good")
    average = sum(1 for f in items if f["rating"] == "average")
    poor = sum(1 for f in items if f["rating"] == "poor")
    current_sections = get_sections()
    by_section = {s: {"good": 0, "average": 0, "poor": 0} for s in current_sections}
    for f in items:
        if f["section"] in by_section:
            by_section[f["section"]][f["rating"]] += 1

    # Weighted average rating out of 5 (good=5, average=3, poor=1)
    weight = {"good": 5, "average": 3, "poor": 1}
    avg_rating = round(sum(weight[f["rating"]] for f in items) / total, 1) if total else 0

    # Daily submission counts for the last 14 days (zero-filled for empty days)
    today = date.today()
    daily = {}
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        daily[d.isoformat()] = 0
    for f in items:
        d = f["created_at"][:10]
        if d in daily:
            daily[d] += 1
    daily_counts = [{"date": k, "count": v} for k, v in daily.items()]

    return {
        "total": total, "good": good, "average": average, "poor": poor,
        "by_section": by_section, "avg_rating": avg_rating, "daily_counts": daily_counts,
    }
