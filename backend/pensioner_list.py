"""Reads and validates an uploaded pensioner list (CSV). All rows must be valid, or nothing is imported."""

from __future__ import annotations

import csv
import io
from datetime import date

from pydantic import ValidationError

from models import PRAMAAN_RE, PensionerIn, for_n8n, parse_date, verified_until_for

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000

# Column name in the template -> accepted spellings
COLUMNS = {
    "name": ["name", "full_name", "pensioner_name"],
    "age": ["age"],
    "date_of_birth": ["date_of_birth", "dob", "birth_date"],
    "bank": ["bank", "bank_name"],
    "language": ["language", "preferred_language"],
    "ppo_number": ["ppo_number", "ppo", "ppo_no"],
    "bank_account_number": ["bank_account_number", "account_number", "bank_account"],
    "basic_pension": ["basic_pension", "basic_pension_rs", "basic"],
    "commuted_amount": ["commuted_amount", "commutation"],
    "family_email": ["family_email", "email"],
    "jeevan_pramaan_id": ["jeevan_pramaan_id", "pramaan_id", "life_certificate_id"],
    "certificate_date": ["certificate_date", "life_certificate_date", "submitted_on"],
}
REQUIRED = ["name", "bank", "language", "ppo_number", "basic_pension"]  # plus age OR date_of_birth
TEMPLATE_HEADER = list(COLUMNS)
LABELS = {"name": "Name", "age": "Age", "date_of_birth": "Date of birth", "bank": "Bank", "language": "Language", "ppo_number": "PPO number",
          "bank_account_number": "Bank account number", "basic_pension": "Basic pension", "commuted_amount": "Commuted amount",
          "family_email": "Family email", "jeevan_pramaan_id": "Jeevan Pramaan ID", "certificate_date": "Certificate date"}


class ListError(ValueError):
    def __init__(self, message: str, errors: list[dict] | None = None):
        super().__init__(message)
        self.errors = errors or []


def template_csv() -> str:
    return ",".join(TEMPLATE_HEADER) + "\n"


def _norm(h: str) -> str:
    return h.strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace("â‚¹", "rs")


def read_list(filename: str, data: bytes, existing_names: set[str], consent_at: str, consent_by: str) -> list[dict]:
    if not (filename or "").lower().endswith(".csv"):
        raise ListError("Please upload the pensioner list as a .csv file (use the template).")
    if not data:
        raise ListError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ListError("The file is larger than 2 MB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ListError("The file has no pensioners. Add one row per pensioner under the heading row.")
    header = [_norm(h) for h in rows[0]]
    index = {}
    for key, names in COLUMNS.items():
        for i, h in enumerate(header):
            if h in names:
                index[key] = i
                break
    missing = [LABELS[k] for k in REQUIRED if k not in index]
    if "age" not in index and "date_of_birth" not in index:
        missing.insert(1, "Age (or Date of birth)")
    if missing:
        raise ListError("These columns are missing: " + ", ".join(missing) + ". Please use the template.")
    if len(rows) - 1 > MAX_ROWS:
        raise ListError(f"Please upload at most {MAX_ROWS} pensioners at a time.")

    errors, out, seen = [], [], set()
    today = date.today()
    for n, r in enumerate(rows[1:], start=2):
        cell = lambda k: (r[index[k]].strip() if k in index and index[k] < len(r) else "")
        raw = {k: cell(k) for k in COLUMNS}
        try:
            p = PensionerIn(
                name=raw["name"], age=raw["age"] or 0, date_of_birth=raw["date_of_birth"], bank=raw["bank"], language=raw["language"],
                family_email=raw["family_email"], ppo_number=raw["ppo_number"], bank_account_number=raw["bank_account_number"],
                basic_pension=(raw["basic_pension"].replace(",", "") or 0), commuted_amount=(raw["commuted_amount"].replace(",", "") or 0),
                consent=True)
        except ValidationError as e:
            for err in e.errors():
                field = str(err["loc"][0]) if err.get("loc") else ""
                msg = str(err.get("msg", "")).removeprefix("Value error, ")
                if err.get("type") in ("int_parsing", "int_from_float"):
                    msg = "Please enter a whole number."
                elif err.get("type") in ("greater_than_equal", "less_than_equal"):
                    msg = {"age": "Give an age between 40 and 120, or a date of birth.", "basic_pension": "Basic pension must be between â‚¹500 and â‚¹10,00,000."}.get(field, "This value is out of range.")
                if not field and "commuted" in msg.lower():
                    field = "commuted_amount"
                errors.append({"row": n, "field": LABELS.get(field, "Row"), "message": msg})
            continue
        if not p.ppo_number:
            errors.append({"row": n, "field": "PPO number", "message": "The PPO number is required."})
            continue
        key = p.name.lower()
        if key in seen:
            errors.append({"row": n, "field": "Name", "message": f"{p.name} appears twice in the file."})
            continue
        if key in existing_names:
            errors.append({"row": n, "field": "Name", "message": f"{p.name} is already in your pensioner list."})
            continue
        seen.add(key)
        item = for_n8n(p)
        item.update(consent_given_at=consent_at, consent_by=consent_by)
        if p.date_of_birth:  # kept only in memory to make the family status fingerprint; never sent to n8n
            item["_lookup"] = (p.ppo_number, p.date_of_birth)
        pid, pdate = raw["jeevan_pramaan_id"], raw["certificate_date"]
        if pid or pdate:
            d = parse_date(pdate) if pdate else None
            if not pid or not PRAMAAN_RE.match(pid):
                errors.append({"row": n, "field": "Jeevan Pramaan ID", "message": "Give the ID (6 to 30 letters or numbers) together with the certificate date, or leave both empty."})
                continue
            if not d or d > today:
                errors.append({"row": n, "field": "Certificate date", "message": "Use a past date like 05/11/2026 (DD/MM/YYYY), or leave both certificate columns empty."})
                continue
            item.update(pramaan_id=pid.upper(), lc_submitted_on=d.isoformat(), lc_verified_until=verified_until_for(d).isoformat())
        out.append(item)

    if errors:
        raise ListError(f"{len(errors)} problem(s) found. Nothing was imported. Please fix the file and upload it again.", errors[:50])
    return out
