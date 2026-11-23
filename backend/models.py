"""Shared validation rules for pensioners (used by the form, the family onboarding and the CSV upload)."""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

LANGUAGES = ["Hindi", "English", "Bengali", "Marathi", "Tamil", "Telugu", "Kannada", "Gujarati",
             "Malayalam", "Punjabi", "Odia", "Urdu", "Assamese"]
NAME_RE = re.compile(r"^[^\W\d_]+(?:[ .'-][^\W\d_]+)*\.?$", re.UNICODE)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
PRAMAAN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{5,29}$")


def digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def verified_until_for(submitted: date) -> date:
    """Verify once: submitted from 1 October -> valid until 30 Nov next year, earlier -> 30 Nov this year."""
    return date(submitted.year + 1 if submitted.month >= 10 else submitted.year, 11, 30)


def age_on(born: date, today: date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


class PensionerIn(BaseModel):
    name: str
    age: int = Field(ge=40, le=120)
    bank: str = Field(min_length=2, max_length=80)
    language: str
    family_email: str = ""
    ppo_number: str = ""           # only the last 4 digits are kept
    bank_account_number: str = ""  # only the last 4 digits are kept
    basic_pension: int = Field(ge=500, le=1_000_000)
    commuted_amount: int = Field(default=0, ge=0, le=1_000_000)
    date_of_birth: str = ""        # never stored: only used (with the PPO) for the family status check
    consent: bool = False

    @model_validator(mode="before")
    @classmethod
    def _age_from_dob(cls, data):
        """If a date of birth is given, the age is worked out from it."""
        if isinstance(data, dict):
            d = parse_date(str(data.get("date_of_birth") or ""))
            if d:
                data = {**data, "age": age_on(d, date.today())}
        return data

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            return ""
        d = parse_date(v)
        if not d or d >= date.today():
            raise ValueError("Use a date of birth like 15/08/1950 (DD/MM/YYYY).")
        if not 40 <= age_on(d, date.today()) <= 120:
            raise ValueError("The date of birth gives an age outside 40 to 120.")
        return d.isoformat()

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v or "").strip()
        if not (2 <= len(v) <= 80) or not NAME_RE.match(v):
            raise ValueError("Please enter the full name using letters only (2 to 80 characters).")
        return v

    @field_validator("bank")
    @classmethod
    def _bank(cls, v: str) -> str:
        return re.sub(r"\s+", " ", v).strip()

    @field_validator("language")
    @classmethod
    def _language(cls, v: str) -> str:
        v = (v or "").strip().title()
        if v not in LANGUAGES:
            raise ValueError("Please choose a language from the list (" + ", ".join(LANGUAGES[:4]) + "…).")
        return v

    @field_validator("family_email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = (v or "").strip()
        if v and (len(v) > 120 or not EMAIL_RE.match(v)):
            raise ValueError("Please enter a valid email address, or leave it empty.")
        return v.lower()

    @field_validator("ppo_number", "bank_account_number")
    @classmethod
    def _number(cls, v: str) -> str:
        v = (v or "").strip()
        if v and not re.fullmatch(r"[\d\s-]{4,30}", v):
            raise ValueError("Use digits only (spaces and dashes are fine).")
        d = digits(v)
        if v and not (6 <= len(d) <= 20):
            raise ValueError("This number should have 6 to 20 digits.")
        return d

    @model_validator(mode="after")
    def _commuted(self):
        if self.commuted_amount >= self.basic_pension:
            raise ValueError("The commuted amount must be less than the basic pension.")
        return self


def for_n8n(p: PensionerIn) -> dict:
    """PRIVACY: full PPO and bank account numbers never leave the backend. Only the last 4 digits are stored.
    The date of birth is never sent either (only a one-way fingerprint of PPO + date of birth is kept by the backend)."""
    return {
        "name": p.name, "age": p.age, "bank": p.bank, "language": p.language,
        "family_email": p.family_email, "basic_pension": p.basic_pension, "commuted_amount": p.commuted_amount,
        "ppo_last4": p.ppo_number[-4:] if p.ppo_number else "",
        "bank_account_last4": p.bank_account_number[-4:] if p.bank_account_number else "",
    }
