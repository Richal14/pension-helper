"""Test: family status check (PPO + date of birth, no account), the 5-tries limit, and the office flow still working.
Separate server on port 8097 with a THROWAWAY accounts database and the real n8n. Deletes its pensioners at the end.
Run:  backend\\.venv\\Scripts\\python.exe tests\\status_test.py   (asks Claude, through n8n, to write 2 letters)"""
import os, sqlite3, subprocess, tempfile, time
from pathlib import Path
import httpx

PROJECT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT)
DBP = Path(tempfile.mkdtemp()) / "status.db"
os.environ["PH_DB_PATH"] = str(DBP)
SAMPLES = PROJECT / "sample_uploads"
SERVER = subprocess.Popen([r"backend\.venv\Scripts\python.exe", "-m", "uvicorn", "app:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8097", "--log-level", "warning"], env=dict(os.environ))
B = "http://127.0.0.1:8097"
for _ in range(60):
    try: httpx.get(B + "/", timeout=2); break
    except Exception: time.sleep(0.5)

results = []
def check(name, ok, extra=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""), flush=True)
def client(): return httpx.Client(base_url=B, timeout=320, follow_redirects=False)
def files(*names, field="files"):
    return [(field, (n, (SAMPLES / n).read_bytes(), "application/pdf" if n.endswith(".pdf") else "text/csv")) for n in names]
def clear_lock():
    with sqlite3.connect(DBP) as c: c.execute("DELETE FROM lookup_attempts")

RAM = {"ppo_number": "1100 3456 7821", "date_of_birth": "1944-03-12"}   # Ramprasad Yadav (September pension missing)
SAV = {"ppo_number": "2200-4567-8932", "date_of_birth": "1950-07-05"}   # Savitri Kumari (DA increase not applied)
stamp = str(int(time.time()))
OFFICE = {"email": f"office.{stamp}@example.com", "password": "Office-Test-2026!", "display_name": "Test Officer"}
off = client()
try:
    anon = client()
    # ---------------- landing + who can sign in ----------------
    r = anon.get("/")
    check("landing has the 'Check your pension status' box", r.status_code == 200 and "Check your pension status" in r.text and 'id="check-form"' in r.text and 'type="date"' in r.text)
    check("/status without a check goes back to the box", anon.get("/status").headers.get("location") == "/#check")
    check("/api/status without a check is refused", anon.get("/api/status").status_code == 401)
    r = anon.post("/api/signup", json={**OFFICE, "email": f"fam.{stamp}@example.com", "role": "family"})
    check("family sign-up refused (no family accounts)", r.status_code == 403 and "Check your pension status" in r.json()["detail"])
    check("sign-up page has no family choice", 'value="family"' not in anon.get("/signup").text)

    # ---------------- office flow (unchanged) ----------------
    r = off.post("/api/signup", json=OFFICE)
    check("office signs up", r.status_code == 200 and r.json()["role"] == "office")
    off.post("/api/onboarding/details", json={"office_name": "Status Test Office", "district": "Ranchi", "contact_name": "Test Officer"})
    check("consent step", off.post("/api/onboarding/consent", json={"consent": True}).json().get("step") == 3)
    r = off.post("/api/upload/pensioner-list", files=files("pensioner_list_with_errors.csv", field="file"))
    check("list with errors still refused (6 rows)", r.status_code == 422 and len(r.json().get("errors", [])) == 6)
    r = off.post("/api/upload/pensioner-list", files=files("pensioner_list.csv", field="file"))
    check("list with dates of birth imported, 12 can check online", r.status_code == 200 and r.json()["added"] == 12 and r.json()["online"] == 12, r.json().get("message"))
    raw = off.get("/api/overview").text
    check("dates of birth never sent to n8n", "1944" not in raw and "date_of_birth" not in raw)
    d = off.get("/api/overview").json()
    by = {p["name"]: p for p in d["pensioners"]}
    check("office sees 'online check on' for each pensioner", all(p["online_check"] for p in d["pensioners"]))
    r = off.post("/api/upload/statements", files=files("statement_ramprasad_yadav_SBI.csv", "statement_savitri_kumari_PNB.pdf"))
    good = [x for x in r.json()["results"] if x["ok"]]
    r = off.post("/api/upload/statements/confirm", json={"items": [{"token": x["token"], "pensioner_id": x["match"]["id"], "months": [m["month"] for m in x["months"]]} for x in good]})
    check("statements saved for both", r.status_code == 200 and len(r.json()["saved"]) == 2)
    check("onboarding finishes, dashboard/uploads/settings open", off.post("/api/onboarding/finish").status_code == 200
          and "office.js" in off.get("/dashboard").text and off.get("/uploads").status_code == 200 and off.get("/settings").status_code == 200)
    r = off.post("/api/letters/draft-now")
    check("Claude drafts the letters (2)", r.status_code == 200 and r.json()["drafted"] == 2, r.json().get("message"))
    letters = {g["name"]: g for g in off.get("/api/overview").json()["letters"]}
    check("office approves Savitri's letter", off.post(f"/api/letters/{letters['Savitri Kumari']['id']}/decision", json={"decision": "approve"}).status_code == 200)

    # ---------------- family 1: Ramprasad ----------------
    fam = client()
    r = fam.post("/api/status/lookup", json=RAM)
    check("Ramprasad found with PPO + date of birth", r.status_code == 200 and "ph_status" in r.headers.get("set-cookie", ""))
    check("status page opens", fam.get("/status").status_code == 200 and "status.js" in fam.get("/status").text)
    s = fam.get("/api/status")
    sd = s.json()
    months = {m["month"]: m["status"] for m in sd["pensioner"]["payments"]["months"]}
    check("shows life certificate (due) and September missing", sd["pensioner"]["life_certificate"]["status"] in ("open", "urgent") and months.get("2026-09") == "missing"
          and sd["pensioner"]["payments"]["amount_short"] == 50560, str(sd["pensioner"]["life_certificate"]["status"]))
    check("complaint tracker: letter drafted", len(sd["letters"]) == 1 and sd["letters"][0]["status"] == "draft")
    check("no emails, account numbers or consent details", "@" not in s.text and "30012345678901" not in s.text and "bank_account" not in s.text and "consent" not in s.text)
    check("only this one pensioner", sd["pensioner"]["name"] == "Ramprasad Yadav" and "Savitri" not in s.text)
    check("family can't use office data routes", fam.get("/api/overview").status_code == 401 and fam.post("/api/letters/draft-now").status_code == 401)
    check("'check another' clears the status", fam.post("/api/status/leave").status_code == 200 and fam.get("/api/status").status_code == 401)

    # ---------------- family 2: Savitri (PPO typed with dashes, letter approved) ----------------
    fam2 = client()
    check("Savitri found (dashes in PPO are fine)", fam2.post("/api/status/lookup", json=SAV).status_code == 200)
    sd2 = fam2.get("/api/status").json()
    check("Savitri: DA short ₹2,880 and letter approved by office", sd2["pensioner"]["payments"]["amount_short"] == 2880 and sd2["letters"][0]["status"] == "approved"
          and sd2["letters"][0]["timeline"].get("approved"))
    check("date in DD/MM/YYYY also works", client().post("/api/status/lookup", json={"ppo_number": "220045678932", "date_of_birth": "05/07/1950"}).status_code == 200)
    tampered = client(); tampered.cookies.set("ph_status", fam2.cookies.get("ph_status")[:-3] + "abc")
    check("a changed status cookie is refused", tampered.get("/api/status").status_code == 401)

    # ---------------- office edits keep working ----------------
    rp = by["Ramprasad Yadav"]
    body = {"name": "Ramprasad Yadav", "age": 82, "bank": "State Bank of India", "language": "Hindi", "basic_pension": 32000, "commuted_amount": 0,
            "family_email": "ramprasad.family@example.com", "ppo_number": "1100 3456 9999"}
    r = off.put(f"/api/pensioners/{rp['id']}", json=body)
    check("new PPO without date of birth is refused (keeps family access right)", r.status_code == 422 and "date_of_birth" in r.json().get("fields", {}))
    r = off.put(f"/api/pensioners/{rp['id']}", json={**body, "ppo_number": "", "age": 83})
    check("normal edit (age only) still works", r.status_code == 200)
    r = off.post("/api/pensioners", json={"name": "Kamla Devi Sharma", "date_of_birth": "1945-02-10", "bank": "State Bank of India", "language": "Hindi",
                                          "ppo_number": "7700 1122 3344", "basic_pension": 30000, "consent": True})
    check("office adds a pensioner with date of birth (age worked out)", r.status_code == 200, r.text[:150])
    kid = r.json().get("id")
    check("new pensioner can be checked online", client().post("/api/status/lookup", json={"ppo_number": "770011223344", "date_of_birth": "1945-02-10"}).status_code == 200)
    k = next(p for p in off.get("/api/overview").json()["pensioners"] if p["name"] == "Kamla Devi Sharma")
    check("age worked out from date of birth (81)", k["age"] == 81, str(k["age"]))
    check("office deletes Kamla", off.delete(f"/api/pensioners/{kid}").status_code == 200)

    # ---------------- wrong tries: 5 then wait 10 minutes ----------------
    clear_lock()
    bad = client()
    r = bad.post("/api/status/lookup", json={"ppo_number": "12", "date_of_birth": ""})
    check("typing mistakes don't count as a wrong try", r.status_code == 422)
    r = bad.post("/api/status/lookup", json={"ppo_number": "770011223344", "date_of_birth": "1945-02-10"})
    check("deleted pensioner is no longer found", r.status_code == 404 and r.json()["attempts_left"] == 4)
    lefts = [bad.post("/api/status/lookup", json={"ppo_number": "110034567821", "date_of_birth": f"1944-04-1{i}"}).json().get("attempts_left") for i in range(3)]
    check("wrong tries count down 3, 2, 1", lefts == [3, 2, 1], str(lefts))
    r = bad.post("/api/status/lookup", json={"ppo_number": "110034567821", "date_of_birth": "1944-04-19"})
    check("5th wrong try: wait 10 minutes", r.status_code == 429 and r.json()["code"] == "locked" and 590 <= r.json()["wait_seconds"] <= 600, r.json().get("detail"))
    r = bad.post("/api/status/lookup", json=RAM)
    check("even the right details wait during the lock", r.status_code == 429)
    with sqlite3.connect(DBP) as c:
        c.execute("UPDATE lookup_attempts SET locked_until = ?", (time.time() - 1,))
    check("after the wait, the right details work again", bad.post("/api/status/lookup", json=RAM).status_code == 200)
    check("office login is not affected by the lock", client().post("/api/login", json={"email": OFFICE["email"], "password": OFFICE["password"]}).status_code == 200)

    # ---------------- old family accounts can no longer log in ----------------
    import sys; sys.path.insert(0, str(PROJECT / "backend"))
    import db as _db
    _db.sign_up(f"oldfam.{stamp}@example.com", "Old-Family-2026!", "family", "Old Family")
    r = client().post("/api/login", json={"email": f"oldfam.{stamp}@example.com", "password": "Old-Family-2026!"})
    check("old family account login refused with a pointer to the box", r.status_code == 403 and "Check your pension status" in r.json()["detail"])
    check("no n8n link in any page or script", not any("n8n.cloud" in (PROJECT / "frontend" / f).read_text(encoding="utf-8")
          for f in ["index.html", "status.html", "login.html", "signup.html", "office.html", "assets/status.js", "assets/common.js", "assets/office.js"]))
finally:
    for line in (PROJECT / "backend" / ".env").read_text().splitlines():
        if line.startswith("N8N_SHARED_SECRET="): key = line.split("=", 1)[1]
        if line.startswith("N8N_ADMIN_URL="): admin = line.split("=", 1)[1]
    removed = 0
    try:
        d = off.get("/api/overview").json()
        for p in d.get("pensioners", []):
            httpx.post(admin, json={"action": "delete", "dataset": d["dataset"], "id": p["id"], "old_name": p["name"]}, headers={"X-Pension-Key": key}, timeout=60)
            removed += 1
    except Exception as e:
        print("cleanup problem:", e)
    print(f"cleanup: removed {removed} test pensioners (with their payments and letters)")
    SERVER.terminate()
    print(f"\n{sum(results)}/{len(results)} checks passed")
