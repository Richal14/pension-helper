"""Pension Helper backend.

Office flow: Landing page -> Sign up / Login (email + password) -> Onboarding (3 steps) -> Dashboard.
Family flow: Landing page -> "Check your pension status" (PPO number + date of birth, no account) -> /status.
- Every Pension Office account owns one private workspace; the dashboard is built only
  from that workspace's uploaded data (the workspace key is the `dataset` value in n8n).
- Family status check: the backend keeps only a one-way fingerprint (HMAC) of PPO + date of birth.
  5 wrong attempts from one device -> wait 10 minutes. The status page is read-only.
- Uploads: a pensioner list (CSV, validated row by row) and bank statements (CSV/PDF).
- Privacy: only the last 4 digits of PPO and bank account numbers leave the backend; statement
  files are read in memory and never stored; consent is recorded before any pensioner data is stored.
- The n8n webhook URLs and secret stay in backend/.env; pages only call /api on this server.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator

import db
import pensioner_list
import statements
from models import EMAIL_RE, LANGUAGES, PRAMAAN_RE, PensionerIn, digits, for_n8n, parse_date

BASE = Path(__file__).resolve().parent
FRONTEND = BASE.parent / "frontend"
load_dotenv(BASE / ".env")


def _setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing {name} in backend/.env (copy backend/.env.example to start).")
    return value


N8N = {k: _setting(f"N8N_{k}_URL") for k in ("OVERVIEW", "CHECK", "DECISION", "RECORD", "ADMIN", "IMPORT", "WORKSPACE", "DRAFT")}
N8N_SHARED_SECRET = _setting("N8N_SHARED_SECRET")
SESSION_SECRET = _setting("SESSION_SECRET").encode()
SESSION_SECONDS = int(float(os.getenv("SESSION_HOURS", "8")) * 3600)
COOKIE = "ph_session"
STATUS_COOKIE = "ph_status"
STATUS_SECONDS = 30 * 60
LOOKUP_SECRET = (os.getenv("LOOKUP_SECRET", "").strip() or _setting("SESSION_SECRET")).encode()
FAMILY_MOVED = "Families don't need an account any more. Please use “Check your pension status” on the home page with the PPO number and date of birth."
DA_DEFAULT = {"da_old": 55, "da_new": 58, "da_new_from": "2026-07"}
# Cookies only travel over HTTPS when hosted (Render sets RENDER=true); plain http://localhost keeps working.
SECURE_COOKIES = os.getenv("RENDER", "").lower() == "true" or os.getenv("COOKIE_SECURE", "").lower() in ("1", "true", "yes")

db.init()
# On hosts that wipe the disk on restart: refill an empty accounts database from the n8n backup (N8N_STORE_URL).
try:
    print("[startup] backup restore:", db.restore_from_backup(), flush=True)
except Exception as exc:  # the app still starts; new sign-ups keep working
    print("[startup] could not restore the backup:", exc, flush=True)

# ---------------------------------------------------------------- sessions


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _make_token(acc: dict) -> str:
    payload = _b64(json.dumps({"uid": acc["id"], "v": acc["token_version"], "exp": int(time.time()) + SESSION_SECONDS}).encode())
    return f"{payload}.{_b64(hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).digest())}"


def _read_token(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _b64(hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).digest())):
        return None
    try:
        data = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if data.get("exp", 0) < time.time():
        return None
    acc = db.get_account(int(data.get("uid", 0)))
    if not acc or acc["token_version"] != data.get("v"):  # a password change ends every old session
        return None
    if acc["role"] != "office":  # only Pension Office staff sign in; families use the status check
        return None
    acc["workspace"] = db.get_workspace(acc["workspace_id"])
    return acc


def current(request: Request) -> dict | None:
    return _read_token(request.cookies.get(COOKIE))


def _set_cookie(response: Response, acc: dict) -> None:
    response.set_cookie(COOKIE, _make_token(acc), max_age=SESSION_SECONDS, httponly=True, samesite="strict", secure=SECURE_COOKIES, path="/")


def signed_in(request: Request) -> dict:
    acc = current(request)
    if not acc:
        raise HTTPException(401, "Please sign in.")
    return acc


def office_only(request: Request) -> dict:
    acc = signed_in(request)
    if acc["role"] != "office":
        raise HTTPException(403, "Only a Pension Office account can do this.")
    return acc


def consented(request: Request) -> dict:
    acc = signed_in(request)
    if not acc["workspace"]["consent_at"]:
        raise HTTPException(409, "Please complete the consent step first.")
    return acc


def _me(acc: dict) -> dict:
    ws = acc["workspace"]
    return {"email": acc["email"], "role": acc["role"], "display_name": acc["display_name"],
            "workspace": {"name": ws["name"], "onboarding_step": ws["onboarding_step"], "onboarding_done": bool(ws["onboarding_done"]),
                          "consent_at": ws["consent_at"]}}


# ---------------------------------------------------------------- n8n


SAMPLE_LIST = BASE.parent / "sample_uploads" / "pensioner_list.csv"


async def _seed_sample_office(client: httpx.AsyncClient) -> str:
    """Optional, for a hosted demo: make sure the sample Pension Office account exists.

    Set SEED_OFFICE_EMAIL and SEED_OFFICE_PASSWORD (10+ characters). SEED_WORKSPACE_KEY (optional) links the
    account to sample data already in n8n. Family status-check fingerprints are rebuilt from the sample list,
    so the sample PPO + date of birth work. Runs on every start and does nothing when everything is in place.
    """
    email = os.getenv("SEED_OFFICE_EMAIL", "").strip().lower()
    password = os.getenv("SEED_OFFICE_PASSWORD", "")
    if not email or not password:
        return "no seed account configured"
    if not EMAIL_RE.match(email) or len(password) < 10:
        return "SEED_OFFICE_EMAIL must be an email and SEED_OFFICE_PASSWORD at least 10 characters"
    acc = db.account_by_email(email)
    note = "sample office already exists"
    if not acc:
        office = os.getenv("SEED_OFFICE_NAME", "").strip() or "District Pension Office Ranchi"
        acc, ws = db.sign_up(email, password, "office", "Demo Officer")
        fields = {"name": office, "details": {"office_name": office, "district": "Ranchi", "contact_name": "Demo Officer", "phone": ""},
                  "consent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "consent_by": email,
                  "onboarding_step": 3, "onboarding_done": 1}
        key = os.getenv("SEED_WORKSPACE_KEY", "").strip()
        if re.fullmatch(r"w\d{1,9}", key) and not db._con.execute("SELECT 1 FROM workspaces WHERE key = ?", (key,)).fetchone():
            fields["key"] = key  # reuse the sample data already stored in n8n under this key
        ws = db.update_workspace(ws["id"], **fields)
        if "key" not in fields:  # a brand-new, empty workspace: register it in n8n
            await client.post(N8N["WORKSPACE"], json={"action": "upsert", "key": ws["key"], "values": {
                "kind": "office", "name": office, "email": email, **DA_DEFAULT}})
        db.audit(ws["id"], email, "sample_office_created")
        acc = db.account_by_email(email)
        note = "sample office created"
    ws = db.get_workspace(acc["workspace_id"])
    if db.lookup_ids(ws["id"]) or not SAMPLE_LIST.exists():
        return note
    res = await client.get(N8N["OVERVIEW"], params={"dataset": ws["key"]})
    ids = {p["name"].lower(): p["id"] for p in (res.json().get("pensioners") or [])}
    made = 0
    with SAMPLE_LIST.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid, dob = ids.get((row.get("name") or "").strip().lower()), parse_date(row.get("date_of_birth") or "")
            if pid and dob and digits(row.get("ppo_number")):
                db.set_lookup(ws["id"], int(pid), _fingerprint(digits(row["ppo_number"]), dob.isoformat()))
                made += 1
    return f"{note}; family status check turned on for {made} sample pensioners"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10), headers={"X-Pension-Key": N8N_SHARED_SECRET})
    app.state.previews = {}
    try:
        print("[startup] sample office:", await _seed_sample_office(app.state.http), flush=True)
    except Exception as exc:  # never stop the app from starting
        print("[startup] could not prepare the sample office:", exc, flush=True)
    yield
    db.flush_backup(10)  # send any backups still waiting before the server stops
    await app.state.http.aclose()


async def _n8n(request: Request, method: str, key: str, body: dict | None = None, params: dict | None = None, timeout: float | None = None):
    try:
        kw = {"json": body, "params": params}
        if timeout:
            kw["timeout"] = timeout
        res = await request.app.state.http.request(method, N8N[key], **kw)
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach n8n. Check the internet connection.")
    try:
        data = res.json()
    except ValueError:
        raise HTTPException(502, "n8n sent an unexpected reply. Is the workflow switched on?")
    return res.status_code, data


async def _overview_key(request: Request, key: str) -> dict:
    status, data = await _n8n(request, "GET", "OVERVIEW", params={"dataset": key})
    if status != 200 or not isinstance(data, dict) or not {"pensioners", "letters", "totals", "generated_at"} <= data.keys():
        raise HTTPException(502, "n8n did not send the overview. Check that the workflow is on and the secret key matches.")
    if data.get("dataset") != key:
        raise HTTPException(502, "n8n sent data for the wrong workspace.")
    return data


async def _overview(request: Request, acc: dict) -> dict:
    return await _overview_key(request, acc["workspace"]["key"])


def _fingerprint(ppo_digits: str, dob_iso: str) -> str:
    """One-way fingerprint of PPO number + date of birth. Neither value can be read back from it."""
    return hmac.new(LOOKUP_SECRET, f"{ppo_digits}|{dob_iso}".encode(), hashlib.sha256).hexdigest()


async def _sync_workspace(request: Request, ws: dict, email: str, da: dict | None = None) -> dict:
    values = {"kind": ws["kind"], "name": ws["name"] or email, "email": email, **(da or DA_DEFAULT)}
    status, data = await _n8n(request, "POST", "WORKSPACE", {"action": "upsert", "key": ws["key"], "values": values})
    if status != 200 or not data.get("ok"):
        raise HTTPException(502, "n8n could not save the workspace.")
    return data["workspace"]


async def _workspace_n8n(request: Request, ws: dict) -> dict:
    status, data = await _n8n(request, "POST", "WORKSPACE", {"action": "get", "key": ws["key"]})
    if status != 200 or not isinstance(data, dict):
        raise HTTPException(502, "n8n did not send the workspace.")
    return data.get("workspace") or {}


def _find(data: dict, pensioner_id: int) -> dict:
    p = next((x for x in data["pensioners"] if x.get("id") == pensioner_id), None)
    if not p:
        raise HTTPException(404, "This pensioner was not found in your workspace.")
    return p


# ---------------------------------------------------------------- app

app = FastAPI(title="Pension Helper", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

FIELD_NAMES = {"name": "Name", "age": "Age", "bank": "Bank", "language": "Language", "family_email": "Family email",
               "ppo_number": "PPO number", "bank_account_number": "Bank account number", "basic_pension": "Basic pension",
               "commuted_amount": "Commuted amount", "email": "Email", "password": "Password", "role": "Account type",
               "display_name": "Your name", "pramaan_id": "Jeevan Pramaan ID", "da_old": "DA rate (old)", "da_new": "DA rate (new)",
               "da_new_from": "New DA from (month)", "office_name": "Office name", "district": "District", "contact_name": "Contact person",
               "phone": "Phone", "your_name": "Your name", "relation": "Relation", "date_of_birth": "Date of birth"}


@app.exception_handler(RequestValidationError)
async def friendly_validation(request: Request, exc: RequestValidationError):
    """One plain message plus a message per form field."""
    fields = {}
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query", "path")]
        field = loc[-1] if loc else ""
        msg = str(err.get("msg", "")).removeprefix("Value error, ")
        t = err.get("type")
        if t == "string_pattern_mismatch":
            msg = "This is not in the expected format."
        elif t in ("greater_than_equal", "less_than_equal"):
            msg = f"Please enter a value within the allowed range ({msg.lower()})."
        elif t in ("int_parsing", "float_parsing"):
            msg = "Please enter a number."
        elif t == "missing":
            msg = "This is required."
        elif t == "literal_error":
            msg = "Please choose one of the options."
        elif t == "string_too_short":
            msg = "This is too short. Please write it in full."
        elif t == "string_too_long":
            msg = "This is too long."
        fields.setdefault(field or "_", msg)
    first, first_msg = next(iter(fields.items()), ("", "Please check what you typed."))
    label = FIELD_NAMES.get(first, "")
    return JSONResponse({"detail": (label + ": " if label else "") + first_msg, "fields": fields, "code": "invalid"}, status_code=422)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-cache" if request.url.path.startswith("/assets/") else "no-store"
    return response


# ---------------------------------------------------------------- sign up / login


def _check_password(password: str, email: str) -> str:
    if len(password) < 10:
        raise HTTPException(422, "The password must be at least 10 characters.")
    if password.lower() in {email.lower(), "password123", "1234567890", "pension123", "qwertyuiop"}:
        raise HTTPException(422, "Please choose a less guessable password.")
    return password


class SignupIn(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(min_length=1, max_length=128)
    role: Literal["office", "family"] = "office"
    display_name: str = Field(min_length=2, max_length=60)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Please enter a valid email address.")
        return v


@app.post("/api/signup")
async def signup(body: SignupIn, request: Request, response: Response):
    if body.role != "office":
        raise HTTPException(403, FAMILY_MOVED)
    if db.email_taken(body.email):
        raise HTTPException(409, "An account with this email already exists. Please log in instead.")
    _check_password(body.password, body.email)
    acc, ws = db.sign_up(body.email, body.password, body.role, body.display_name.strip())
    ws = db.update_workspace(ws["id"], name=body.display_name.strip() if body.role == "family" else "")
    try:
        await _sync_workspace(request, ws, acc["email"])
    except HTTPException:
        pass  # synced again at the details step
    db.audit(ws["id"], acc["email"], "signed_up", body.role)
    _set_cookie(response, acc)
    acc["workspace"] = ws
    return _me(acc)


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=128)


@app.post("/api/login")
def login(body: LoginIn, response: Response):
    email = body.email.strip().lower()
    acc, why = db.check_login(email, body.password)
    if why == "locked":
        raise HTTPException(429, "Too many wrong passwords. This account is locked for 10 minutes.")
    if not acc:
        raise HTTPException(401, "Wrong email or password.")
    if acc["role"] != "office":
        raise HTTPException(403, FAMILY_MOVED)
    acc["workspace"] = db.get_workspace(acc["workspace_id"])
    db.audit(acc["workspace_id"], acc["email"], "logged_in")
    _set_cookie(response, acc)
    return _me(acc)


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(acc: dict = Depends(signed_in)):
    return _me(acc)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


@app.post("/api/me/password")
def change_password(body: PasswordIn, response: Response, acc: dict = Depends(signed_in)):
    if not db.verify_password(acc["id"], body.current_password):
        raise HTTPException(400, "The current password is wrong.")
    db.set_password(acc["id"], _check_password(body.new_password, acc["email"]))
    db.audit(acc["workspace_id"], acc["email"], "password_changed")
    _set_cookie(response, db.get_account(acc["id"]))
    return {"ok": True}


# ---------------------------------------------------------------- onboarding


class OfficeDetails(BaseModel):
    office_name: str = Field(min_length=3, max_length=120)
    district: str = Field(min_length=2, max_length=80)
    contact_name: str = Field(min_length=2, max_length=80)
    phone: str = ""

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        d = digits(v)
        if v.strip() and not (10 <= len(d) <= 12):
            raise ValueError("Please enter a 10-digit phone number, or leave it empty.")
        return d


class FamilyDetails(PensionerIn):
    your_name: str = Field(min_length=2, max_length=80)
    relation: Literal["Self", "Son", "Daughter", "Spouse", "Other relative", "Caregiver"]


@app.get("/api/onboarding")
def onboarding_state(acc: dict = Depends(signed_in)):
    ws = acc["workspace"]
    return {"role": acc["role"], "step": ws["onboarding_step"], "done": bool(ws["onboarding_done"]),
            "details": ws["details"], "consent_at": ws["consent_at"], "languages": LANGUAGES}


@app.post("/api/onboarding/details")
async def onboarding_details(request: Request, acc: dict = Depends(signed_in)):
    try:
        raw = await request.json()
        if not isinstance(raw, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(400, "Please send the form again.")
    ws = acc["workspace"]
    try:
        d = OfficeDetails(**raw) if acc["role"] == "office" else FamilyDetails(**{**raw, "consent": True})
    except ValidationError as e:
        raise RequestValidationError(e.errors())
    if acc["role"] == "office":
        details = d.model_dump()
        name = d.office_name.strip()
    else:
        if not d.ppo_number:
            raise HTTPException(422, "PPO number: The PPO number is required.")
        # PRIVACY: only the last-4-digit version is kept, even before consent.
        details = {"your_name": d.your_name, "relation": d.relation, "pensioner": for_n8n(d)}
        name = f"{d.name} (family)"
    ws = db.update_workspace(ws["id"], details=details, name=name, onboarding_step=max(ws["onboarding_step"], 2))
    await _sync_workspace(request, ws, acc["email"])
    db.audit(ws["id"], acc["email"], "onboarding_details_saved")
    return {"ok": True, "step": ws["onboarding_step"]}


class ConsentIn(BaseModel):
    consent: bool


@app.post("/api/onboarding/consent")
async def onboarding_consent(body: ConsentIn, request: Request, acc: dict = Depends(signed_in)):
    ws = acc["workspace"]
    if ws["onboarding_step"] < 2:
        raise HTTPException(409, "Please fill in your details first.")
    if not body.consent:
        return JSONResponse({"detail": "Consent is required: please tick the box to continue.", "fields": {"consent": "Please tick this box to continue."}, "code": "invalid"}, status_code=422)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not ws["consent_at"]:
        ws = db.update_workspace(ws["id"], consent_at=stamp, consent_by=acc["email"])
    if acc["role"] == "family" and not ws["details"].get("pensioner_id"):
        pensioner = {**ws["details"]["pensioner"], "consent_given_at": ws["consent_at"], "consent_by": acc["email"]}
        status, res = await _n8n(request, "POST", "ADMIN", {"action": "create", "dataset": ws["key"], "pensioner": pensioner})
        if status != 200 or not res.get("ok"):
            raise HTTPException(502, "n8n could not save the pensioner.")
        ws = db.update_workspace(ws["id"], details={**ws["details"], "pensioner_id": res.get("id")})
    ws = db.update_workspace(ws["id"], onboarding_step=max(ws["onboarding_step"], 3))
    db.audit(ws["id"], acc["email"], "consent_given", "Agreed to storing pensioner data")
    return {"ok": True, "step": 3}


@app.post("/api/onboarding/finish")
def onboarding_finish(acc: dict = Depends(consented)):
    db.update_workspace(acc["workspace"]["id"], onboarding_done=1)
    db.audit(acc["workspace_id"], acc["email"], "onboarding_finished")
    return {"ok": True}


# ---------------------------------------------------------------- uploads


@app.get("/api/templates/pensioner-list.csv")
def template():
    return PlainTextResponse(pensioner_list.template_csv(), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="pensioner_list_template.csv"'})


@app.post("/api/upload/pensioner-list")
async def upload_list(request: Request, file: UploadFile = File(...), acc: dict = Depends(consented)):
    if acc["role"] != "office":
        raise HTTPException(403, "Only a Pension Office account can upload a pensioner list.")
    data = await file.read(pensioner_list.MAX_BYTES + 1)
    current_data = await _overview(request, acc)
    try:
        rows = pensioner_list.read_list(file.filename or "", data, {p["name"].lower() for p in current_data["pensioners"]},
                                        acc["workspace"]["consent_at"], acc["email"])
    except pensioner_list.ListError as e:
        return JSONResponse({"detail": str(e), "errors": e.errors, "code": "invalid_file"}, status_code=422)
    lookups = {r["name"].lower(): r.pop("_lookup") for r in rows if "_lookup" in r}  # stays in the backend
    status, res = await _n8n(request, "POST", "ADMIN", {"action": "create_many", "dataset": acc["workspace"]["key"], "pensioners": rows}, timeout=180)
    if status != 200 or not res.get("ok"):
        raise HTTPException(502, "n8n could not save the pensioners.")
    if lookups:
        for p in (await _overview(request, acc))["pensioners"]:
            if p["name"].lower() in lookups:
                db.set_lookup(acc["workspace_id"], p["id"], _fingerprint(*lookups[p["name"].lower()]))
    db.audit(acc["workspace_id"], acc["email"], "pensioner_list_uploaded", f"{len(rows)} pensioners from {file.filename}")
    online = f" {len(lookups)} can check their status online." if lookups else ""
    return {"ok": True, "added": len(rows), "online": len(lookups), "message": f"{len(rows)} pensioners added.{online}"}


PREVIEW_SECONDS = 20 * 60


def _match(parsed: dict, pensioners: list[dict]) -> tuple[dict | None, str]:
    acct, ppos = parsed.get("account_last4"), set(parsed.get("ppo_last4s") or [])
    by_acct = [p for p in pensioners if acct and p.get("bank_account_last4") == acct]
    if len(by_acct) == 1:
        return by_acct[0], f"bank account ending {acct}"
    if len(by_acct) > 1:  # two accounts end the same: use the PPO number in the statement to decide
        both = [p for p in by_acct if p.get("ppo_last4") in ppos]
        if len(both) == 1:
            return both[0], f"bank account ending {acct} and PPO ending {both[0]['ppo_last4']}"
        return None, ""
    by_ppo = [p for p in pensioners if p.get("ppo_last4") and p["ppo_last4"] in ppos]
    if len(by_ppo) == 1:
        return by_ppo[0], f"PPO ending {by_ppo[0]['ppo_last4']}"
    if len(pensioners) == 1:
        return pensioners[0], "your pensioner"
    return None, ""


@app.post("/api/upload/statements")
async def upload_statements(request: Request, files: list[UploadFile] = File(...), pensioner_id: int = Form(0), acc: dict = Depends(consented)):
    if not files or len(files) > 20:
        raise HTTPException(422, "Please choose 1 to 20 statement files.")
    data = await _overview(request, acc)
    if not data["pensioners"]:
        raise HTTPException(409, "Please upload your pensioner list first, so statements can be matched to pensioners.")
    previews = request.app.state.previews
    t = time.time()
    for k in [k for k, v in previews.items() if v["expires"] < t]:
        previews.pop(k, None)
    results = []
    for f in files:
        raw = await f.read(statements.MAX_BYTES + 1)
        try:
            parsed = statements.read_statement(f.filename or "", raw)
        except statements.StatementError as e:
            results.append({"filename": f.filename, "ok": False, "error": str(e)})
            continue
        forced = next((p for p in data["pensioners"] if p["id"] == pensioner_id), None) if pensioner_id else None
        match, how = (forced, "chosen by you") if forced else _match(parsed, data["pensioners"])
        token = secrets.token_urlsafe(24)
        previews[token] = {"account_id": acc["id"], "parsed": parsed, "expires": t + PREVIEW_SECONDS}
        results.append({"filename": f.filename, "ok": True, "token": token, "period": parsed["period"],
                        "transactions_read": parsed["transactions_read"], "months": parsed["months"],
                        "match": {"id": match["id"], "name": match["name"], "how": how} if match else None})
    return {"results": results, "pensioners": [{"id": p["id"], "name": p["name"], "ppo_last4": p["ppo_last4"]} for p in data["pensioners"]]}


class ConfirmItem(BaseModel):
    token: str = Field(min_length=10, max_length=64)
    pensioner_id: int
    months: list[str] = Field(min_length=1, max_length=60)


class ConfirmIn(BaseModel):
    items: list[ConfirmItem] = Field(min_length=1, max_length=20)


@app.post("/api/upload/statements/confirm")
async def confirm_statements(body: ConfirmIn, request: Request, acc: dict = Depends(consented)):
    data = await _overview(request, acc)
    previews = request.app.state.previews
    saved = []
    for item in body.items:
        pv = previews.get(item.token)
        if not pv or pv["account_id"] != acc["id"] or pv["expires"] < time.time():
            raise HTTPException(400, "A preview has expired. Please upload the statement again.")
        p = _find(data, item.pensioner_id)
        if not p.get("basic_pension"):
            raise HTTPException(400, f"Please add {p['name']}'s basic pension first, so payments can be checked.")
        chosen = [m for m in pv["parsed"]["months"] if m["month"] in set(item.months)]
        if not chosen:
            continue
        status, res = await _n8n(request, "POST", "IMPORT", {
            "dataset": acc["workspace"]["key"], "name": p["name"], "basic_pension": p["basic_pension"], "commuted_amount": p.get("commuted_amount") or 0,
            "months": [{"month": m["month"], "amount_received": m["amount_received"]} for m in chosen]})
        if status != 200 or not res.get("ok"):
            raise HTTPException(502, "n8n could not save the payments.")
        previews.pop(item.token, None)
        saved.append({"name": p["name"], "months": len(chosen)})
        db.audit(acc["workspace_id"], acc["email"], "statement_imported", f"{p['name']}: {', '.join(m['month'] for m in chosen)}")
    if not saved:
        raise HTTPException(400, "Please choose at least one month to save.")
    return {"ok": True, "saved": saved, "message": f"Saved payments for {len(saved)} pensioner(s)."}


# ---------------------------------------------------------------- dashboard data


@app.get("/api/overview")
async def overview(request: Request, acc: dict = Depends(signed_in)):
    data = await _overview(request, acc)
    online = db.lookup_ids(acc["workspace_id"])
    for p in data["pensioners"]:
        p["online_check"] = p.get("id") in online
    return data


@app.post("/api/pensioners")
async def add_pensioner(body: PensionerIn, request: Request, acc: dict = Depends(office_only)):
    if not body.consent:
        return JSONResponse({"detail": "Consent is required: please confirm that the pensioner (or their family) agreed to this data being stored.",
                             "fields": {"consent": "Consent is required before adding a pensioner."}, "code": "invalid"}, status_code=422)
    if not body.ppo_number:
        raise HTTPException(422, "PPO number: The PPO number is required.")
    data = await _overview(request, acc)
    if any(p["name"].lower() == body.name.lower() for p in data["pensioners"]):
        raise HTTPException(409, "A pensioner with this name already exists.")
    pensioner = {**for_n8n(body), "consent_given_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "consent_by": acc["email"]}
    status, res = await _n8n(request, "POST", "ADMIN", {"action": "create", "dataset": acc["workspace"]["key"], "pensioner": pensioner})
    if status != 200 or not res.get("ok"):
        raise HTTPException(502, "n8n could not add the pensioner.")
    if body.date_of_birth and res.get("id"):
        db.set_lookup(acc["workspace_id"], int(res["id"]), _fingerprint(body.ppo_number, body.date_of_birth))
    db.audit(acc["workspace_id"], acc["email"], "pensioner_added", body.name)
    return {"ok": True, "id": res.get("id"), "message": f"{body.name} was added."}


@app.put("/api/pensioners/{pensioner_id}")
async def edit_pensioner(pensioner_id: int, body: PensionerIn, request: Request, acc: dict = Depends(signed_in)):
    data = await _overview(request, acc)
    cur = _find(data, pensioner_id)
    if any(p["name"].lower() == body.name.lower() and p["id"] != pensioner_id for p in data["pensioners"]):
        raise HTTPException(409, "Another pensioner already has this name.")
    has_online = pensioner_id in db.lookup_ids(acc["workspace_id"])
    if body.date_of_birth and not body.ppo_number:
        return JSONResponse({"detail": "PPO number: please type the full PPO number again, together with the date of birth.",
                             "fields": {"ppo_number": "Needed together with the date of birth for the family status check."}, "code": "invalid"}, status_code=422)
    if body.ppo_number and has_online and not body.date_of_birth:
        return JSONResponse({"detail": "Date of birth: please type it again, so the family can keep checking their status with the new PPO number.",
                             "fields": {"date_of_birth": "Needed together with the new PPO number."}, "code": "invalid"}, status_code=422)
    pensioner = for_n8n(body)
    pensioner["ppo_last4"] = pensioner["ppo_last4"] or cur.get("ppo_last4") or ""
    pensioner["bank_account_last4"] = pensioner["bank_account_last4"] or cur.get("bank_account_last4") or ""
    status, res = await _n8n(request, "POST", "ADMIN", {"action": "update", "dataset": acc["workspace"]["key"], "id": pensioner_id,
                                                       "old_name": cur["name"], "pensioner": pensioner})
    if status != 200 or not res.get("ok"):
        raise HTTPException(502, "n8n could not save the changes.")
    if body.date_of_birth and body.ppo_number:
        db.set_lookup(acc["workspace_id"], pensioner_id, _fingerprint(body.ppo_number, body.date_of_birth))
    db.audit(acc["workspace_id"], acc["email"], "pensioner_edited", body.name)
    return {"ok": True, "message": "Changes saved."}


@app.delete("/api/pensioners/{pensioner_id}")
async def delete_pensioner(pensioner_id: int, request: Request, acc: dict = Depends(office_only)):
    data = await _overview(request, acc)
    cur = _find(data, pensioner_id)
    status, res = await _n8n(request, "POST", "ADMIN", {"action": "delete", "dataset": acc["workspace"]["key"], "id": pensioner_id, "old_name": cur["name"]})
    if status != 200 or not res.get("ok"):
        raise HTTPException(502, "n8n could not delete the pensioner.")
    db.remove_lookup(acc["workspace_id"], pensioner_id)
    db.audit(acc["workspace_id"], acc["email"], "pensioner_deleted", cur["name"])
    return {"ok": True, "message": f"{cur['name']} and all their records were deleted."}


class CheckIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@app.post("/api/pensioners/check")
async def check_pensioner(body: CheckIn, request: Request, acc: dict = Depends(signed_in)):
    status, data = await _n8n(request, "POST", "CHECK", {"name": body.name, "dataset": acc["workspace"]["key"]})
    if status != 200 or not isinstance(data, dict):
        raise HTTPException(502, "n8n could not run the check.")
    if isinstance(data.get("pensioner"), dict):
        data["pensioner"].pop("family_email", None)
    return data


class RecordIn(BaseModel):
    id: int
    pramaan_id: str = Field(pattern=PRAMAAN_RE.pattern)


@app.post("/api/pensioners/record-certificate")
async def record_certificate(body: RecordIn, request: Request, acc: dict = Depends(signed_in)):
    p = _find(await _overview(request, acc), body.id)
    status, data = await _n8n(request, "POST", "RECORD", {"id": p["id"], "name": p["name"], "pramaan_id": body.pramaan_id.strip(),
                                                         "recorded_by": acc["role"]})
    if status == 200 and data.get("ok"):
        db.audit(acc["workspace_id"], acc["email"], "life_certificate_recorded", p["name"])
        return data
    if status == 400:
        return JSONResponse({"detail": data.get("message") or "Not recorded.", "code": data.get("code"), "verified_until": data.get("verified_until")}, status_code=400)
    raise HTTPException(502, "n8n could not record the certificate.")


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject", "mark_sent", "mark_resolved"]


@app.post("/api/letters/{letter_id}/decision")
async def decide_letter(letter_id: int, body: DecisionIn, request: Request, acc: dict = Depends(signed_in)):
    data = await _overview(request, acc)
    if not any(g["id"] == letter_id for g in data["letters"]):
        raise HTTPException(404, "This letter was not found in your workspace.")
    status, res = await _n8n(request, "POST", "DECISION", {"id": letter_id, "decision": body.decision})
    if status != 200 or not res.get("ok"):
        raise HTTPException(400 if status == 400 else 502, res.get("message") or "The decision was not saved.")
    db.audit(acc["workspace_id"], acc["email"], "letter_" + body.decision, res.get("name", ""))
    return res


@app.post("/api/letters/draft-now")
async def draft_now(request: Request, acc: dict = Depends(consented)):
    before = len((await _overview(request, acc))["letters"])
    status, _ = await _n8n(request, "POST", "DRAFT", {"dataset": acc["workspace"]["key"]}, timeout=300)
    if status != 200:
        raise HTTPException(502, "n8n could not draft the letters.")
    after = len((await _overview(request, acc))["letters"])
    db.audit(acc["workspace_id"], acc["email"], "letters_drafted", str(after - before))
    n = after - before
    return {"ok": True, "drafted": n, "message": f"Claude drafted {n} new letter(s)." if n else "No new problems to write about."}


# ---------------------------------------------------------------- family status check (no account)


class StatusLookupIn(BaseModel):
    ppo_number: str = Field(max_length=40)
    date_of_birth: str = Field(max_length=20)


def _client(request: Request) -> str:
    """The visitor's address, for the "5 wrong tries" limit. Behind Render's proxy every request comes from the
    proxy, so there the LAST X-Forwarded-For entry (added by Render itself, not by the visitor) is used."""
    if os.getenv("RENDER", "").lower() == "true":
        forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if forwarded:
            return forwarded[-1]
    return request.client.host if request.client else "unknown"


def _wait_text(seconds: float) -> str:
    minutes = max(1, int((seconds + 59) // 60))
    return f"Too many wrong tries. Please wait {minutes} minute{'s' if minutes != 1 else ''} and try again."


def _status_token(workspace_id: int, pensioner_id: int) -> str:
    payload = _b64(json.dumps({"kind": "status", "w": workspace_id, "p": pensioner_id, "exp": int(time.time()) + STATUS_SECONDS}).encode())
    return f"{payload}.{_b64(hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).digest())}"


def _read_status(request: Request) -> dict | None:
    token = request.cookies.get(STATUS_COOKIE)
    if not token or "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _b64(hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).digest())):
        return None
    try:
        data = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if data.get("kind") != "status" or data.get("exp", 0) < time.time():
        return None
    return data


@app.post("/api/status/lookup")
async def status_lookup(body: StatusLookupIn, request: Request, response: Response):
    client = _client(request)
    locked = db.lookup_locked(client)
    if locked:
        return JSONResponse({"detail": _wait_text(locked), "code": "locked", "wait_seconds": int(locked)}, status_code=429)
    ppo = digits(body.ppo_number)
    dob = parse_date(body.date_of_birth or "")
    if not (6 <= len(ppo) <= 20) or not dob:  # a typing mistake: not counted as a wrong try
        fields = {}
        if not (6 <= len(ppo) <= 20):
            fields["ppo_number"] = "Type the full PPO number (6 to 20 digits)."
        if not dob:
            fields["date_of_birth"] = "Choose the date of birth."
        return JSONResponse({"detail": "Please check what you typed.", "fields": fields, "code": "invalid"}, status_code=422)
    found = db.find_lookup(_fingerprint(ppo, dob.isoformat()))
    if not found:
        left, wait = db.lookup_failed(client)
        if wait:
            return JSONResponse({"detail": _wait_text(wait), "code": "locked", "wait_seconds": int(wait)}, status_code=429)
        return JSONResponse({"detail": "We could not find a pensioner with this PPO number and date of birth. Please check both and try again, "
                             "or ask your pension office to add the date of birth.", "code": "not_found", "attempts_left": left}, status_code=404)
    db.lookup_ok(client)
    hit = found[0]
    db.audit(hit["workspace_id"], None, "family_status_checked", f"pensioner #{hit['pensioner_id']}")
    response.set_cookie(STATUS_COOKIE, _status_token(hit["workspace_id"], hit["pensioner_id"]), max_age=STATUS_SECONDS,
                        httponly=True, samesite="strict", secure=SECURE_COOKIES, path="/")
    return {"ok": True}


def _public_letter(g: dict) -> dict:
    keep = ("id", "status", "timeline", "amount_short", "bank", "issue_type", "problem_summary", "letter", "created_at")
    return {k: g.get(k) for k in keep}


@app.get("/api/status")
async def status_data(request: Request):
    s = _read_status(request)
    if not s:
        raise HTTPException(401, "Please enter the PPO number and date of birth again.")
    ws = db.get_workspace(int(s["w"]))
    if not ws:
        raise HTTPException(404, "This record is no longer available. Please contact your pension office.")
    data = await _overview_key(request, ws["key"])
    p = next((x for x in data["pensioners"] if x.get("id") == s["p"]), None)
    if not p:
        raise HTTPException(404, "This record is no longer available. Please contact your pension office.")
    letters = [_public_letter(g) for g in data["letters"] if g.get("name") == p["name"]]
    letters.sort(key=lambda g: g.get("id") or 0, reverse=True)
    # PRIVACY: whitelist only what the family needs. No emails, no account numbers, no consent details.
    pensioner = {k: p.get(k) for k in ("name", "age", "bank", "language", "ppo_last4", "life_certificate", "payments")}
    return {"generated_at": data["generated_at"], "deadline_iso": data.get("deadline_iso"), "days_left": data.get("days_left"),
            "settings": data.get("settings"), "office": ws["name"], "pensioner": pensioner, "letters": letters,
            "expires_in": max(0, int(s["exp"] - time.time()))}


@app.post("/api/status/leave")
def status_leave(response: Response):
    response.delete_cookie(STATUS_COOKIE, path="/")
    return {"ok": True}


# ---------------------------------------------------------------- settings


@app.get("/api/settings")
async def get_settings(request: Request, acc: dict = Depends(signed_in)):
    w = await _workspace_n8n(request, acc["workspace"])
    return {"name": acc["workspace"]["name"], "email": acc["email"], "role": acc["role"], "details": acc["workspace"]["details"],
            "consent_at": acc["workspace"]["consent_at"], "da_old": w.get("da_old", 55), "da_new": w.get("da_new", 58),
            "da_new_from": w.get("da_new_from", "2026-07"), "activity": db.recent_audit(acc["workspace_id"])}


class SettingsIn(BaseModel):
    da_old: float = Field(ge=0, le=300)
    da_new: float = Field(ge=0, le=300)
    da_new_from: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")


@app.put("/api/settings")
async def put_settings(body: SettingsIn, request: Request, acc: dict = Depends(signed_in)):
    await _sync_workspace(request, acc["workspace"], acc["email"], body.model_dump())
    db.audit(acc["workspace_id"], acc["email"], "da_rates_changed", json.dumps(body.model_dump()))
    return {"ok": True}


# ---------------------------------------------------------------- pages


def _page(name: str) -> FileResponse:
    return FileResponse(FRONTEND / name, media_type="text/html")


@app.get("/healthz")
def healthz():
    """For the hosting platform's health check: answers fast, without calling n8n."""
    return {"ok": True}


@app.get("/")
def landing():
    return _page("index.html")


@app.get("/signup")
def signup_page(request: Request):
    return RedirectResponse("/dashboard", 303) if current(request) else _page("signup.html")


@app.get("/login")
def login_page(request: Request):
    return RedirectResponse("/dashboard", 303) if current(request) else _page("login.html")


@app.get("/onboarding")
def onboarding_page(request: Request):
    acc = current(request)
    if not acc:
        return RedirectResponse("/login", 303)
    return _page("onboarding.html")


def _app_page(request: Request, office: str, family: str | None = None):
    acc = current(request)
    if not acc:
        return RedirectResponse("/login", 303)
    if not acc["workspace"]["onboarding_done"]:
        return RedirectResponse("/onboarding", 303)
    return _page(family if (family and acc["role"] == "family") else office)


@app.get("/dashboard")
def dashboard_page(request: Request):
    return _app_page(request, "office.html")


@app.get("/status")
def status_page(request: Request):
    return _page("status.html") if _read_status(request) else RedirectResponse("/#check", 303)


@app.get("/uploads")
def uploads_page(request: Request):
    return _app_page(request, "uploads.html")


@app.get("/settings")
def settings_page(request: Request):
    return _app_page(request, "settings.html")


app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")
