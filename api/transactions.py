from __future__ import annotations

from datetime import datetime


def _parse_pickup(raw_value):
    value = str(raw_value or "").strip()
    if not value:
        return datetime.max
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.max


def normalize_transactions(payload):
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def enrich_reservation_queue(payload):
    transactions = normalize_transactions(payload)
    for tx in transactions:
        status = str(tx.get("status", "")).strip().lower()
        if status != "reserved":
            tx.pop("queue_position", None)
            tx.pop("queue_total", None)
            tx.pop("same_slot_conflict", None)
            continue

        book_no = str(tx.get("book_no", "")).strip()
        school_id = str(tx.get("school_id", "")).strip().lower()
        book_queue = sorted(
            [
                row
                for row in transactions
                if str(row.get("book_no", "")).strip() == book_no
                and str(row.get("status", "")).strip().lower() == "reserved"
            ],
            key=lambda row: _parse_pickup(row.get("pickup_schedule") or row.get("date")),
        )

        tx["queue_position"] = next(
            (
                index + 1
                for index, row in enumerate(book_queue)
                if str(row.get("school_id", "")).strip().lower() == school_id
            ),
            None,
        )
        tx["queue_total"] = len(book_queue)
        tx["same_slot_conflict"] = (
            sum(1 for row in book_queue if row.get("pickup_schedule") == tx.get("pickup_schedule"))
            > 1
        )
    return transactions

