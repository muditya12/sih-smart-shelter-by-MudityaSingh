"""SIH26051 - SQLite storage for analyzed designs."""
import json, os, sqlite3, uuid
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shelter.db")


def _conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS designs(
        id TEXT PRIMARY KEY, created_at TEXT, inputs TEXT,
        results TEXT, score REAL)""")
    return c


def save_design(inputs, results, score):
    did = uuid.uuid4().hex[:8]
    with _conn() as c:
        c.execute("INSERT INTO designs VALUES (?,?,?,?,?)",
                  (did, datetime.now().isoformat(timespec="seconds"),
                   json.dumps(inputs), json.dumps(results), float(score)))
    return did


def list_designs(limit=50):
    with _conn() as c:
        rows = c.execute(
            "SELECT id, created_at, inputs, results, score FROM designs "
            "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for i, ts, ins, res, sc in rows:
        ins, res = json.loads(ins), json.loads(res)
        out.append({"id": i, "created_at": ts, "score": sc,
                    "t_after": res["t_after"], "cost": res["cost"],
                    "wall": ins.get("wall_name", ""), "roof": ins.get("roof_name", ""),
                    "inputs": ins, "results": res})
    return out


def get_design(did):
    with _conn() as c:
        r = c.execute("SELECT inputs FROM designs WHERE id=?", (did,)).fetchone()
    return json.loads(r[0]) if r else None