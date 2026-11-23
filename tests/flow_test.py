"""End-to-end test of the whole app on a separate server (port 8099) with a THROWAWAY accounts database and the real n8n.
Office: landing -> sign up -> onboarding -> uploads -> dashboard -> letters. Family: status check with PPO + date of birth (no account).
Deletes every pensioner it created at the end. Run:  backend\\.venv\\Scripts\\python.exe tests\\flow_test.py
Note: it asks Claude (through n8n) to write 3-4 letters, a small AI cost."""
import os, subprocess, sys, tempfile, time
from pathlib import Path
import httpx

PROJECT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT)
os.environ["PH_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "flow.db")
SAMPLES = PROJECT / "sample_uploads"
SERVER = subprocess.Popen([r"backend\.venv\Scripts\python.exe", "-m", "uvicorn", "app:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8099", "--log-level", "warning"], env=dict(os.environ))
B = "http://127.0.0.1:8099"
for _ in range(60):
    try: httpx.get(B + "/", timeout=2); break
    except Exception: time.sleep(0.5)

results = []
def check(name, ok, extra=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""))
def client(): return httpx.Client(base_url=B, timeout=320, follow_redirects=False)
def files(*names, field="files"):
    return [(field, (n, (SAMPLES / n).read_bytes(), "application/pdf" if n.endswith(".pdf") else "text/csv")) for n in names]

stamp = str(int(time.time()))
OFFICE = {"email": f"office.{stamp}@example.com", "password": "Office-Test-2026!", "role": "office", "display_name": "Test Officer"}
OTHER = {"email": f"other.{stamp}@example.com", "password": "Other-Office-2026!", "role": "office", "display_name": "Other Officer"}
FAMILY = {"email": f"family.{stamp}@example.com", "password": "Family-Test-2026!", "role": "family", "display_name": "Ravi Sharma"}  # must be refused now
created = []  # (client, pensioner ids) for cleanup

try:
    anon = client()
    # ---------------- landing + gating ----------------
    r = anon.get("/")
    check("landing page loads with tagline and Get started", r.status_code == 200 and "No pensioner should lose their income" in r.text and "Get started" in r.text and "DEMO" not in r.text)
    for page in ("/dashboard", "/uploads", "/settings", "/onboarding"):
        check(f"{page} redirects to /login when signed out", anon.get(page).headers.get("location") == "/login")
    check("signup and login pages load", anon.get("/signup").status_code == 200 and anon.get("/login").status_code == 200 and "Forgot password" in anon.get("/login").text)
    check("CSV template downloads (with date of birth)", "name,age,date_of_birth,bank,language,ppo_number" in anon.get("/api/templates/pensioner-list.csv").text)

    # ---------------- sign up ----------------
    r = anon.post("/api/signup", json={**OFFICE, "password": "short"})
    check("weak password refused", r.status_code == 422, r.json().get("detail"))
    r = anon.post("/api/signup", json={**OFFICE, "email": "not-an-email"})
    check("bad email refused", r.status_code == 422, r.json().get("detail"))
    off = client()
    r = off.post("/api/signup", json=OFFICE)
    check("office signs up", r.status_code == 200 and r.json()["workspace"]["onboarding_step"] == 1)
    check("duplicate email refused", client().post("/api/signup", json=OFFICE).status_code == 409)
    check("password stored only as a hash", OFFICE["password"].encode() not in Path(os.environ["PH_DB_PATH"]).read_bytes())
    check("dashboard sends an unfinished account to onboarding", off.get("/dashboard").headers.get("location") == "/onboarding")

    # ---------------- onboarding (office) ----------------
    check("consent before details refused", off.post("/api/onboarding/consent", json={"consent": True}).status_code == 409)
    r = off.post("/api/onboarding/details", json={"office_name": "A", "district": "", "contact_name": "B", "phone": "12"})
    check("details validated per field", r.status_code == 422 and {"office_name", "district", "phone"} <= set(r.json()["fields"]), r.json()["detail"])
    r = off.post("/api/onboarding/details", json={"office_name": "District Pension Office Ranchi (Test)", "district": "Ranchi", "contact_name": "Test Officer", "phone": "98765 43210"})
    check("office details saved (step 2)", r.status_code == 200 and r.json()["step"] == 2)
    check("uploads blocked before consent", off.post("/api/upload/pensioner-list", files=files("pensioner_list.csv", field="file")).status_code == 409)
    r = off.post("/api/onboarding/consent", json={"consent": False})
    check("consent checkbox required", r.status_code == 422, r.json().get("detail"))
    check("consent saved (step 3)", off.post("/api/onboarding/consent", json={"consent": True}).json().get("step") == 3)

    # ---------------- uploads ----------------
    d = off.get("/api/overview").json()
    check("dashboard data starts empty", d["totals"]["pensioners"] == 0 and d["pensioners"] == [])
    r = off.post("/api/upload/statements", files=files("statement_ramprasad_yadav_SBI.csv"))
    check("statements before the list are refused", r.status_code == 409, r.json().get("detail"))
    r = off.post("/api/upload/pensioner-list", files=files("pensioner_list_with_errors.csv", field="file"))
    errs = r.json().get("errors", [])
    check("list with errors refused with 6 row messages", r.status_code == 422 and len(errs) == 6, "; ".join(f"row {e['row']} {e['field']}" for e in errs))
    check("nothing imported from the bad list", off.get("/api/overview").json()["totals"]["pensioners"] == 0)
    check("wrong file type refused", off.post("/api/upload/pensioner-list", files=[("file", ("list.xlsx", b"PK..", "application/octet-stream"))]).status_code == 422)
    r = off.post("/api/upload/pensioner-list", files=files("pensioner_list.csv", field="file"))
    check("good list imported (12 pensioners)", r.status_code == 200 and r.json()["added"] == 12, r.json().get("message"))
    check("same list again refused (duplicates)", off.post("/api/upload/pensioner-list", files=files("pensioner_list.csv", field="file")).status_code == 422)
    d = off.get("/api/overview").json()
    created.append((off, [p["id"] for p in d["pensioners"]]))
    raw = off.get("/api/overview").text
    check("only last 4 digits stored", "30012345678901" not in raw and "110034567821" not in raw and any(p["bank_account_last4"] == "8901" for p in d["pensioners"]))
    check("3 certificates from the list are verified", d["totals"]["lc_submitted"] == 3, str(d["totals"]["lc_submitted"]))
    stmts = ["statement_ramprasad_yadav_SBI.csv", "statement_savitri_kumari_PNB.pdf", "statement_lalita_deshmukh_BOM.pdf", "statement_mohammed_iqbal_BOB.csv", "statement_joseph_mathew_Canara.csv", "not_a_statement.csv"]
    r = off.post("/api/upload/statements", files=files(*stmts))
    res = r.json()["results"]
    good = [x for x in res if x["ok"]]
    check("5 statements read, 1 refused with a clear reason", len(good) == 5 and not next(x for x in res if x["filename"] == "not_a_statement.csv")["ok"])
    check("all 5 matched to the right pensioner automatically", all(x["match"] and x["match"]["name"].split()[0].lower() in x["filename"] for x in good),
          ", ".join(f"{x['filename'].split('_')[1]}→{(x['match'] or {}).get('name')} ({(x['match'] or {}).get('how')})" for x in good))
    check("no account numbers in the preview", "30012345678901" not in r.text and "4419000100045672" not in r.text)
    items = [{"token": x["token"], "pensioner_id": x["match"]["id"], "months": [m["month"] for m in x["months"]]} for x in good]
    r = off.post("/api/upload/statements/confirm", json={"items": items})
    check("payments saved for 5 pensioners", r.status_code == 200 and len(r.json()["saved"]) == 5, r.json().get("message"))
    check("onboarding finishes", off.post("/api/onboarding/finish").status_code == 200)
    check("dashboard page now opens", off.get("/dashboard").status_code == 200 and "office.js" in off.get("/dashboard").text)

    d = off.get("/api/overview").json()
    by = {p["name"]: p for p in d["pensioners"]}
    st = lambda n: {m["month"]: m["status"] for m in by[n]["payments"]["months"]}
    check("Ramprasad: September missing", st("Ramprasad Yadav").get("2026-09") == "missing" and by["Ramprasad Yadav"]["payments"]["amount_short"] == 50560)
    check("Savitri: DA not applied (₹720 x 4)", by["Savitri Kumari"]["payments"]["amount_short"] == 2880 and st("Savitri Kumari").get("2026-07") == "short")
    check("Lalita: Aug short + Oct missing", st("Lalita Deshmukh").get("2026-08") == "short" and st("Lalita Deshmukh").get("2026-10") == "missing", str(by["Lalita Deshmukh"]["payments"]["amount_short"]))
    check("Iqbal and Joseph paid in full", by["Mohammed Iqbal"]["payments"]["status"] == "ok" and by["Joseph Mathew"]["payments"]["status"] == "ok")
    check("totals: 3 with problems, 5 with statements", d["totals"]["payment_problem_pensioners"] == 3 and d["totals"]["payments_known"] == 5, f"pending {d['totals']['amount_pending']}")

    # ---------------- workspace isolation ----------------
    oth = client()
    oth.post("/api/signup", json=OTHER)
    oth.post("/api/onboarding/details", json={"office_name": "Another Test Office", "district": "Pune", "contact_name": "Other"})
    oth.post("/api/onboarding/consent", json={"consent": True}); oth.post("/api/onboarding/finish")
    d2 = oth.get("/api/overview").json()
    check("another office sees an empty dashboard", d2["totals"]["pensioners"] == 0)
    rp = by["Ramprasad Yadav"]
    check("another office can't edit my pensioner", oth.put(f"/api/pensioners/{rp['id']}", json={"name": "X Y", "age": 70, "bank": "SBI", "language": "Hindi", "basic_pension": 1000}).status_code == 404)
    check("another office can't delete my pensioner", oth.delete(f"/api/pensioners/{rp['id']}").status_code == 404)

    # ---------------- AI letters + tracker ----------------
    r = off.post("/api/letters/draft-now")
    check("Claude drafts letters for the 3 problems", r.status_code == 200 and r.json()["drafted"] == 3, r.json().get("message"))
    d = off.get("/api/overview").json()
    letter = next(g for g in d["letters"] if g["name"] == "Ramprasad Yadav")
    check("letter mentions the missing September amount", "50,560" in letter["letter"] and letter["status"] == "draft", letter["letter_source"])
    check("another office can't approve my letter", oth.post(f"/api/letters/{letter['id']}/decision", json={"decision": "approve"}).status_code == 404)
    ok = all(off.post(f"/api/letters/{letter['id']}/decision", json={"decision": s}).status_code == 200 for s in ("approve", "mark_sent", "mark_resolved"))
    check("tracker: approve → sent → resolved", ok)
    check("draft again adds nothing new", off.post("/api/letters/draft-now").json()["drafted"] == 0)
    r = off.post("/api/pensioners/record-certificate", json={"id": rp["id"], "pramaan_id": "TEST-JP-RY7821"})
    check("verify once still works", r.status_code == 200 and r.json().get("verified_until") == "2027-11-30")
    r = off.put("/api/settings", json={"da_old": 55, "da_new": 60, "da_new_from": "2026-07"})
    jul = next(m for m in next(p for p in off.get("/api/overview").json()["pensioners"] if p["name"] == "Mohammed Iqbal")["payments"]["months"] if m["month"] == "2026-07")
    check("DA rate change applies to this workspace (Iqbal Jul expected 44,800)", r.status_code == 200 and jul["expected"] == 44800, str(jul["expected"]))
    check("other workspace DA unchanged", oth.get("/api/settings").json()["da_new"] == 58)
    s = off.get("/api/settings").json()
    check("settings + activity log work", s["name"].startswith("District Pension Office") and any(a["action"] == "statement_imported" for a in s["activity"]))

    # ---------------- family flow (no account: PPO number + date of birth) ----------------
    r = client().post("/api/signup", json=FAMILY)
    check("family sign-up refused, pointed to the status box", r.status_code == 403 and "Check your pension status" in r.json()["detail"])
    check("landing page has the status box", 'id="check-form"' in client().get("/").text)
    check("office sees the family check is on (list had dates of birth)", all(p["online_check"] for p in off.get("/api/overview").json()["pensioners"]))
    fam = client()
    r = fam.post("/api/status/lookup", json={"ppo_number": "1100 3456 7821", "date_of_birth": "12/03/1944"})
    check("family finds Ramprasad with PPO + date of birth", r.status_code == 200)
    s = fam.get("/api/status")
    sd = s.json()
    rst = {m["month"]: m["status"] for m in sd["pensioner"]["payments"]["months"]}
    check("family sees the office's work: certificate verified, Sept missing, letter resolved",
          sd["pensioner"]["life_certificate"]["status"] == "done" and rst.get("2026-09") == "missing" and sd["letters"][0]["status"] == "resolved")
    check("status has no emails or account numbers", "@" not in s.text and "30012345678901" not in s.text and "bank_account" not in s.text)
    check("family can't open office data", fam.get("/api/overview").status_code == 401 and fam.post("/api/letters/draft-now").status_code == 401)
    # Kamla Devi: added by the office with a date of birth, then her own statement is uploaded for her
    r = off.post("/api/pensioners", json={"name": "Kamla Devi Sharma", "date_of_birth": "1945-02-10", "bank": "State Bank of India", "language": "Hindi",
                                          "ppo_number": "7700 1122 3344", "bank_account_number": "31122334455", "basic_pension": 30000, "consent": True})
    check("office adds Kamla with a date of birth", r.status_code == 200, r.text[:120])
    kid = r.json().get("id")
    r = off.post("/api/upload/statements", data={"pensioner_id": str(kid)}, files=files("family_statement_kamla_devi_SBI.csv"))
    x = r.json()["results"][0]
    check("Kamla's statement read for her", x["ok"] and x["match"]["name"] == "Kamla Devi Sharma", x.get("error"))
    off.post("/api/upload/statements/confirm", json={"items": [{"token": x["token"], "pensioner_id": kid, "months": [m["month"] for m in x["months"]]}]})
    fam2 = client()
    check("family finds Kamla", fam2.post("/api/status/lookup", json={"ppo_number": "770011223344", "date_of_birth": "1945-02-10"}).status_code == 200)
    kst = {m["month"]: m["status"] for m in fam2.get("/api/status").json()["pensioner"]["payments"]["months"]}
    check("Kamla: July short + October missing", kst.get("2026-07") == "short" and kst.get("2026-10") == "missing", str(kst))
    r = client().post("/api/status/lookup", json={"ppo_number": "770011223344", "date_of_birth": "1945-02-11"})
    check("wrong date of birth: not found, tries counted", r.status_code == 404 and r.json()["attempts_left"] == 4)

    # ---------------- login/logout ----------------
    check("wrong password refused", client().post("/api/login", json={"email": OFFICE["email"], "password": "nope-nope-nope"}).status_code == 401)
    r = client().post("/api/login", json={"email": OFFICE["email"].upper(), "password": OFFICE["password"]})
    check("login works (email not case-sensitive)", r.status_code == 200 and r.json()["workspace"]["onboarding_done"] is True)
    check("logout ends the session", off.post("/api/logout").status_code == 200 and off.get("/api/me").status_code == 401)
finally:
    # ---------------- cleanup: delete everything this test created in n8n ----------------
    for line in (PROJECT / "backend" / ".env").read_text().splitlines():
        if line.startswith("N8N_SHARED_SECRET="): key = line.split("=", 1)[1]
        if line.startswith("N8N_ADMIN_URL="): admin = line.split("=", 1)[1]
        if line.startswith("N8N_OVERVIEW_URL="): ov_url = line.split("=", 1)[1]
    removed = 0
    for who in (OFFICE,):
        c = client()
        if c.post("/api/login", json={"email": who["email"], "password": who["password"]}).status_code != 200:
            continue
        d = c.get("/api/overview").json()
        ws = d.get("dataset")
        for p in d.get("pensioners", []):
            httpx.post(admin, json={"action": "delete", "dataset": ws, "id": p["id"], "old_name": p["name"]}, headers={"X-Pension-Key": key}, timeout=60)
            removed += 1
    print(f"cleanup: removed {removed} test pensioners (with their payments and letters)")
    SERVER.terminate()

print(f"\n{sum(results)}/{len(results)} checks passed")
