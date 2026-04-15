import argparse
import calendar
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List


DAY_RE = re.compile(r"^(\d+)\s+hari lalu$")
WEEK_RE = re.compile(r"^(\d+)\s+minggu lalu$")
MONTH_RE = re.compile(r"^(\d+)\s+bulan lalu$")
YEAR_RE = re.compile(r"^(\d+)\s+tahun lalu$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert relative Tokopedia dates to real dates.")
    parser.add_argument(
        "--base-date",
        default="2026-04-15",
        help="Base date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="JSON files to process.",
    )
    return parser.parse_args()


def stable_int(row: Dict, salt: str) -> int:
    seed = "|".join(
        [
            salt,
            str(row.get("username", "")),
            str(row.get("text_review", "")),
            str(row.get("star_rating", "")),
            str(row.get("nama_produk", "")),
            str(row.get("varian", "")),
            str(row.get("tanggal", "")),
        ]
    )
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def shift_months(base: date, months_back: int) -> date:
    year = base.year
    month = base.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def random_day_in_month(month_start: date, row: Dict, salt: str) -> date:
    days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
    day = (stable_int(row, salt) % days_in_month) + 1
    return date(month_start.year, month_start.month, day)


def random_date_between(start: date, end: date, row: Dict, salt: str) -> date:
    span = (end - start).days
    if span <= 0:
        return start
    offset = stable_int(row, salt) % (span + 1)
    return start + timedelta(days=offset)


def resolve_real_date(relative_text: str, base_date: date, row: Dict) -> date:
    value = (relative_text or "").strip()

    if not value:
        return base_date

    if re.match(r"^\d{2}/\d{2}/\d{4}$", value):
        return datetime.strptime(value, "%d/%m/%Y").date()

    if value.lower() == "hari ini":
        return base_date

    match = DAY_RE.match(value)
    if match:
        days_back = int(match.group(1))
        return base_date - timedelta(days=days_back)

    match = WEEK_RE.match(value)
    if match:
        weeks_back = int(match.group(1))
        start = base_date - timedelta(days=(weeks_back * 7 + 6))
        end = base_date - timedelta(days=weeks_back * 7)
        return random_date_between(start, end, row, f"week:{weeks_back}")

    match = MONTH_RE.match(value)
    if match:
        months_back = int(match.group(1))
        month_start = shift_months(base_date, months_back)
        return random_day_in_month(month_start, row, f"month:{months_back}")

    match = YEAR_RE.match(value)
    if match:
        years_back = int(match.group(1))
        start = date(base_date.year - years_back, 1, 1)
        end = date(base_date.year - years_back, 12, 31)
        return random_date_between(start, end, row, f"year:{years_back}")

    if value.lower() == "lebih dari 1 tahun lalu":
        start = date(base_date.year - 3, 1, 1)
        end = date(base_date.year - 2, 12, 31)
        return random_date_between(start, end, row, "older_than_1_year")

    return base_date


def convert_file(path: Path, base_date: date) -> Path:
    with path.open(encoding="utf-8") as handle:
        rows: List[Dict] = json.load(handle)

    for row in rows:
        real_date = resolve_real_date(row.get("tanggal", ""), base_date, row)
        row["tanggal_real"] = real_date.strftime("%d/%m/%Y")

    output_path = path.with_name(f"{path.stem}_dated.json")
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)

    return output_path


def main() -> int:
    args = parse_args()
    base_date = datetime.strptime(args.base_date, "%Y-%m-%d").date()

    for file_name in args.files:
        output_path = convert_file(Path(file_name), base_date)
        print(f"{file_name} -> {output_path.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
