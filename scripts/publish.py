#!/usr/bin/env python3
"""
طرح‌های موجود در پوشه designs/ را روی pooshai.ir منتشر می‌کند.

ساختار مورد انتظار:
  designs/<category-slug>/<name>.png
  designs/<category-slug>/<name>.json      <- متادیتای همان طرح
  designs/<category-slug>/_category.json   <- (اختیاری) مشخصات دسته

متغیرهای محیطی:
  POOSHAI_TOKEN  – کلید API (از GitHub Secrets)
  MODE           – changed | all
  BEFORE_SHA     – کامیت قبلی برای git diff
"""

import base64
import json
import mimetypes
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

BASE = os.environ.get("POOSHAI_BASE", "https://pooshai.ir/api/v1")
TOKEN = os.environ.get("POOSHAI_TOKEN", "").strip()
MODE = os.environ.get("MODE", "changed")
BEFORE_SHA = os.environ.get("BEFORE_SHA", "")
ROOT = Path(__file__).resolve().parent.parent
DESIGNS = ROOT / "designs"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
MAX_BYTES = 12 * 1024 * 1024

if not TOKEN:
    sys.exit("POOSHAI_TOKEN تنظیم نشده است")

HEAD = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def call(method: str, path: str, payload=None, params=None):
    """یک درخواست با تلاش مجدد ساده."""
    last = None
    for attempt in range(3):
        try:
            res = requests.request(
                method, BASE + path, headers=HEAD, json=payload, params=params, timeout=90
            )
            body = res.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
            continue
        if body.get("ok"):
            return body.get("data")
        # خطای ورودی/احراز هویت را تکرار نمی‌کنیم
        if res.status_code in (400, 401):
            raise RuntimeError(f"{res.status_code} {path}: {body.get('error')}")
        last = RuntimeError(f"{res.status_code} {path}: {body.get('error')}")
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(str(last))


def upload_asset(image_path: Path) -> str:
    """عکس را آپلود می‌کند و url سایت را برمی‌گرداند."""
    raw = image_path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise RuntimeError(f"{image_path.name}: حجم بیشتر از ۱۲ مگابایت است")
    mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
    if image_path.suffix.lower() == ".svg":
        mime = "image/svg+xml"
    data = call("POST", "/assets", {"base64": base64.b64encode(raw).decode(), "mime": mime})
    return data["url"]


def get_categories() -> list:
    """لیست دسته‌ها را از API می‌گیرد؛ شکل‌های رایج پاسخ را هندل می‌کند."""
    data = call("GET", "/categories")
    if data is None:
        return []
    if isinstance(data, dict):
        # پاسخ ممکن است داخل کلیدی مثل items پیچیده شده باشد
        for key in ("items", "categories", "results", "data"):
            if isinstance(data.get(key), list):
                return data[key]
        # یا نگاشت slug → دسته باشد
        if all(isinstance(v, dict) for v in data.values()):
            return list(data.values())
    elif isinstance(data, list) and all(isinstance(c, dict) for c in data):
        return data
    # شکل ناشناخته: با چاپ پاسخ واقعی خطا بده تا دیباگ دقیق شود
    raise RuntimeError(
        "شکل غیرمنتظره پاسخ /categories: "
        + json.dumps(data, ensure_ascii=False)[:500]
    )


def ensure_category(slug: str, meta: dict) -> None:
    """دسته را می‌سازد یا دست نمی‌زند اگر از قبل هست."""
    existing = {c["slug"]: c for c in get_categories()}
    if slug in existing and not meta.get("forceUpdate"):
        return
    payload = {"name": meta.get("name", slug), "slug": slug}
    for key in ("tagline", "introText", "seoTitle", "seoDescription", "sortOrder", "isActive"):
        if key in meta:
            payload[key] = meta[key]
    if slug in existing:
        payload["id"] = existing[slug]["id"]
    call("POST", "/categories", payload)
    print(f"  ✓ دسته {slug}")


def rel(path: Path) -> str:
    """مسیر نسبی فایل نسبت به ریشه‌ی مخزن با جداکننده‌ی یونیکس."""
    return path.relative_to(ROOT).as_posix()


def changed_files() -> set | None:
    """فایل‌های تغییرکرده در designs/ (مسیر نسبی)؛ None یعنی نامشخص — همه منتشر شوند."""
    base = BEFORE_SHA if BEFORE_SHA and not BEFORE_SHA.startswith("0000") else "HEAD~1"
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", base, "HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        print(f"⚠ git diff ناموفق بود ({exc.stderr.strip()}) — همه‌ی طرح‌ها بررسی می‌شوند", file=sys.stderr)
        return None
    return {line.replace("\\", "/") for line in out.splitlines() if line.startswith("designs/")}


def main() -> int:
    if not DESIGNS.exists():
        print("پوشه designs/ وجود ندارد")
        return 0

    # changed == None یعنی همه منتشر شوند (حالت all یا وقتی diff در دسترس نیست)
    changed = None if MODE == "all" else changed_files()
    published, skipped, failed = 0, 0, 0

    for category_dir in sorted(p for p in DESIGNS.iterdir() if p.is_dir()):
        slug = category_dir.name
        cat_file = category_dir / "_category.json"
        cat_meta = json.loads(cat_file.read_text("utf-8")) if cat_file.exists() else {}
        images = sorted(p for p in category_dir.iterdir() if p.suffix.lower() in IMAGE_EXT)
        if not images:
            continue

        targets = [p for p in images if changed is None or rel(p) in changed]
        if not targets:
            skipped += len(images)
            continue

        print(f"▶ دسته {slug} — {len(targets)} طرح")
        ensure_category(slug, cat_meta)

        for image in targets:
            meta_file = image.with_suffix(".json")
            meta = json.loads(meta_file.read_text("utf-8")) if meta_file.exists() else {}
            try:
                asset_url = meta.get("image")
                # آپلود دوباره فقط وقتی که خود فایل عکس تغییر کرده یا قبلاً آپلود نشده
                if not asset_url or MODE == "all" or rel(image) in (changed or set()):
                    asset_url = upload_asset(image)

                payload = {
                    "categorySlug": slug,
                    "title": meta.get("title", image.stem),
                    "image": asset_url,
                }
                for key in (
                    "slug", "description", "prompt", "tags", "imageAlt", "fabricColor",
                    "placementId", "styleId", "seoTitle", "seoDescription",
                    "isActive", "isFeatured", "sortOrder",
                ):
                    if key in meta:
                        payload[key] = meta[key]
                # ویرایش به جای ساخت دوباره
                if meta.get("id"):
                    payload["id"] = meta["id"]

                data = call("POST", "/designs", payload)

                # id و url را برای دفعه بعد در متادیتا ذخیره کن
                meta["id"] = data.get("id", meta.get("id"))
                meta["image"] = asset_url
                if data.get("slug"):
                    meta["slug"] = data["slug"]
                meta.setdefault("title", image.stem)
                meta_file.write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2) + "\n", "utf-8"
                )
                published += 1
                print(f"  ✓ {meta['title']} → {meta.get('slug', '')}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  ✗ {image.name}: {exc}", file=sys.stderr)

    print(f"\nمنتشرشده: {published} · ردشده: {skipped} · خطا: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
