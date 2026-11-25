"""Test for hosting that wipes the disk (Render free plan): accounts must survive a restart with an EMPTY database.

1. Server A (empty database, backup ON, sample office seed ON): sign up a new office, check the seeded office and
   the family status check.
2. Server B (a NEW empty database, same settings): everything must come back from the n8n backup.
Uses the real n8n (no AI calls). At the end it deletes every row it wrote to the backend_store table, so only use it
while no hosted copy is using that table, or point N8N_STORE_URL at a test table.
Run:  backend\\.venv\\Scripts\\python.exe tests\\render_test.py
"""
import os, re, subprocess, sys, tempfile, time
from pathlib import Path
import httpx

PROJECT = Path(__file__).resolve().parents[1]
ENV = dict(l.split("=", 1) for l in (PROJECT / "backend/.env").read_text().splitlines() if "=" in l and not l.startswith("#"))
STORE = ENV["N8N_OVERVIEW_URL"].strip().rsplit("/", 1)[0] + "/backend-store"
KEY = {"X-Pension-Key": ENV["N8N_SHARED_SECRET"].strip()}
logins = (PROJECT / "demo_logins.md").read_text(encoding="utf-8") if (PROJECT / "demo_logins.md").exists() else ""
SAMPLE_KEY = (re.search(r"SEED_WORKSPACE_KEY[^`]*`(w\d{9})`", logins) or [None, ""])[1]
stamp = str(int(time.time()))
SEED = {"email": f"seed.{stamp}@example.com", "password": "Seed-Test-Pass-2026"}
NEW = {"email": f"render.{stamp}@example.com", "password": "Render-Test-2026!", "display_name": "Render Tester", "role": "office"}
PY = str(PROJECT / "backend/.venv/Scripts/python.exe")
results = []

def check(name, ok, extra=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""), flush=True)

def start(port, db_file):
    env = dict(os.environ, PH_DB_PATH=str(db_file), N8N_STORE_URL=STORE, SEED_OFFICE_EMAIL=SEED["email"],
               SEED_OFFICE_PASSWORD=SEED["password"], SEED_WORKSPACE_KEY=SAMPLE_KEY, PYTHONUNBUFFERED="1")
    log = open(db_file.with_suffix(".log"), "w", encoding="utf-8")
    p = subprocess.Popen([PY, "-m", "uvicorn", "app:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", str(port)],
                         cwd=PROJECT, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=2).status_code == 200: return p
        except Exception: time.sleep(0.5)
    raise SystemExit("server did not start")

def stop(p):
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)

tmp = Path(tempfile.mkdtemp())
try:
    # ---------------- server A ----------------
    a = start(8095, tmp / "a.db"); B = "http://127.0.0.1:8095"
    check("health check answers", httpx.get(B + "/healthz").json() == {"ok": True})
    log_a = (tmp / "a.log").read_text(encoding="utf-8")
    check("startup log mentions the sample office", "sample office" in log_a, log_a.strip().splitlines()[-1][:150] if log_a.strip() else "")
    c = httpx.Client(base_url=B, timeout=120)
    check("new office signs up", c.post("/api/signup", json=NEW).status_code == 200)
    c.post("/api/onboarding/details", json={"office_name": "Render Test Office", "district": "Pune", "contact_name": "Tester"})
    check("new office gives consent (step 3)", c.post("/api/onboarding/consent", json={"consent": True}).json().get("step") == 3)
    s = httpx.Client(base_url=B, timeout=120)
    check("seeded sample office can log in", s.post("/api/login", json=SEED).status_code == 200)
    if SAMPLE_KEY:
        d = s.get("/api/overview").json()
        check("seeded office sees the sample pensioners", len(d.get("pensioners", [])) >= 12, str(len(d.get("pensioners", []))))
        r = httpx.post(B + "/api/status/lookup", json={"ppo_number": "1100 3456 7821", "date_of_birth": "1944-03-12"})
        check("family status check works on the fresh server", r.status_code == 200, r.text[:80])
    # wait until the background backup has reached n8n (Render stops a server gently and the app sends what is left;
    # this test stops it abruptly, so it waits instead)
    want = 2  # accounts: the new office + the sample office
    for _ in range(60):
        rows = httpx.post(STORE, json={"action": "get_all"}, headers=KEY, timeout=90).json().get("rows", [])
        if sum(r["key"].startswith("acc:") for r in rows) >= want and sum(r["key"].startswith("lk:") for r in rows) >= (12 if SAMPLE_KEY else 0):
            break
        time.sleep(1)
    check("backup reached n8n", sum(r["key"].startswith("acc:") for r in rows) >= want, f"{len(rows)} rows")
    time.sleep(2)
    stop(a)

    # ---------------- server B: brand-new empty database ----------------
    b = start(8094, tmp / "b.db"); B2 = "http://127.0.0.1:8094"
    log_b = (tmp / "b.log").read_text(encoding="utf-8")
    m = re.search(r"\[startup\] backup restore: (.*)", log_b)
    check("restart restored the backup", m and "'restored': True" in m.group(1), m.group(1)[:160] if m else log_b[:200])
    c2 = httpx.Client(base_url=B2, timeout=120)
    r = c2.post("/api/login", json={"email": NEW["email"], "password": NEW["password"]})
    check("new office can still log in after the restart", r.status_code == 200, r.text[:80])
    check("its setup progress was kept (step 3)", c2.get("/api/onboarding").json().get("step") == 3)
    check("wrong password still refused", httpx.post(B2 + "/api/login", json={"email": NEW["email"], "password": "nope-nope-nope"}).status_code == 401)
    s2 = httpx.Client(base_url=B2, timeout=120)
    check("sample office still logs in (not duplicated)", s2.post("/api/login", json=SEED).status_code == 200)
    check("startup says the sample office already exists", "sample office already exists" in log_b)
    if SAMPLE_KEY:
        r = httpx.post(B2 + "/api/status/lookup", json={"ppo_number": "1100 3456 7821", "date_of_birth": "1944-03-12"})
        check("family status check still works after the restart", r.status_code == 200, r.text[:80])
    stop(b)
finally:
    # clean up: remove every backup row this test wrote, and the test office's n8n workspace row stays harmless
    rows = httpx.post(STORE, json={"action": "get_all"}, headers=KEY, timeout=90).json().get("rows", [])
    for row in rows:
        httpx.post(STORE, json={"action": "delete", "key": row["key"]}, headers=KEY, timeout=60)
    print(f"cleanup: removed {len(rows)} backup rows")
    print(f"\n{sum(results)}/{len(results)} checks passed")
