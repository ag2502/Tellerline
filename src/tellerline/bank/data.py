"""SQLite storage and deterministic synthetic data for the mock bank.

Everything here is invented. Amounts are stored in cents to avoid floating-point money.
"""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    customer_number TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    kind TEXT NOT NULL CHECK (kind IN ('current', 'savings')),
    iban TEXT UNIQUE NOT NULL,
    balance_cents INTEGER NOT NULL,
    available_cents INTEGER NOT NULL,
    UNIQUE (customer_id, kind)
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    last_four TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    freeze_reason TEXT,
    replacement_ordered_on TEXT,
    UNIQUE (customer_id, last_four)
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    posted_on TEXT NOT NULL,
    merchant TEXT NOT NULL,
    amount_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS disputes (
    id INTEGER PRIMARY KEY,
    reference TEXT UNIQUE NOT NULL,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    merchant TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    transaction_date TEXT NOT NULL,
    opened_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS handoffs (
    id INTEGER PRIMARY KEY,
    customer_id TEXT REFERENCES customers(id),
    reason TEXT,
    created_on TEXT NOT NULL
);
"""

BANK_CODE = "TLBK"

# Callers used throughout the benchmarks and the demo sheet, with fixed details.
KNOWN_CUSTOMERS = [
    ("45127890", "Aoife", "Byrne", "1991-03-03", ["4217", "0093"]),
    ("30118842", "Cian", "Murphy", "1985-07-14", ["5561"]),
    ("77451102", "Niamh", "Kelly", "1996-02-29", ["7780", "1188"]),
    ("61023397", "Seán", "O'Brien", "1978-11-21", ["6604", "3317"]),
    ("22904718", "Róisín", "Walsh", "2001-04-01", ["2291", "8850"]),
    ("58331026", "Declan", "Ryan", "1964-06-09", ["5092", "7701"]),
]
_FIRST = [
    "Ciara",
    "Oisín",
    "Emma",
    "Jack",
    "Saoirse",
    "Liam",
    "Grace",
    "Darragh",
    "Aisling",
    "Conor",
]
_LAST = ["Doyle", "McCarthy", "Gallagher", "Kennedy", "Lynch", "Quinn", "Nolan", "Farrell"]
_MERCHANTS = [
    ("Tesco Rathmines", -4217, -1250),
    ("Dublin Bus", -200, -300),
    ("Centra", -350, -1899),
    ("Aldi", -2550, -8740),
    ("Luas", -210, -210),
    ("Electric Ireland", -8900, -14500),
    ("Bewley's Café", -420, -980),
    ("Penneys", -1500, -6000),
    ("Irish Rail", -1290, -3450),
    ("Netflix", -1399, -1399),
]


def iban(account_number: str, sort_code: str = "930115") -> str:
    """A valid-format Irish IBAN (ISO 13616 mod-97 check digits) for a synthetic account."""
    bban = f"{BANK_CODE}{sort_code}{account_number}"
    rearranged = bban + "IE00"
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    check = 98 - int(digits) % 97
    return f"IE{check:02d}{bban}"


def iban_is_valid(value: str) -> bool:
    rearranged = value[4:] + value[:4]
    return int("".join(str(int(ch, 36)) for ch in rearranged)) % 97 == 1


def connect(path: Path | str) -> sqlite3.Connection:
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def seed(connection: sqlite3.Connection, today: date, extra_customers: int = 20) -> None:
    """Create the schema and a deterministic set of customers, accounts, cards and payments."""
    rng = random.Random(2026)
    connection.executescript(SCHEMA)
    if connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]:
        return

    customers = list(KNOWN_CUSTOMERS)
    for _ in range(extra_customers):
        number = f"{rng.randrange(10_000_000, 99_999_999)}"
        dob = date(rng.randrange(1950, 2005), rng.randrange(1, 13), rng.randrange(1, 29))
        cards = [f"{rng.randrange(0, 10_000):04d}"]
        customers.append((number, rng.choice(_FIRST), rng.choice(_LAST), dob.isoformat(), cards))

    for index, (number, first, last, dob, cards) in enumerate(customers):
        customer_id = f"cus_{index + 1:04d}"
        connection.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?)", (customer_id, number, first, last, dob)
        )
        for kind in ("current", "savings"):
            balance = (
                rng.randrange(5_000, 900_000) if kind == "current" else rng.randrange(0, 4_000_000)
            )
            held = rng.randrange(0, 12_000) if kind == "current" else 0
            if number == "45127890" and kind == "current":
                balance, held = 125_040, 7_000  # €1,250.40, as used in the benchmarks
            account_number = f"{index + 1:04d}{1 if kind == 'current' else 2:04d}"
            cursor = connection.execute(
                "INSERT INTO accounts (customer_id, kind, iban, balance_cents, available_cents) "
                "VALUES (?, ?, ?, ?, ?)",
                (customer_id, kind, iban(account_number), balance, balance - held),
            )
            _add_transactions(connection, rng, cursor.lastrowid, kind, today)
        for last_four in cards:
            connection.execute(
                "INSERT INTO cards (customer_id, last_four) VALUES (?, ?)", (customer_id, last_four)
            )
    connection.commit()


def _add_transactions(connection, rng: random.Random, account_id: int, kind: str, today: date):
    rows = []
    if kind == "current":
        for back in range(1, 25):
            if rng.random() < 0.6:
                merchant, low, high = rng.choice(_MERCHANTS)
                amount = rng.randint(min(low, high), max(low, high))
                rows.append(((today - timedelta(days=back)).isoformat(), merchant, amount))
        rows.append(((today - timedelta(days=3)).isoformat(), "Salary, Acme Ltd", 265_000))
    else:
        rows.append(
            ((today - timedelta(days=10)).isoformat(), "Transfer from current account", 20_000)
        )
        rows.append(((today - timedelta(days=40)).isoformat(), "Interest", rng.randrange(100, 900)))
    connection.executemany(
        "INSERT INTO transactions (account_id, posted_on, merchant, amount_cents) "
        "VALUES (?, ?, ?, ?)",
        [(account_id, *row) for row in rows],
    )
