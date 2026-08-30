# خط لوله‌ی انتشار طرح — GitHub ←→ pooshai.ir

عکس را تولید می‌کنی → در پوشه‌ی دسته push می‌کنی → GitHub Action خودکار عکس را آپلود و طرح را در سایت می‌سازد.

## ۱) ساختار مخزن

```
designs/
  cats/
    _category.json          # اختیاری — مشخصات دسته
    astronaut-cat.png       # خود طرح
    astronaut-cat.json      # متادیتای همان طرح
.github/workflows/publish-designs.yml
scripts/publish.py
```

قاعده: **نام پوشه = slug دسته** · **هر عکس یک json هم‌نام دارد**.
اگر json نداشته باشد، نام فایل عنوان طرح می‌شود.

## ۲) کلید API

1. `https://pooshai.ir/admin/api` → کلید بساز (مثلاً به نام `github-action`).
2. در مخزن: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `POOSHAI_TOKEN`
   - Value: `pshai_...`

کلید را هرگز داخل کد یا فایل json نگذار.

## ۳) گردش کار

| مرحله | اتفاق |
| --- | --- |
| push روی `main` در مسیر `designs/**` | اکشن اجرا می‌شود |
| `git diff` | فقط طرح‌های تغییرکرده انتخاب می‌شوند |
| `POST /categories` | دسته اگر نباشد ساخته می‌شود |
| `POST /assets` | عکس base64 آپلود می‌شود و `url` می‌گیرد |
| `POST /designs` | طرح ساخته یا (با `id`) ویرایش می‌شود |
| commit بازگشتی | `id` و `slug` در json ذخیره می‌شود |

آن commit بازگشتی مهم است: طبق سند API، ویرایش فقط با `id` انجام می‌شود. بدون ذخیره‌ی `id`، push دوم همان طرح یک رکورد تکراری با slug مثل `cat-2` می‌سازد.

## ۴) نمونه متادیتای طرح

```json
{
  "title": "گربه فضانورد",
  "description": "طرح گربه با کلاه فضانوردی",
  "prompt": "astronaut cat, retro print, flat vector",
  "tags": ["گربه", "فضا"],
  "fabricColor": "white",
  "placementId": "chest-a4",
  "isActive": true,
  "isFeatured": false
}
```

پس از اولین اجرا، خود اکشن `id`، `slug` و `image` را به همین فایل اضافه می‌کند.

## ۵) نمونه متادیتای دسته (`_category.json`)

```json
{
  "name": "گربه‌ها",
  "tagline": "طرح‌های گربه",
  "sortOrder": 10,
  "isActive": true
}
```

## ۶) اجرای دستی / همه‌ی طرح‌ها

در تب **Actions → Publish designs → Run workflow** گزینه‌ی `all` را روشن کن تا همه‌ی طرح‌ها دوباره همگام شوند.

## ۷) تست محلی قبل از push

```bash
pip install requests
POOSHAI_TOKEN=pshai_XXXX MODE=all python scripts/publish.py
```

## ۸) نکات محدودیت

- حداکثر حجم عکس: ۱۲ مگابایت · فرمت‌ها: png / jpeg / webp / svg
- حداکثر ۱۰ تگ و هر تگ ۳۲ نویسه
- در ویرایش، فیلدهای نفرستاده به پیش‌فرض برمی‌گردند — به همین دلیل اسکریپت همیشه کل json را می‌فرستد
- rate limit هنوز پیاده نشده؛ در push های خیلی بزرگ بهتر است دسته‌دسته push کنی
