#!/usr/bin/env python3
"""Card authenticity primitives for Sancai human interaction cards.

A card is a harness-owned object that binds a human decision to a stable
payload. The renderer stores it under .sancai/runs/<run>/L3-intent/decisions/cards/<card_id>.json;
a human-facing command later consumes it exactly once.

The MAC is optional: without SANCAI_SECRET (or SANCAI_CARD_SECRET) cards still
carry an integrity hash, but a compromised agent could recompute it. The MAC
raises the bar only when the agent cannot read the secret.
"""
import datetime
import hashlib
import hmac
import json
import math
import os

import sancai_paths as paths  # type: ignore

import re
import uuid

os.umask(0o077)

DWELL_SECONDS = {"T0": 0, "T1": 0, "T2": 3, "T3": 10, "T4": 60}

CARD_KINDS = {"intent", "approve", "out-of-scope", "ambiguous", "accept", "blocked"}

CARD_ID_RE = re.compile(r"^CARD-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

FINDING_FIELDS = (
    "id",
    "severity",
    "file",
    "line",
    "evidence",
    "fix",
    "summary",
    "suggested_fix",
    "source",
)


class CardError(Exception):
    """Raised when a card is invalid, stale, forged, or already consumed."""


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def card_secret():
    return os.environ.get("SANCAI_SECRET") or os.environ.get("SANCAI_CARD_SECRET") or None


def card_dir(root, run):
    return paths.cards_dir(root, run)


def card_path(root, run, card_id):
    return os.path.join(card_dir(root, run), card_id + ".json")


def _validate_card_id(card_id):
    if not isinstance(card_id, str) or not CARD_ID_RE.match(card_id) or ".." in card_id:
        raise CardError(f"invalid card id: {card_id!r}")


def _atomic_save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _signed_object(card):
    return {
        "card_id": card.get("card_id"),
        "run": card.get("run"),
        "kind": card.get("kind"),
        "tier": card.get("tier"),
        "payload": card.get("payload"),
        "options": card.get("options"),
        "created_at": card.get("created_at"),
    }


def _mac_for(card_hash):
    secret = card_secret()
    if not secret:
        return None
    return hmac.new(
        secret.encode("utf-8"), card_hash.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def make_card(root, run, kind, payload, options, tier="T2"):
    if kind not in CARD_KINDS:
        raise CardError(f"invalid card kind: {kind!r}")
    if tier not in DWELL_SECONDS:
        raise CardError(f"invalid card tier: {tier!r}")
    if (
        tier in ("T0", "T1")
        and os.environ.get("SANCAI_ALLOW_CARD_TIER_OVERRIDE") != "1"
    ):
        tier = "T2"
    if not card_secret():
        raise CardError(
            "SANCAI_SECRET or SANCAI_CARD_SECRET is required to issue a card"
        )
    if options is None:
        options = []

    card_id = "CARD-" + uuid.uuid4().hex[:12]
    created_at = now()
    signed = {
        "card_id": card_id,
        "run": run,
        "kind": kind,
        "tier": tier,
        "payload": payload,
        "options": options,
        "created_at": created_at,
    }
    card_hash = sha256_hex(canonical(signed))
    card_code = sha256_hex(card_hash)[:8]
    mac = _mac_for(card_hash)
    card = {
        "card_id": card_id,
        "run": run,
        "kind": kind,
        "tier": tier,
        "created_at": created_at,
        "payload": payload,
        "options": options,
        "card_hash": card_hash,
        "card_code": card_code,
        "mac": mac,
        "used_at": None,
    }
    _atomic_save(card_path(root, run, card_id), card)
    return card


def load_card(root, run, card_id):
    _validate_card_id(card_id)
    path = card_path(root, run, card_id)
    if not os.path.isfile(path):
        raise CardError(f"card not found: {card_id}")
    try:
        with open(path, encoding="utf-8") as f:
            card = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise CardError(f"cannot read card {card_id}: {exc}") from exc
    if not isinstance(card, dict):
        raise CardError(f"card {card_id} is not a JSON object")
    return card


def latest_card(root, run, kind=None):
    """Newest persisted card for a run, optionally filtered by kind."""
    directory = card_dir(root, run)
    if not os.path.isdir(directory):
        return None
    cards = []
    for name in os.listdir(directory):
        if not name.endswith(".json"):
            continue
        try:
            card = load_card(root, run, name[:-5])
        except CardError:
            continue
        if kind and card.get("kind") != kind:
            continue
        cards.append(card)
    return max(cards, key=lambda c: c.get("created_at", "")) if cards else None


def _format_path(path):
    return path or "payload"


def _subset_problems(expected, actual, path=""):
    problems = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            problems.append(f"{_format_path(path)}: expected object, got {type(actual).__name__}")
            return problems
        for key, value in expected.items():
            child = f"{path}.{key}" if path else key
            if key not in actual:
                problems.append(f"{child}: missing")
            else:
                problems.extend(_subset_problems(value, actual[key], child))
        return problems
    if isinstance(expected, list):
        if not isinstance(actual, list):
            problems.append(f"{_format_path(path)}: expected list, got {type(actual).__name__}")
            return problems
        if len(expected) != len(actual):
            problems.append(
                f"{_format_path(path)}: expected {len(expected)} items, got {len(actual)}"
            )
            return problems
        for i, (exp, act) in enumerate(zip(expected, actual)):
            problems.extend(_subset_problems(exp, act, f"{path}[{i}]"))
        return problems
    if expected != actual:
        problems.append(f"{_format_path(path)}: expected {expected!r}, got {actual!r}")
    return problems


def verify_card(card, expected_payload=None):
    """Return a list of problems; an empty list means the card is authentic.

    used_at is deliberately not a verification failure: consumption is checked
    by consume_card, so a human can still inspect a used card with `verify`.
    """
    problems = []
    if not isinstance(card, dict):
        return ["card is not a JSON object"]
    if not card_secret():
        return ["card secret is not set; refusing to verify an unsigned card"]

    if "kind" in card and card.get("kind") not in CARD_KINDS:
        problems.append(f"unknown kind: {card.get('kind')!r}")
    if "tier" in card and card.get("tier") not in DWELL_SECONDS:
        problems.append(f"unknown tier: {card.get('tier')!r}")

    recomputed_hash = sha256_hex(canonical(_signed_object(card)))
    if card.get("card_hash") != recomputed_hash:
        problems.append("card_hash mismatch: payload was altered")
    recomputed_code = sha256_hex(recomputed_hash)[:8]
    if card.get("card_code") != recomputed_code:
        problems.append("card_code mismatch")
    if card.get("card_id") and not CARD_ID_RE.match(str(card.get("card_id"))):
        problems.append(f"invalid card id: {card.get('card_id')!r}")

    mac = card.get("mac")
    if mac:
        expected_mac = _mac_for(recomputed_hash)
        if expected_mac is None:
            problems.append("card carries a mac but no SANCAI_SECRET/SANCAI_CARD_SECRET is set")
        elif not hmac.compare_digest(str(mac), expected_mac):
            problems.append("mac mismatch: card was not issued by this harness")

    if expected_payload is not None:
        if not isinstance(card.get("payload"), dict) and not isinstance(
            card.get("payload"), list
        ):
            problems.append("payload missing or not a container")
        else:
            problems.extend(_subset_problems(expected_payload, card.get("payload")))

    return problems


def _parse_ts(value):
    if not isinstance(value, str) or not value:
        raise CardError("card has no valid created_at timestamp")
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CardError(f"invalid timestamp {value!r}: {exc}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def card_age_seconds(card, now_dt=None):
    created = _parse_ts(card.get("created_at"))
    reference = now_dt or datetime.datetime.now(datetime.timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=datetime.timezone.utc)
    return (reference - created).total_seconds()


def consume_card(root, run, card_id, card_code=None, expected_payload=None):
    card = load_card(root, run, card_id)

    problems = verify_card(card, expected_payload)
    if problems:
        raise CardError("card verification failed: " + "; ".join(problems))

    if card_code is not None and card_code != card.get("card_code"):
        raise CardError("card_code mismatch: reply does not match this card")

    if card.get("used_at"):
        raise CardError(f"card already used at {card['used_at']}")

    tier = card.get("tier", "T2")
    dwell = DWELL_SECONDS.get(tier, 0)
    age = card_age_seconds(card)
    if age < dwell:
        remaining = dwell - age
        raise CardError(
            f"card is too fresh: tier {tier} requires {dwell}s dwell, "
            f"{math.ceil(remaining)}s remaining"
        )

    marker = card_path(root, run, card_id) + ".used"
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise CardError("card already used (consumption marker exists)")
    else:
        os.close(fd)

    card["used_at"] = now()
    _atomic_save(card_path(root, run, card_id), card)
    return card


def findings_hash(findings):
    """Hash the decision-relevant fields of every finding, order-independent."""
    rows = []
    for finding in findings or []:
        if isinstance(finding, dict):
            rows.append({k: finding.get(k) for k in FINDING_FIELDS})
        else:
            rows.append(finding)
    rows.sort(key=canonical)
    return "sha256:" + sha256_hex(canonical(rows))
