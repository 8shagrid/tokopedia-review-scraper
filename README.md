# Tokopedia Review Scraper

Script Python untuk mengambil review toko Tokopedia dan menyimpan hasilnya ke `JSON` atau `CSV`.

Script yang tersedia:
- `scrape_tokped_reviews.py`
  Untuk kasus umum:
  - ambil review terbaru
  - skip review tanpa teks
  - kuota per rating, mis. `5:500,4:300,3:300,2:200,1:200`
- `scrape_tokped_reviews_prior_bags.py`
  Untuk kasus khusus `prior-bags`:
  - ambil semua review `1-4 star` yang punya teks
  - isi sisanya dengan `5 star` sampai total `1500`
- `convert_relative_dates.py`
  Untuk menambahkan field `tanggal_real` dari field `tanggal` relatif.

## Requirement

- Python `3.10+`
- `pip`

Install dependency:

```bash
pip install -r requirements.txt
```

## Cara Pakai

### 1. Ambil review terbaru biasa

Contoh ambil `30` review terbaru:

```bash
python scrape_tokped_reviews.py --url https://www.tokopedia.com/mossdoom/review --limit 30 --format json --output tokped_reviews_latest_30.json
```

Kalau mau skip review tanpa teks:

```bash
python scrape_tokped_reviews.py --url https://www.tokopedia.com/mossdoom/review --limit 1500 --page-size 50 --skip-empty-text --format json --output tokped_reviews_latest_1500_with_text.json
```

### 2. Ambil review dengan kuota per rating

Contoh:
- `5 star = 500`
- `4 star = 300`
- `3 star = 300`
- `2 star = 200`
- `1 star = 200`

```bash
python scrape_tokped_reviews.py --url https://www.tokopedia.com/mossdoom/review --page-size 50 --skip-empty-text --rating-quotas 5:500,4:300,3:300,2:200,1:200 --format json --output mossdoom_reviews_quota_1500_with_text.json
```

Contoh untuk toko lain:

```bash
python scrape_tokped_reviews.py --url https://www.tokopedia.com/les-catino/review --page-size 50 --skip-empty-text --rating-quotas 5:500,4:300,3:300,2:200,1:200 --format json --output les_catino_reviews_quota_1500_with_text.json
```

### 3. Kasus khusus prior-bags

Aturannya:
- `4 star = ambil semua`
- `3 star = ambil semua`
- `2 star = ambil semua`
- `1 star = ambil semua`
- `5 star = 1500 - jumlah review 1-4 star`

Jalankan:

```bash
python scrape_tokped_reviews_prior_bags.py --url https://www.tokopedia.com/prior-bags/review --page-size 50 --format json --output prior_bags_reviews_special_1500_with_text.json
```

### 4. Konversi tanggal relatif jadi tanggal riil

Script ini menambahkan field baru `tanggal_real` tanpa menghapus field `tanggal`.

Contoh:

```bash
python convert_relative_dates.py --base-date 2026-04-15 mossdoom_reviews_quota_1500_with_text.json les_catino_reviews_quota_1500_with_text.json prior_bags_reviews_special_1500_with_text.json
```

Output:
- `mossdoom_reviews_quota_1500_with_text_dated.json`
- `les_catino_reviews_quota_1500_with_text_dated.json`
- `prior_bags_reviews_special_1500_with_text_dated.json`

## Format Output

Field utama di file hasil scrape:
- `username`
- `text_review`
- `star_rating`
- `tanggal`
- `varian`
- `nama_produk`
- `harga`

Field tambahan dari script konversi tanggal:
- `tanggal_real`

## Contoh Nama Output

- `mossdoom_reviews_quota_1500_with_text.json`
- `les_catino_reviews_quota_1500_with_text.json`
- `prior_bags_reviews_special_1500_with_text.json`
- `mossdoom_reviews_quota_1500_with_text_dated.json`
- `les_catino_reviews_quota_1500_with_text_dated.json`
- `prior_bags_reviews_special_1500_with_text_dated.json`

## Catatan

- Nilai `tanggal` dari Tokopedia sumbernya relatif, mis. `Hari ini`, `1 minggu lalu`, `1 bulan lalu`.
- `tanggal_real` adalah hasil konversi berbasis `--base-date`.
- Untuk kasus `bulan lalu` dan `tahun lalu`, script membuat tanggal semi-random yang tetap konsisten untuk row yang sama.
- Dataset hasil scrape tidak disarankan untuk dipush ke repo publik. `.gitignore` di repo ini mengecualikan file output JSON.
