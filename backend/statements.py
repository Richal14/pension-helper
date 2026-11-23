"""Reads pension credits from an uploaded bank statement (CSV or PDF).

Privacy: the file is only read in memory and never saved. Nothing from it is kept except
month totals of pension credits. Long digit runs (account numbers) are masked in the preview.
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import date, datetime

MAX_BYTES = 5 * 1024 * 1024
PENSION_WORDS = re.compile(r"pension|pensn|\bpens\b|\bppo\b|पेंशन", re.I)
DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y",
                "%d-%b-%Y", "%d %b %Y", "%d-%b-%y", "%d %b %y", "%d %B %Y", "%b %d, %Y"]
DATE_IN_TEXT = re.compile(r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}[ -][A-Za-z]{3,9}[ -]\d{2,4})\b")
AMOUNT_IN_TEXT = re.compile(r"(?<![\d.])(?:₹|Rs\.?|INR)?\s?(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+\.\d{2})(?![\d])")


class StatementError(ValueError):
    pass


def mask_digits(text: str) -> str:
    """Hide account-like numbers: keep only the last 4 of any run of 5+ digits."""
    return re.sub(r"\d{5,}", lambda m: "•" * 4 + m.group(0)[-4:], text)


def _parse_date(s: str) -> date | None:
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(s: str) -> float | None:
    if s is None:
        return None
    s = str(s).strip()
    if not s or s in {"-", "--"}:
        return None
    negative = s.startswith("-") or s.startswith("(")
    s = re.sub(r"(?i)(₹|rs\.?|inr|cr\.?|dr\.?|[(),\s])", "", s).lstrip("-+")
    try:
        value = float(s)
    except ValueError:
        return None
    return -value if negative else value


def _find_col(headers: list[str], *names: str) -> int | None:
    low = [h.strip().lower() for h in headers]
    for name in names:
        for i, h in enumerate(low):
            if h == name:
                return i
    for name in names:
        for i, h in enumerate(low):
            if name in h:
                return i
    return None


def _from_csv(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise StatementError("The file is empty.")
    try:
        dialect = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(lines, dialect))
    # Banks often put a few lines of account details above the real header row.
    header_idx = next((i for i, r in enumerate(rows[:30])
                       if any("date" in c.lower() for c in r) and
                       any(k in " ".join(r).lower() for k in ("credit", "deposit", "amount"))), None)
    if header_idx is None:
        raise StatementError("Could not find the column headings (Date, Description, Credit) in the CSV.")
    headers = rows[header_idx]
    c_date = _find_col(headers, "txn date", "transaction date", "date", "value date")
    c_desc = _find_col(headers, "description", "narration", "particulars", "details", "remarks", "transaction details")
    c_credit = _find_col(headers, "credit", "deposit", "credit amount", "deposits", "cr amount")
    c_amount = _find_col(headers, "amount")
    c_type = _find_col(headers, "type", "cr/dr", "dr/cr", "txn type")
    if c_date is None or c_desc is None or (c_credit is None and c_amount is None):
        raise StatementError("The CSV needs Date, Description/Narration and Credit (or Amount) columns.")
    out = []
    for r in rows[header_idx + 1:]:
        if len(r) <= max(i for i in (c_date, c_desc, c_credit, c_amount, c_type) if i is not None):
            continue
        d = _parse_date(r[c_date])
        if not d:
            continue
        desc = r[c_desc].strip()
        credit = None
        if c_credit is not None:
            credit = _parse_amount(r[c_credit])
        elif c_amount is not None:
            amt = _parse_amount(r[c_amount])
            if amt is not None:
                is_credit = (c_type is not None and r[c_type].strip().lower().startswith("c")) or (c_type is None and amt > 0)
                credit = abs(amt) if is_credit else None
        out.append({"date": d, "description": desc, "credit": credit if credit and credit > 0 else None})
    return out


def _from_pdf(data: bytes) -> list[dict]:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise StatementError("This PDF is password-protected. Please download an unlocked statement.")
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:50])
    except StatementError:
        raise
    except Exception:
        raise StatementError("Could not read this PDF. Please upload the statement as CSV instead.")
    if not text.strip():
        raise StatementError("This PDF has no readable text (it may be a scanned image). Please upload a CSV statement.")
    out = []
    for line in text.splitlines():
        m = DATE_IN_TEXT.search(line)
        if not m:
            continue
        d = _parse_date(m.group(1))
        if not d:
            continue
        rest = line[m.end():]
        amounts = [_parse_amount(a) for a in AMOUNT_IN_TEXT.findall(rest)]
        amounts = [a for a in amounts if a is not None]
        credit = None
        if PENSION_WORDS.search(rest) and amounts:
            # Typical layout: ... Credit  Balance  -> the credit is the second-to-last amount.
            credit = amounts[-2] if len(amounts) >= 2 else amounts[0]
        out.append({"date": d, "description": rest.strip(), "credit": credit})
    return out


ACCOUNT_RE = re.compile(r"(?:account|a/c|acct)\.?\s*(?:number|no\.?|num|#)?\s*[:\-]?\s*,?\s*([0-9][0-9 \-]{4,26}[0-9])", re.I)
PPO_RE = re.compile(r"\bPPO\s*(?:no\.?|number|#)?\s*[:\-]?\s*([0-9]{6,20})", re.I)


def _text_of(name: str, data: bytes) -> str:
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader
            return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages[:50])
        except Exception:
            return ""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def identifiers(name: str, data: bytes) -> dict:
    """Only the LAST 4 digits of the account number and of any PPO numbers in the statement (used to match it to a pensioner)."""
    text = _text_of((name or "").lower(), data)
    acct = next((re.sub(r"\D", "", m.group(1)) for m in ACCOUNT_RE.finditer(text) if 6 <= len(re.sub(r"\D", "", m.group(1))) <= 20), None)
    ppos = sorted({m.group(1)[-4:] for m in PPO_RE.finditer(text)})
    return {"account_last4": acct[-4:] if acct else None, "ppo_last4s": ppos}


def read_statement(filename: str, data: bytes) -> dict:
    if len(data) > MAX_BYTES:
        raise StatementError("The file is larger than 5 MB.")
    name = (filename or "").lower()
    if not data:
        raise StatementError("The file is empty.")
    if name.endswith(".csv") or name.endswith(".txt"):
        rows = _from_csv(data)
    elif name.endswith(".pdf") or data[:5] == b"%PDF-":
        rows = _from_pdf(data)
    else:
        raise StatementError("Please upload a CSV or PDF bank statement.")
    if not rows:
        raise StatementError("No transactions were found in this statement.")

    credits = defaultdict(float)
    found = defaultdict(list)
    for r in rows:
        if r["credit"] and PENSION_WORDS.search(r["description"] or ""):
            key = r["date"].strftime("%Y-%m")
            credits[key] += r["credit"]
            found[key].append({"date": r["date"].isoformat(), "description": mask_digits(r["description"])[:80], "amount": round(r["credit"], 2)})

    first, last = min(r["date"] for r in rows), max(r["date"] for r in rows)
    months = []
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        key = f"{y:04d}-{m:02d}"
        whole_month = not ((y, m) == (first.year, first.month) and first.day > 3) and not ((y, m) == (last.year, last.month) and last.day < 28)
        if key in credits:
            months.append({"month": key, "amount_received": round(credits[key]), "credits": found[key], "covered": True})
        elif whole_month:
            # The statement covers this whole month but has no pension credit: that is a missing payment.
            months.append({"month": key, "amount_received": 0, "credits": [], "covered": True})
        m += 1
        if m == 13:
            y, m = y + 1, 1

    if not credits:
        raise StatementError("No pension credits were found. We look for lines that mention PENSION, PPO or पेंशन.")
    return {
        "period": {"from": first.isoformat(), "to": last.isoformat()},
        "transactions_read": len(rows),
        "months": months,
        **identifiers(filename, data),
    }
