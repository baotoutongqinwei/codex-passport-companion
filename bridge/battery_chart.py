"""Read local battery history and aggregate measured samples without interpolation."""
import csv
from datetime import datetime
import fcntl
from pathlib import Path

from battery_history import FIELDS


def read_history(path, now):
    cards, seen = {}, set()
    try:
        stream = Path(path).open(newline="")
    except FileNotFoundError:
        return cards
    with stream:
        # An import may be appending: retry later instead of reading half a row.
        fcntl.flock(stream.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("电量 CSV 格式不匹配")
        for row in reader:
            identity = row.get("card_serial")
            if not identity:
                continue
            card = cards.setdefault(identity, {"samples": [], "unsynced": 0, "invalid": 0})
            try:
                key = (identity, int(row["log_id"]), int(row["sequence"]))
                if key in seen:
                    continue
                seen.add(key)
                if not row["recorded_utc"]:
                    card["unsynced"] += 1
                    continue
                stamp = datetime.fromisoformat(row["recorded_utc"])
                if stamp.tzinfo is None:
                    raise ValueError("Timezone missing")
                at = stamp.timestamp()
                percent, voltage = int(row["battery_pct"]), int(row["battery_mv"])
                if not 0 <= percent <= 100 or not (voltage == -1 or 2500 <= voltage <= 5500):
                    raise ValueError("Invalid gauge value")
                if at > now:
                    raise ValueError("Future timestamp")
                if at >= now - 7*86400:
                    card["samples"].append({"at": at, "percent": percent, "voltage": voltage})
            except (ValueError, TypeError, KeyError, OverflowError):
                card["invalid"] += 1
    for card in cards.values():
        card["samples"].sort(key=lambda row: row["at"])
    return cards


def chart_data(samples, now, days=1):
    """Each bar is the last actual reading in its interval; empty stays empty."""
    if days not in (1, 7):
        raise ValueError("Unsupported time range")
    interval = 900 if days == 1 else 7200
    start = now-days*86400
    bins = [None] * (days*86400//interval)
    for sample in sorted(samples, key=lambda row: row["at"]):
        if start <= sample["at"] <= now:
            index = min(len(bins)-1, int((sample["at"]-start)//interval))
            bins[index] = sample
    available = [row for row in bins if row is not None]
    return {"start": start, "end": now, "interval": interval, "bins": bins,
            "latest": available[-1] if available else None,
            "minimum": min((row["percent"] for row in samples
                            if start <= row["at"] <= now), default=None)}
