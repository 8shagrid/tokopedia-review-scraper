import json
import sys
from collections import Counter
from typing import Dict, List

from scrape_tokped_reviews import (
    get_shop_id,
    has_text_review,
    iter_reviews,
    normalize_rows,
    parse_args,
    write_csv,
    write_json,
)
import requests


TARGET_TOTAL = 1500
STORE_URL = "https://www.tokopedia.com/prior-bags/review"


def collect_all_reviews_for_rating(
    session: requests.Session, shop_id: str, rating: int, page_size: int
) -> List[Dict]:
    results: List[Dict] = []
    seen_ids = set()

    for item in iter_reviews(
        session,
        shop_id,
        limit_rows=100000,
        page_size=page_size,
        filter_by=f"rating={rating}",
    ):
        review_id = item.get("id")
        if review_id in seen_ids:
            continue
        seen_ids.add(review_id)

        if not has_text_review(item):
            continue

        results.append(item)

    return results


def main() -> int:
    args = parse_args()
    session = requests.Session()

    try:
        shop_id = get_shop_id(session, args.url or STORE_URL)

        collected: List[Dict] = []
        lower_star_counts: Dict[int, int] = {}

        for rating in [4, 3, 2, 1]:
            items = collect_all_reviews_for_rating(session, shop_id, rating, args.page_size)
            lower_star_counts[rating] = len(items)
            collected.extend(items)

        lower_total = sum(lower_star_counts.values())
        if lower_total > TARGET_TOTAL:
            raise RuntimeError(
                f"Total review bintang 1-4 dengan teks adalah {lower_total}, melebihi target {TARGET_TOTAL}."
            )

        quota_5_star = TARGET_TOTAL - lower_total
        five_star_items: List[Dict] = []
        if quota_5_star > 0:
            for item in iter_reviews(
                session,
                shop_id,
                limit_rows=quota_5_star * 5,
                page_size=args.page_size,
                filter_by="rating=5",
            ):
                if not has_text_review(item):
                    continue
                five_star_items.append(item)
                if len(five_star_items) >= quota_5_star:
                    break

        if len(five_star_items) < quota_5_star:
            raise RuntimeError(
                f"Review bintang 5 dengan teks hanya {len(five_star_items)}, kurang dari kebutuhan {quota_5_star}."
            )

        all_items = five_star_items + collected
        rows = normalize_rows(session, all_items)

        if args.format == "csv":
            write_csv(args.output, rows)
        else:
            write_json(args.output, rows)

        summary = {
            "shop_id": shop_id,
            "target_total": TARGET_TOTAL,
            "lower_star_counts": lower_star_counts,
            "quota_5_star": quota_5_star,
            "final_counts": dict(sorted(Counter(row["star_rating"] for row in rows).items(), reverse=True)),
            "rows": len(rows),
            "output": args.output,
        }
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
