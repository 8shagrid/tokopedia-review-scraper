import argparse
import csv
import json
import math
import re
import sys
import time
from typing import Dict, Iterable, List

import requests


REVIEW_LIST_QUERY = """
query ReviewList($shopID:String!,$limit:Int!,$page:Int!,$filterBy:String,$sortBy:String){
  productrevGetShopReviewReadingList(
    shopID:$shopID,
    limit:$limit,
    page:$page,
    filterBy:$filterBy,
    sortBy:$sortBy
  ){
    list{
      id:reviewID
      product{
        productID
        productName
        productImageURL
        productPageURL
        productStatus
        isDeletedProduct
        productVariant{
          variantID
          variantName
        }
      }
      rating
      reviewTime
      reviewText
      reviewerID
      reviewerName
      avatar
      replyText
      replyTime
      attachments{
        attachmentID
        thumbnailURL
        fullsizeURL
      }
      videoAttachments{
        attachmentID
        videoUrl
      }
      state{
        isReportable
        isAnonymous
      }
      likeDislike{
        totalLike
        likeStatus
      }
      badRatingReasonFmt
    }
    hasNext
    shopName
    totalReviews
  }
}
""".strip()

HEADERS = {
    "accept": "*/*",
    "content-type": "application/json",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
}

SHOP_ID_PATTERNS = [
    re.compile(r'ShopPageGetHeaderLayout\(\{\\"shopID\\":\\"(\d+)\\"\}\)'),
    re.compile(r'productrevGetShopReviewReadingList\(\{[^}]*\\"shopID\\":\\"(\d+)\\"'),
    re.compile(r'"shopID":"(\d+)"'),
]

PRICE_PATTERNS = [
    re.compile(r'property="product:price:amount" content="(\d+)"'),
    re.compile(r'name="twitter:data1" content="(Rp[^"]+)"'),
]


def get_shop_id(session: requests.Session, review_url: str) -> str:
    response = session.get(review_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    html = response.text

    for pattern in SHOP_ID_PATTERNS:
        match = pattern.search(html)
        if match:
            return match.group(1)

    raise RuntimeError("Shop ID tidak ditemukan dari halaman review.")


def fetch_review_page(
    session: requests.Session, shop_id: str, page: int, page_size: int, filter_by: str = ""
) -> Dict:
    payload = {
        "operationName": "ReviewList",
        "query": REVIEW_LIST_QUERY,
        "variables": {
            "shopID": shop_id,
            "limit": page_size,
            "page": page,
            "filterBy": filter_by,
            "sortBy": "create_time desc",
        },
    }
    response = session.post(
        "https://gql.tokopedia.com/graphql/ReviewList",
        json=payload,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "data" not in payload or "productrevGetShopReviewReadingList" not in payload["data"]:
        raise RuntimeError(f"Respons review tidak valid: {payload}")
    return payload["data"]["productrevGetShopReviewReadingList"]


def format_rupiah(amount: str) -> str:
    try:
        value = int(amount)
    except (TypeError, ValueError):
        return amount or ""
    return f"Rp{value:,}".replace(",", ".")


def fetch_price(session: requests.Session, product_url: str) -> str:
    response = session.get(product_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    html = response.text

    match = PRICE_PATTERNS[0].search(html)
    if match:
        return format_rupiah(match.group(1))

    match = PRICE_PATTERNS[1].search(html)
    if match:
        return match.group(1)

    return ""


def iter_reviews(
    session: requests.Session,
    shop_id: str,
    limit_rows: int,
    page_size: int,
    filter_by: str = "",
) -> Iterable[Dict]:
    max_pages = max(math.ceil(limit_rows / page_size) * 5, 10)
    yielded = 0

    for page in range(1, max_pages + 1):
        data = fetch_review_page(
            session, shop_id, page=page, page_size=page_size, filter_by=filter_by
        )
        items = data.get("list") or []
        if not items:
            return

        for item in items:
            yield item
            yielded += 1
            if yielded >= limit_rows:
                return

        if not data.get("hasNext"):
            return

        time.sleep(0.5)


def normalize_rows(session: requests.Session, reviews: List[Dict]) -> List[Dict]:
    price_cache: Dict[str, str] = {}
    rows: List[Dict] = []

    for review in reviews:
        product = review.get("product") or {}
        product_url = product.get("productPageURL") or ""

        if product_url not in price_cache:
            price_cache[product_url] = fetch_price(session, product_url) if product_url else ""
            time.sleep(0.4)

        rows.append(
            {
                "username": review.get("reviewerName", ""),
                "text_review": (review.get("reviewText") or "").replace("\r\n", "\n").strip(),
                "star_rating": review.get("rating", ""),
                "tanggal": review.get("reviewTime", ""),
                "varian": ((product.get("productVariant") or {}).get("variantName") or "").strip(),
                "nama_produk": (product.get("productName") or "").strip(),
                "harga": price_cache.get(product_url, ""),
            }
        )

    return rows


def has_text_review(review: Dict) -> bool:
    text = review.get("reviewText")
    return bool(text and text.strip())


def has_variant(review: Dict) -> bool:
    product = review.get("product") or {}
    variant = (product.get("productVariant") or {}).get("variantName")
    return bool(variant and variant.strip())


def is_usable_review(review: Dict, skip_empty_text: bool) -> bool:
    if skip_empty_text and not has_text_review(review):
        return False
    if not has_variant(review):
        return False
    return True


def parse_rating_quotas(raw: str) -> Dict[int, int]:
    quotas: Dict[int, int] = {}
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Format quota tidak valid: {item}")
        rating_text, count_text = item.split(":", 1)
        rating = int(rating_text.strip())
        count = int(count_text.strip())
        if rating < 1 or rating > 5:
            raise ValueError(f"Rating harus 1-5, dapat: {rating}")
        if count < 0:
            raise ValueError(f"Quota tidak boleh negatif, dapat: {count}")
        quotas[rating] = count
    if not quotas:
        raise ValueError("Quota rating kosong.")
    return quotas


def write_csv(path: str, rows: List[Dict]) -> None:
    if not rows:
        raise RuntimeError("Tidak ada data untuk ditulis.")

    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: str, rows: List[Dict]) -> None:
    if not rows:
        raise RuntimeError("Tidak ada data untuk ditulis.")

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape review toko Tokopedia.")
    parser.add_argument(
        "--url",
        default="https://www.tokopedia.com/mossdoom/review",
        help="URL halaman review toko Tokopedia.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Jumlah review terbaru yang ingin diambil.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=10,
        help="Jumlah item per request ReviewList.",
    )
    parser.add_argument(
        "--output",
        default="tokped_reviews_latest_30.json",
        help="Path output file.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Format output.",
    )
    parser.add_argument(
        "--skip-empty-text",
        action="store_true",
        help="Lewati review yang tidak punya text review.",
    )
    parser.add_argument(
        "--rating-quotas",
        default="",
        help="Kuota per rating, format contoh: 5:500,4:300,3:300,2:200,1:200",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = requests.Session()

    try:
        shop_id = get_shop_id(session, args.url)
        review_items: List[Dict] = []
        target_limit = args.limit

        if args.rating_quotas:
            quotas = parse_rating_quotas(args.rating_quotas)
            target_limit = sum(quotas.values())
            for rating in sorted(quotas.keys(), reverse=True):
                needed = quotas[rating]
                if needed == 0:
                    continue

                collected_for_rating = 0
                for item in iter_reviews(
                    session,
                    shop_id,
                    needed * 5,
                    args.page_size,
                    filter_by=f"rating={rating}",
                ):
                    if not is_usable_review(item, args.skip_empty_text):
                        continue
                    review_items.append(item)
                    collected_for_rating += 1
                    if collected_for_rating >= needed:
                        break

                if collected_for_rating < needed:
                    raise RuntimeError(
                        f"Review rating {rating} yang memenuhi syarat hanya {collected_for_rating}, "
                        f"kurang dari target {needed}."
                    )
        else:
            for item in iter_reviews(session, shop_id, args.limit * 5, args.page_size):
                if not is_usable_review(item, args.skip_empty_text):
                    continue
                review_items.append(item)
                if len(review_items) >= target_limit:
                    break

        rows = normalize_rows(session, review_items[: target_limit])
        if args.format == "csv":
            write_csv(args.output, rows)
        else:
            write_json(args.output, rows)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"shop_id={shop_id}")
    print(f"rows={len(rows)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
