import asyncio
import base64
import ctypes.util
import io
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from datetime import datetime, timedelta, timezone

# نصب خودکار موتور فارسی‌نویس (libraqm0) بدون نیاز به تغییر bot.yml
if not ctypes.util.find_library("raqm") and shutil.which("apt-get"):
    _r = subprocess.run(
        ["sudo", "apt-get", "install", "-y", "-qq", "libraqm0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if _r.returncode != 0:
        subprocess.run(["sudo", "apt-get", "update", "-qq"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "apt-get", "install", "-y", "-qq", "libraqm0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# نصب خودکار کتابخانه گوینده فارسی (edge-tts) بدون نیاز به تغییر bot.yml
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "edge-tts"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        import edge_tts
        HAS_EDGE_TTS = True
    except ImportError:
        edge_tts = None
        HAS_EDGE_TTS = False

import aiohttp
import arabic_reshaper
import cv2
import jdatetime
import numpy as np
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

# ==================== تنظیمات محیطی ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
EVENT_NAME = os.getenv("GITHUB_EVENT_NAME", "workflow_dispatch").strip()

GEMINI_MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))
ACTIVE_START_HOUR = 6
ACTIVE_END_HOUR = 24
MAX_RUN_SECONDS = 5 * 3600 + 30 * 60

BRAND_HANDLE = "@ShirazLastNews"
BRAND_HANDLE_LOWER = "@shirazlastnews"
BRAND_TITLE_FA = "آخرین خبرهای شیراز"
HAS_RAQM = features.check("raqm")

# ==================== پرامپت دقیق سردبیری ۶ بخشی ====================
EDITORIAL_CAPTION_PROMPT = """تو سردبیر ارشد یک رسانه خبری معتبر و رسمی در اینستاگرام با آیدی @shirazlastnews هستی.
متن یا محتوای خبری (متن، تصویر، صدا یا ویدئو) که به تو می‌دهم را دقیق بررسی کن و فقط و فقط متن نهایی و آماده انتشارِ کپشن اینستاگرام را تحویل بده (هیچ مقدمه، توضیح اضافه یا علامت ستاره و مارک‌داون مثل ** در خروجی نگذار، چون در اینستاگرام نمایش داده نمی‌شوند).

ابتدا در ذهن خود دو مورد را درباره خبر تشخیص بده:
- دسته‌بندی دقیق موضوع (یکی از ۶ دسته): «شیراز و فارس»، «نظامی و سیاسی»، «اقتصادی و معیشتی»، «ورزشی»، «حوادث» یا «عمومی».
- محلی یا سراسری بودن خبر: اگر خبر واقعاً مربوط به شهر شیراز یا شهرهای استان فارس است، «محلی» و در غیر این صورت «سراسری» محسوب می‌شود (توجه‌: عباراتی مثل «خلیج فارس»، «خبرگزاری فارس»، «خبرگزاری مهر» یا «زبان فارسی» نشانه محلی بودن نیستند).

سپس کپشن را دقیقاً با این ساختار ۶ بخشی بنویس:

۱. خط اول (تیتر خبری):
- حداکثر ۱۲ کلمه، دقیق، شفاف و بدون تحریف اعداد، اسامی یا واقعیت خبر.
- با ایموجی ⭕ و یک برچسب دقیقاً متناسب با نوع خبر شروع شود:
  - اخبار فوری، نظامی/امنیتی یا حوادث مهم: «⭕ فوری | ...»
  - اخبار اقتصادی، معیشتی یا تصمیمات مهم: «⭕ مهم | ...»
  - اخبار شهری شیراز و استان فارس: «⭕ خبر شیراز | ...»
  - اخبار ورزشی: «⭕ ورزشی | ...»
  - سایر اخبار اجتماعی و عمومی: «⭕ گزارش | ...»
- خط قرمز: هرگز از عبارات کلیک‌بیت، زرد یا تکراری مثل «جزئیات در کپشن 👇»، «تکان‌دهنده»، «تا آخر ببینید» یا «اما واقعیت ماجرا...» استفاده نکن.

۲. بدنه خبر (با یک خط فاصله زیر تیتر):
- خلاصه دقیق، روان و استاندارد خبر در ۲ تا ۳ خط کوتاه با لحن رسمی خبرگزاری‌ها.
- از گذاشتن ایموجی‌های تکراری (به‌ویژه ✅) در ابتدای خطوط خودداری کن.

۳. خط تعاملی کامنت‌گیر (با یک خط فاصله زیر بدنه):
- با ایموجی 💬 شروع شود و شامل فقط یک سؤال کوتاه و دقیقاً مرتبط با جزئیات همین خبر باشد.
- سؤال باید طوری طراحی شود که مخاطب در ۲ ثانیه و فقط با نوشتن عدد یا یک کلمه پاسخ دهد؛ مثل: «(۱: بله | ۲: خیر)» یا «(۱: ... | ۲: ...)».
- خط قرمز: هرگز برای اخبار نظامی، سیاسی، اقتصادی یا ورزشی سؤال «مقصر کیه؟» نپرس (این مدل سؤال فقط مخصوص دسته حوادث است).

۴. دعوت به فالو (با یک خط فاصله زیر سؤال — بدون تکرار آیدی):
- اگر خبر «محلی (شیراز و فارس)» بود، دقیقاً این دو خط را بگذار:
🔔 پوشش لحظه‌ای اخبار شیراز و استان فارس در استوری‌ها و ریلزها
📲 برای پیگیری ادامه خبر فالو کنید: @shirazlastnews
- اگر خبر «سراسری یا بین‌المللی» بود، دقیقاً این دو خط را بگذار:
🔥 فوری‌ترین ویدیوهای خبری ایران در ریلزها + پوشش لحظه‌ای شیراز در استوری‌ها
📲 برای پیگیری ادامه خبر فالو کنید: @shirazlastnews

۵. منبع خبر (با یک خط فاصله زیر دعوت به فالو):
- دقیقاً به شکل: «📌 منبع: [نام منبع]» (اگر منبعی ذکر نشده بود، این خط را حذف کن).

۶. هشتگ‌ها (دقیقاً در خط زیرِ منبع):
- دقیقاً ۵ هشتگ فارسی مرتبط با موضوع همین خبر در یک خط با فاصله.
- اگر خبر محلی است، ۲ هشتگ اول حتماً #شیراز و #استان_فارس باشند و ۳ هشتگ بعدی تخصصیِ موضوع خبر.
- خط قرمز: از هشتگ‌های اسپم مثل #اکسپلور #وایرال #explore #viral هرگز استفاده نکن. هشتگ #حوادث را فقط و فقط زمانی به کار ببر که دسته خبر «حوادث» باشد."""

# ==================== پرامپت و قوانین سخت‌گیرانه قلاب دوطبقه کاغذ سوخته ====================
BURNT_HOOK_PROMPT = """تو سردبیر تیترنویسی ریلزهای خبری هستی. از خبر زیر یک «قلاب دوطبقه خبری» دقیقاً با قواعد زیر بساز و خروجی را فقط و فقط در قالب JSON معتبر با دو کلید hook_line1 و hook_line2 تحویل بده (بدون مارک‌داون و بدون هیچ توضیح اضافه):

قواعد اجباری:
۱. طول کل عبارت قلاب: بین ۴ تا ۸ کلمه (ایده‌آل: ۵ تا ۷ کلمه) در قالب یک جمله یا عبارت خبری کاملاً طبیعی، دقیق و بدون تحریف اعداد و اسامی.
۲. تقسیم‌بندی متوازن (تقریباً ۵۰ به ۵۰):
   - hook_line1: دقیقاً ۲ تا ۴ کلمه و حداکثر ۲۴ کاراکتر (فقط ۱ خط) — معرفی موضوع اصلی خبر.
   - hook_line2: دقیقاً ۲ تا ۴ کلمه و حداکثر ۲۴ کاراکتر (فقط ۱ خط) — ادامه طبیعی و بخش جذاب/هیجانی خبر که حتماً با «!» یا «؟!» تمام شود.
   - اگر تعداد کل کلمات فرد بود (مثلاً ۵ یا ۷ کلمه)، تقسیم ۳+۲ یا ۴+۳ باشد تا هر دو سطر از نظر عرضی هم‌تراز باشند.
۳. خط قرمزهای نگارش فارسی:
   - hook_line1 هرگز نباید با این کلمات تمام شود: در، به، از، با، بر، تا، برای، را، که، و، یا، اما، یک، دو، عدم، بدون.
   - hook_line2 هرگز نباید با «را» شروع شود یا با حرف اضافه تمام شود.
   - ترکیب‌های اسمی دوقسمتی فارسی هرگز نباید بین دو سطر شکسته شوند (مثل: دروازه قرآن، تخت جمشید، خلیج فارس، شورای شهر، پلیس راهور، آتش‌سوزی، تیم ملی، لیگ برتر، بلوار چمران، معالی آباد).
   - هرگز از عبارات کلیک‌بیت زرد مثل «ببینید!»، «را ببینید» یا «تا آخر ببینید» استفاده نکن.
   - هیچ ایموجی داخل متن نگذار.

نمونه خروجی دقیق:
{"hook_line1": "آتش‌سوزی گسترده معالی‌آباد", "hook_line2": "جزئیات مهار حریق!"}"""

DIACRITIZE_PROMPT = """تو ویراستار گویندگی خبر به زبان فارسی معیار هستی.
متن زیر را برای خوانش کاملاً روان، شمرده و طبیعی توسط گوینده خبری آماده کن:
- اعراب‌گذاری (ـَ، ـِ، ـُ، ـّ) را «هوشمند و هدفمند» انجام بده؛ یعنی فقط روی کسره‌های اضافه، اسامی خاص، محله‌های شیراز و کلمات دوپهلو (مثل مِلک/مُلک، کُشت/کِشت، شَهر، قَصرِ دَشت) حرکت بگذار و از شلوغ کردن کل حروف با اعراب اضافه خودداری کن تا صدای گوینده دچار لکنت نشود.
- هیچ کلمه‌ای را حذف یا عوض نکن و برای مکث طبیعی گوینده از ویرگول (،) و نقطه (.) دقیق استفاده کن.
- اعداد را به حروف فارسی روان بنویس.
- فقط و فقط متن نهایی آماده خوانش را بدون توضیح اضافه برگردان."""

HOOK_FORBIDDEN_END_WORDS = {
    "در", "به", "از", "با", "بر", "تا", "برای", "را", "که", "و",
    "یا", "اما", "یک", "دو", "عدم", "بدون", "روی", "توی", "هم", "این", "آن",
}

HOOK_COMPOUND_PHRASES = [
    "دروازه قرآن", "تخت جمشید", "خلیج فارس", "شورای شهر", "پلیس راهور",
    "آتش‌سوزی", "آتش سوزی", "تیم ملی", "لیگ برتر", "معالی آباد", "معالی‌آباد",
    "بلوار چمران", "میدان نمازی", "فرهنگ شهر", "عفیف آباد", "استان فارس",
    "بانک مرکزی", "نیروی انتظامی", "هلال احمر", "آتش نشانی", "اورژانس فارس",
    "مترو شیراز", "شهرداری شیراز", "دانشگاه شیراز", "قوه قضائیه", "مجلس شورای",
]

HOOK_CLICKBAIT_PHRASES = [
    "ببینید", "تا آخر", "تکان‌دهنده", "تکان دهنده", "باورکردنی نیست", "جزئیات در کپشن",
]

# ==================== بانک تلفظ دقیق فارسی (شیراز، فارس و اصطلاحات خبری) ====================
DEFAULT_PRONUNCIATION_DICT = {
    "معالی‌آباد": "مَعالی‌آباد",
    "معالی آباد": "مَعالی‌آباد",
    "قصردشت": "قَصرِ دَشت",
    "قصر دشت": "قَصرِ دَشت",
    "عفیف‌آباد": "عَفیف‌آباد",
    "عفیف آباد": "عَفیف‌آباد",
    "دروازه قرآن": "دَروازِه‌یِ قُرآن",
    "شاهچراغ": "شاه‌چِراغ",
    "تخت جمشید": "تَختِ جَمشید",
    "تاچارا": "تاچارا",
    "صدرا": "صَدرا",
    "مرودشت": "مَرو‌دَشت",
    "کازرون": "کازِرون",
    "جهرم": "جَهرُم",
    "فسا": "فَسا",
    "لارستان": "لارِستان",
    "لامرد": "لامِرد",
    "سپیدان": "سِپیدان",
    "ممسنی": "مَمَسَنی",
    "اقلید": "اِقلید",
    "آباده": "آبادِه",
    "استهبان": "اِستَهبان",
    "نی‌ریز": "نِی‌ریز",
    "کوار": "کَوار",
    "زرقان": "زَرقان",
    "گراش": "گِراش",
    "اوز": "اِوَز",
    "سروستان": "سَروِستان",
    "خرامه": "خَرامِه",
    "فیروزآباد": "فیروزآباد",
    "پاسارگاد": "پاسارگاد",
    "میانرود": "میانرود",
    "کوزه‌گری": "کوزِه‌گَری",
    "شورای شهر": "شورایِ شَهر",
    "پلیس راهور": "پُلیسِ راهوَر",
    "آتش‌سوزی": "آتَش‌سوزی",
    "شهرداری شیراز": "شَهرداریِ شیراز",
    "استان فارس": "اُستانِ فارس",
    "خلیج فارس": "خَلیجِ فارس",
    "تیم ملی": "تیمِ مِلّی",
    "لیگ برتر": "لیگِ بَرتَر",
    "خبر فوری": "خَبَرِ فوری",
}

# ==================== تم‌های گرافیکی ====================
THEMES = {
    "navy": {
        "name": "تم رسمی سرمه‌ای 🔵",
        "btn": "🔵 تم رسمی سرمه‌ای",
        "bg": (11, 27, 52),
        "accent": (234, 179, 8),
        "badge_bg": (204, 18, 28),
        "badge_text": (255, 255, 255),
        "text": (255, 255, 255),
        "subtext": (210, 222, 240),
        "wave_hex": "0xEAB308",
    },
    "incident": {
        "name": "تم فوری و حادثه‌ای 🔴",
        "btn": "🔴 تم فوری و حادثه‌ای",
        "bg": (18, 12, 14),
        "accent": (220, 38, 38),
        "badge_bg": (220, 38, 38),
        "badge_text": (255, 255, 255),
        "text": (255, 255, 255),
        "subtext": (254, 226, 226),
        "wave_hex": "0xEF4444",
    },
    "mourning": {
        "name": "تم سوگواری مشکی-نقره‌ای 🖤",
        "btn": "🖤 تم سوگواری",
        "bg": (12, 12, 15),
        "accent": (180, 188, 198),
        "badge_bg": (55, 65, 81),
        "badge_text": (243, 244, 246),
        "text": (248, 250, 252),
        "subtext": (190, 198, 208),
        "wave_hex": "0xCBD5E1",
    },
    "sports": {
        "name": "تم ورزشی سبز 🟢",
        "btn": "🟢 تم ورزشی",
        "bg": (6, 40, 30),
        "accent": (34, 197, 94),
        "badge_bg": (22, 163, 74),
        "badge_text": (255, 255, 255),
        "text": (255, 255, 255),
        "subtext": (209, 250, 229),
        "wave_hex": "0x22C55E",
    },
}

# ==================== بانک مختصات محله‌های شیراز و شهرهای فارس ====================
FARS_LOCATIONS = {
    "معالی آباد": (29.6712, 52.4638, 15),
    "معالی‌آباد": (29.6712, 52.4638, 15),
    "صدرا": (29.7984, 52.4970, 14),
    "چمران": (29.6470, 52.5015, 15),
    "قصردشت": (29.6455, 52.4950, 15),
    "دروازه قرآن": (29.6352, 52.5618, 15),
    "شاهچراغ": (29.6095, 52.5433, 15),
    "عفیف آباد": (29.6197, 52.5067, 15),
    "عفیف‌آباد": (29.6197, 52.5067, 15),
    "زند": (29.6177, 52.5401, 15),
    "میدان نمازی": (29.6272, 52.5236, 15),
    "نمازی": (29.6272, 52.5236, 15),
    "ستارخان": (29.6289, 52.5008, 15),
    "فرهنگ شهر": (29.6552, 52.4730, 15),
    "فرهنگ‌شهر": (29.6552, 52.4730, 15),
    "تاچارا": (29.6626, 52.4820, 15),
    "گلستان": (29.7130, 52.4350, 14),
    "میانرود": (29.5562, 52.5028, 14),
    "کوزه‌گری": (29.5750, 52.5780, 14),
    "حافظیه": (29.6257, 52.5584, 15),
    "سعدیه": (29.6224, 52.5831, 15),
    "مرودشت": (29.8742, 52.8025, 13),
    "تخت جمشید": (29.9352, 52.8915, 14),
    "جهرم": (28.5000, 53.5605, 13),
    "فسا": (28.9383, 53.6482, 13),
    "کازرون": (29.6195, 51.6541, 13),
    "لار": (27.6835, 54.3413, 13),
    "لارستان": (27.6835, 54.3413, 12),
    "داراب": (28.7519, 54.5444, 13),
    "فیروزآباد": (28.8438, 52.5707, 13),
    "آباده": (31.1608, 52.6506, 13),
    "اقلید": (30.8926, 52.6873, 13),
    "لامرد": (27.3339, 53.1789, 13),
    "نی‌ریز": (29.1988, 54.3278, 13),
    "نی ریز": (29.1988, 54.3278, 13),
    "استهبان": (29.1265, 54.0419, 13),
    "سپیدان": (30.2606, 51.9810, 13),
    "ممسنی": (30.1141, 51.5217, 13),
    "زرقان": (29.7720, 52.7192, 14),
    "کوار": (29.2050, 52.6897, 13),
    "خرامه": (29.5000, 53.3164, 13),
    "گراش": (27.6652, 54.1371, 13),
    "اوز": (27.7611, 54.0067, 13),
    "پاسارگاد": (30.1942, 53.1670, 13),
    "سروستان": (29.2735, 53.2202, 13),
    "شیراز": (29.5918, 52.5837, 13),
    "فارس": (29.5918, 52.5837, 9),
}

# ==================== بانک مناسبت‌های شمسی و سپر ضدشدوبن ====================
JALALI_MONTHS = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]
JALALI_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]

SHAMSI_OCCASIONS = {
    (1, 1): "آغاز نوروز و سال نو خورشیدی",
    (1, 12): "روز جمهوری اسلامی ایران",
    (1, 13): "روز طبیعت",
    (2, 1): "روز بزرگداشت سعدی شیرازی",
    (2, 10): "روز ملی خلیج فارس",
    (2, 12): "روز معلم",
    (2, 15): "روز شیراز — پایتخت فرهنگ و ادب ایران",
    (2, 25): "روز بزرگداشت فردوسی و پاسداشت زبان فارسی",
    (3, 3): "سالروز آزادسازی خرمشهر",
    (3, 14): "سالروز رحلت امام خمینی (ره)",
    (4, 7): "روز قوه قضائیه",
    (5, 17): "روز خبرنگار",
    (6, 1): "روز پزشک و بزرگداشت بوعلی سینا",
    (6, 4): "روز کارمند",
    (6, 27): "روز شعر و ادب فارسی",
    (6, 31): "آغاز هفته دفاع مقدس",
    (7, 7): "روز آتش‌نشانی و ایمنی",
    (7, 13): "روز نیروی انتظامی",
    (7, 20): "روز بزرگداشت حافظ شیرازی",
    (8, 13): "روز دانش‌آموز",
    (8, 24): "روز کتاب، کتاب‌خوانی و کتابدار",
    (9, 5): "روز بسیج مستضعفین",
    (9, 7): "روز نیروی دریایی",
    (9, 16): "روز دانشجو",
    (9, 30): "شب یلدا (چله)",
    (10, 9): "روز بصیرت",
    (11, 22): "سالروز پیروزی انقلاب اسلامی",
    (12, 5): "روز مهندس",
    (12, 15): "روز درختکاری",
    (12, 29): "روز ملی شدن صنعت نفت ایران",
}

SENSITIVE_WORDS = {
    "قتل": "جان‌باختن / حادثه تلخ",
    "خودکشی": "پایان دادن به زندگی / حادثه شخصی",
    "کشته": "جان‌باخته",
    "کشتار": "تلفات گسترده",
    "جنازه": "پیکر",
    "جسد": "پیکر",
    "خونین": "شدید / پرتلفات",
    "خونریزی": "آسیب‌دیدگی شدید",
    "انفجار": "حادثه حریق و موج شدید / صدای مهیب",
    "بمب": "ماده منفجره / شیء مشکوک",
    "ترور": "سوءقصد",
    "تروریست": "عوامل مهاجم",
    "شلیک": "تیراندازی / درگیری",
    "تیراندازی": "درگیری مسلحانه",
    "موشک": "پرتابه",
    "پهپاد": "پرنده",
    "حمله": "عملیات / رخداد امنیتی",
    "اعدام": "اجرای حکم قضایی",
    "تجاوز": "آزار / جرم سنگین",
    "مواد مخدر": "مواد غیرمجاز",
    "اسلحه": "سلاح",
}

# ==================== برچسب دکمه‌های منوی دسته‌بندی‌شده جدید ====================
# منوی اصلی (۲×۲ خلوت و سریع)
BTN_CAT_REELS = "🎬 استودیو ریلز و ویدئو"
BTN_CAT_STORY = "🖼️ استودیو استوری و کپشن"
BTN_CAT_QUICK = "⚡ تولید سریع و ابزارها"
BTN_CAT_SETTINGS = "⚙️ تنظیمات و وضعیت"

# زیرمنوی ۱: استودیو ریلز و ویدئو
BTN_INCIDENT = "🚨 ریلز فوری و حادثه‌ای"
BTN_MAP = "🗺️ ریلز زوم نقشه"
BTN_DAILY60 = "🎬 ریلز جمع‌بندی (۶ سبک)"
BTN_VIDEO = "🎞️ استودیو تدوین ویدئو"
BTN_HOOK_ONLY = "🔥 قلاب‌گذار کاغذ سوخته"
BTN_AUDIO = "🎙️ ریلز موج صوتی"

# زیرمنوی ۲: استودیو استوری و کپشن
BTN_CARD_STORY = "📱 کارت استوری رسمی پیج"
BTN_CARD_POST = "🖼️ کارت پست (۴:۵)"
BTN_CAPTION = "✍️ کپشن‌نویس ۶ بخشی"
BTN_SHADOWBAN = "🛡️ سپر ضدشدوبن"
BTN_OCCASION = "📅 کارت مناسبت امروز"

# زیرمنوی ۳: تولید سریع و ابزارها
BTN_ONE_TAP = "📦 بسته کامل خبر (پک)"
BTN_CLEAN_LOGO = "🧹 حذف واترمارک و لوگو"
BTN_WEATHER = "🌤️ استوری هواشناسی شیراز"

# زیرمنوی ۴: تنظیمات و وضعیت
BTN_THEME = "🎨 تغییر تم گرافیکی"
BTN_STUDIO_OPTS = "🎛️ تنظیمات تدوین و قاب‌ها"
BTN_PRONOUNCE = "🗣️ بانک تلفظ گوینده"
BTN_STATUS = "📊 وضعیت استودیو"

# دکمه‌های مشترک و عملیاتی
BTN_BACK = "🔙 منوی اصلی"
BTN_CANCEL = "❌ انصراف و بازگشت"
BTN_SKIP_PHOTO = "⏭️ بدون عکس گوینده"
BTN_SAFE_REWRITE = "✨ بازنویسی ایمن آخرین کپشن"
BTN_HOOK_CONFIRM = "✅ تایید و ساخت ویدئو"
BTN_HOOK_EDIT = "✏️ اصلاح دستی متن قلاب"
BTN_HOOK_REGEN = "🔄 پیشنهاد قلاب جدید"

# دکمه‌های گوشه حذف واترمارک
BTN_CORNER_TR = "↗️ گوشه بالا راست"
BTN_CORNER_TL = "↖️ گوشه بالا چپ"
BTN_CORNER_BR = "↘️ گوشه پایین راست"
BTN_CORNER_BL = "↙️ گوشه پایین چپ"

# دکمه‌های ۶ سبک ریلز جمع‌بندی (بدون قلاب کاغذ سوخته)
BTN_STYLE_BROADCAST = "📺 ۱. برودکست شیشه‌ای"
BTN_STYLE_SPLIT = "📰 ۲. دوپنجره‌ای تحریریه"
BTN_STYLE_EDITORIAL = "🗞️ ۳. مطبوعاتی تحلیلی"
BTN_STYLE_KINETIC = "⚡ ۴. اکسپلور تند"
BTN_STYLE_LIVE = "📡 ۵. بولتین زنده"
BTN_STYLE_HOLOGRAM = "💎 ۶. هولوگرام + گوینده"
BTN_CLEAR_DAILY = "🧹 پاک کردن صف جمع‌بندی"

DAILY_STYLE_MAP = {
    BTN_STYLE_BROADCAST: ("broadcast", "برودکست شیشه‌ای"),
    BTN_STYLE_SPLIT: ("split", "دوپنجره‌ای تحریریه"),
    BTN_STYLE_EDITORIAL: ("editorial", "مطبوعاتی تحلیلی"),
    BTN_STYLE_KINETIC: ("kinetic", "اکسپلور تند"),
    BTN_STYLE_LIVE: ("live", "بولتین زنده تلویزیونی"),
    BTN_STYLE_HOLOGRAM: ("hologram", "هولوگرام شیشه‌ای + گوینده فارسی"),
}

CONFIG = {
    "theme": "navy",
    "use_repo_frame": True,      # قاب ۳ باکسه ریلز (reel_frame.png)
    "use_burnt_hook": True,      # قلاب کاغذ سوخته ۳ ثانیه اول (فقط در تدوین ویدئو / پک، نه جمع‌بندی)
    "make_grid_cover": True,     # ساخت خودکار کاور ۴:۵ گرید پروفایل همراه ریلزها
    "video_antidup": True,       # اصالت‌سازی و حذف متادیتا
    "video_facetrack": True,     # ردیابی چهره ۹:۱۶
    "video_brand": True,         # اند-اسکرین دعوت به فالو
    "video_ticker": True,        # نوار زیرنویس متحرک شبکه خبر
    "auto_shadowban": True,
    "auto_daily_card": True,
    "tts_profile": "studio_baritone",  # پروفایل صدای اختصاصی رادیویی
    "custom_pronunciations": {},
    "last_occasion_date": "",
}

CONFIG_PIN_PREFIX = "⚙️STUDIO_CFG:"
CONFIG_MSG_ID = None

USER_STATE = {}
LAST_CAPTION = {}
DAILY_ITEMS = []
BG_TASKS = set()
TMP_ROOT = tempfile.mkdtemp(prefix="shiraz_studio_")
# ==================== ابزارهای کمکی، صدای اضطراری و اجرای امن FFmpeg ====================
def run_ffmpeg(cmd: list):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        err_lines = [ln.strip() for ln in res.stderr.splitlines() if ln.strip()]
        tail = "\n".join(err_lines[-5:]) if err_lines else f"exit code {res.returncode}"
        raise RuntimeError(tail)


def find_repo_audio(mode: str = "incident") -> str:
    if mode == "incident":
        cands = ("incident.mp3", "sounds/incident.mp3", "incident_music.mp3", "sounds/incident_music.mp3")
    elif mode == "hologram":
        cands = ("hologram.mp3", "sounds/hologram.mp3", "epic.mp3", "daily.mp3", "news.mp3", "sounds/news.mp3")
    else:
        cands = ("daily.mp3", "sounds/daily.mp3", "news.mp3", "sounds/news.mp3", "news_music.mp3")
    for p in cands:
        if os.path.exists(p) and os.path.getsize(p) > 4000:
            return p
    return ""


def generate_emergency_audio_wav(out_path: str, duration_sec: float, mode: str = "incident") -> str:
    sr = 44100
    n = int(sr * duration_sec)
    t = np.linspace(0.0, duration_sec, n, endpoint=False, dtype=np.float64)

    if mode == "incident":
        boom_env = np.exp(-t * 4.5) * (t < 1.2)
        boom = 0.55 * np.sin(2 * np.pi * (95.0 - 45.0 * np.minimum(t, 1.0)) * t) * boom_env
        alert_beep = 0.28 * np.sin(2 * np.pi * 1040.0 * t) * (
            ((t >= 0.05) & (t < 0.22)) | ((t >= 0.30) & (t < 0.47)) | ((t >= 0.55) & (t < 0.72))
        )
        siren_phase = 2 * np.pi * (720.0 * t - (200.0 / (2 * np.pi * 1.15)) * np.cos(2 * np.pi * 1.15 * t))
        siren = 0.19 * (0.75 * np.sin(siren_phase) + 0.25 * np.sin(2.0 * siren_phase))
        siren *= np.clip((t - 0.5) / 0.6, 0.0, 1.0)
        pulse_cycle = np.mod(t, 0.50)
        kick = 0.32 * np.sin(2 * np.pi * 62.0 * t) * np.exp(-pulse_cycle * 14.0)
        tick_cycle = np.mod(t, 0.14)
        type_ticks = 0.11 * np.sin(2 * np.pi * 2400.0 * t) * np.exp(-tick_cycle * 65.0) * ((t >= 1.2) & (t < 5.5))
        signal = boom + alert_beep + siren + kick + type_ticks
    elif mode == "hologram":
        bar = np.mod(t, 0.50)
        sub = 0.22 * np.sin(2 * np.pi * 68.0 * t) * np.exp(-bar * 5.0)
        arp = 0.08 * np.sin(2 * np.pi * (220.0 + 110.0 * np.floor(np.mod(t * 2.0, 4.0))) * t) * np.exp(-np.mod(t, 0.5) * 7.0)
        pad = 0.07 * np.sin(2 * np.pi * 136.0 * t) * (0.65 + 0.35 * np.sin(2 * np.pi * 0.45 * t))
        signal = sub + arp + pad
    else:
        bar = np.mod(t, 0.60)
        bass = 0.18 * np.sin(2 * np.pi * 92.0 * t) * np.exp(-bar * 6.0)
        chime_cycle = np.mod(t, 1.20)
        chime = 0.09 * np.sin(2 * np.pi * 440.0 * t) * np.exp(-chime_cycle * 10.0)
        pad = 0.06 * np.sin(2 * np.pi * 184.0 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.8 * t))
        signal = bass + chime + pad

    fade_n = min(int(sr * 0.4), n // 4)
    if fade_n > 0:
        signal[-fade_n:] *= np.linspace(1.0, 0.0, fade_n)
    signal = np.tanh(signal) * 0.90
    pcm = (signal * 32767.0).astype(np.int16)

    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return out_path


def get_audio_track(work_dir: str, duration_sec: float, mode: str = "incident") -> str:
    repo_mp3 = find_repo_audio(mode)
    if repo_mp3:
        return repo_mp3
    return generate_emergency_audio_wav(os.path.join(work_dir, f"sfx_{mode}.wav"), duration_sec, mode=mode)


def pipe_frames_to_mp4(frame_generator, out_mp4: str, audio_path: str, fps: int = 25, loop_audio: bool = True):
    """ارسال مستقیم فریم‌ها به FFmpeg بدون خطای flush و با تکرار خودکار موزیک‌های کوتاه."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", "1080x1920", "-r", str(fps),
        "-i", "-",
    ]
    if loop_audio:
        cmd += ["-stream_loop", "-1"]
    cmd += [
        "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
        "-shortest", "-map_metadata", "-1", "-movflags", "+faststart",
        out_mp4,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    write_err = None
    try:
        for frame_rgb in frame_generator:
            proc.stdin.write(frame_rgb.tobytes())
    except BrokenPipeError:
        pass
    except Exception as e:
        write_err = e
    finally:
        if proc.stdin:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.stdin = None
    err = proc.stderr.read() if proc.stderr else b""
    if proc.stderr:
        proc.stderr.close()
    proc.wait()
    if write_err:
        raise write_err
    if proc.returncode != 0:
        err_txt = err.decode("utf-8", errors="ignore")
        lines = [ln.strip() for ln in err_txt.splitlines() if ln.strip()]
        raise RuntimeError("\n".join(lines[-4:]) if lines else f"ffmpeg exit {proc.returncode}")


def get_tehran_now() -> datetime:
    return datetime.now(TEHRAN_TZ)


def should_keep_running(boot_time: float) -> bool:
    if (time.time() - boot_time) >= MAX_RUN_SECONDS:
        return False
    if EVENT_NAME == "workflow_dispatch":
        return True
    now = get_tehran_now()
    return ACTIVE_START_HOUR <= now.hour < ACTIVE_END_HOUR


def is_admin(user_id: str) -> bool:
    return bool(ADMIN_ID) and str(user_id) == str(ADMIN_ID)


def find_repo_reel_frame() -> str:
    for path in ("reel_frame.png", "assets/reel_frame.png", "reel_overlay.png", "assets/reel_overlay.png", "frame.png"):
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return path
    return ""


def find_repo_logo() -> str:
    for path in ("logo.png", "assets/logo.png", "quran_gate.png", "assets/quran_gate.png", "brand_logo.png"):
        if os.path.exists(path) and os.path.getsize(path) > 500:
            return path
    for fname in os.listdir("."):
        low = fname.lower()
        if low.endswith(".png") and ("logo" in low or "لوگو" in fname or "دروازه" in fname) and os.path.getsize(fname) > 500:
            return fname
    return ""


def extract_source_name(news_text: str) -> str:
    if not news_text:
        return ""
    m = re.search(r"منبع\s*[:：]\s*([^\n|،]+)", news_text)
    if m:
        return strip_emojis_for_font(m.group(1))[:36]
    agencies = [
        ("ایرنا", "خبرگزاری ایرنا"), ("فارس", "خبرگزاری فارس"), ("تسنیم", "خبرگزاری تسنیم"),
        ("ایسنا", "خبرگزاری ایسنا"), ("مهر", "خبرگزاری مهر"), ("ایلنا", "خبرگزاری ایلنا"),
        ("باشگاه خبرنگاران", "باشگاه خبرنگاران جوان"), ("صداوسیما", "خبرگزاری صداوسیما"),
        ("میزان", "خبرگزاری میزان"), ("دانشجو", "خبرگزاری دانشجو"), ("روابط عمومی", "روابط عمومی"),
    ]
    for key, title in agencies:
        if key in news_text:
            return title
    return ""


def spawn_bg_task(coro):
    task = asyncio.create_task(coro)
    BG_TASKS.add(task)
    task.add_done_callback(BG_TASKS.discard)
    return task


def to_persian_digits(text: str) -> str:
    en, fa = "0123456789", "۰۱۲۳۴۵۶۷۸۹"
    for i in range(10):
        text = text.replace(en[i], fa[i])
    return text


def strip_emojis_for_font(text: str) -> str:
    if not text:
        return ""
    allowed = re.sub(
        r"[^\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF\u200c\x20-\x7E«»—–،؛؟!\n]",
        " ",
        text,
    )
    return re.sub(r"[ \t]+", " ", allowed).strip()


def find_font_path(kind: str = "bold") -> str:
    if not HAS_RAQM and kind == "display":
        kind = "bold"
    candidates = {
        "display": ["fonts/Lalezar-Regular.ttf", "fonts/Vazirmatn-Bold.ttf"],
        "bold": [
            "fonts/Vazirmatn-Bold.ttf",
            "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ],
        "regular": [
            "fonts/Vazirmatn-Regular.ttf",
            "fonts/Vazirmatn-Bold.ttf",
            "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ],
    }
    for p in candidates.get(kind, candidates["bold"]):
        if os.path.exists(p) and os.path.getsize(p) > 5000:
            return p
    return "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load_font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(find_font_path(kind), max(12, int(size)))
    except Exception:
        return ImageFont.load_default()


def prepare_text_and_kwargs(text: str, is_rtl: bool = True) -> tuple:
    clean = strip_emojis_for_font(text)
    if HAS_RAQM:
        return (clean, {"direction": "rtl", "language": "fa"}) if is_rtl else (clean, {"direction": "ltr"})
    if is_rtl:
        return get_display(arabic_reshaper.reshape(clean)), {}
    return clean, {}


def wrap_all_words(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    clean = strip_emojis_for_font(text).replace("\n", " ")
    words = clean.split()
    if not words:
        return []
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        t_draw, kw = prepare_text_and_kwargs(trial, is_rtl=True)
        bbox = draw.textbbox((0, 0), t_draw, font=font, **kw)
        if (bbox[2] - bbox[0]) <= max_width or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def fit_text_in_box(
    draw: ImageDraw.ImageDraw, text: str, font_kind: str, max_width: int, max_height: int,
    max_size: int = 72, min_size: int = 24, max_lines: int = 3, line_spacing: float = 1.32,
) -> tuple:
    clean = strip_emojis_for_font(text)
    for sz in range(max_size, min_size - 1, -3):
        font = load_font(font_kind, sz)
        lines = wrap_all_words(draw, clean, font, max_width)
        if not lines:
            return font, [], int(sz * line_spacing)
        lh = int(sz * line_spacing)
        if len(lines) <= max_lines and (len(lines) * lh) <= max_height:
            return font, lines, lh
    font = load_font(font_kind, min_size)
    return font, wrap_all_words(draw, clean, font, max_width)[:max_lines], int(min_size * line_spacing)


def draw_rtl_text(
    draw: ImageDraw.ImageDraw, xy: tuple, text: str, font: ImageFont.FreeTypeFont, fill: tuple,
    align: str = "center", shadow: bool = True, shadow_offset: int = 4, is_rtl: bool = True,
):
    clean = strip_emojis_for_font(text)
    if not clean:
        return
    t_draw, kw = prepare_text_and_kwargs(clean, is_rtl=is_rtl)
    bbox = draw.textbbox((0, 0), t_draw, font=font, **kw)
    x, y = xy
    if align == "center":
        x = x - (bbox[0] + bbox[2]) // 2
    elif align == "right":
        x = x - bbox[2]
    else:
        x = x - bbox[0]
    if shadow:
        draw.text((x + shadow_offset, y + shadow_offset), t_draw, font=font, fill=(0, 0, 0, 185), **kw)
    draw.text((x, y), t_draw, font=font, fill=fill, **kw)


def draw_centered_block_in_box(
    draw: ImageDraw.ImageDraw, box: tuple, text: str, font_kind: str, fill: tuple,
    max_size: int = 64, min_size: int = 22, max_lines: int = 3, align: str = "center",
    pad_x: int = 28, pad_y: int = 12, shadow: bool = False,
):
    x1, y1, x2, y2 = box
    bw = max(40, (x2 - x1) - pad_x * 2)
    bh = max(30, (y2 - y1) - pad_y * 2)
    font, lines, lh = fit_text_in_box(draw, text, font_kind, bw, bh, max_size=max_size, min_size=min_size, max_lines=max_lines)
    if not lines:
        return
    total_h = len(lines) * lh
    cur_y = y1 + ((y2 - y1) - total_h) // 2
    for ln in lines:
        ax = (x2 - pad_x) if align == "right" else ((x1 + pad_x) if align == "left" else (x1 + x2) // 2)
        draw_rtl_text(draw, (ax, cur_y), ln, font, fill, align=align, shadow=shadow, shadow_offset=3)
        cur_y += lh


def fit_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    nw, nh = int(src_w * scale), int(src_h * scale)
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left, top = (nw - target_w) // 2, (nh - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def clean_caption_markdown(text: str) -> str:
    text = text.replace("**", "").replace("__", "").replace("```", "")
    return "\n".join(ln.rstrip() for ln in text.strip().splitlines()).strip()


def check_shadowban_words(text: str) -> list:
    return [(w, alt) for w, alt in SENSITIVE_WORDS.items() if w in text]


def add_to_daily_items(headline: str, photo_path: str = None, tag: str = "خبر"):
    clean_hl = strip_emojis_for_font(headline)
    if "|" in clean_hl:
        clean_hl = clean_hl.split("|", 1)[1].strip()
    saved_img = None
    if photo_path and os.path.exists(photo_path):
        saved_img = os.path.join(TMP_ROOT, f"daily_{int(time.time())}_{len(DAILY_ITEMS)}.jpg")
        try:
            shutil.copy(photo_path, saved_img)
        except Exception:
            saved_img = None
    DAILY_ITEMS.append({
        "headline": clean_hl[:110],
        "photo": saved_img,
        "tag": strip_emojis_for_font(tag) or "شیراز",
        "time": get_tehran_now().strftime("%H:%M"),
    })
    if len(DAILY_ITEMS) > 10:
        old = DAILY_ITEMS.pop(0)
        if old.get("photo") and os.path.exists(old["photo"]):
            try:
                os.remove(old["photo"])
            except Exception:
                pass


# ==================== اسکنر خودکار باکس‌های قاب ریلز (reel_frame.png) ====================
def detect_reel_frame_boxes(frame_rgba: Image.Image) -> dict:
    arr = np.array(frame_rgba.resize((1080, 1920), Image.Resampling.LANCZOS))
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    boxes = {
        "red_badge": (80, 140, 382, 234),
        "title_box": (24, 1008, 1026, 1180),
        "sub_box": (60, 1430, 1020, 1622),
    }
    red_mask = ((a > 120) & (r > 155) & (g < 85) & (b < 85)).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    red_top = [(x, y, x + w, y + h) for c in cnts for x, y, w, h in [cv2.boundingRect(c)] if y < 750 and w >= 110 and h >= 40]
    if red_top:
        red_top.sort(key=lambda bx: bx[1])
        boxes["red_badge"] = red_top[0]

    dark_mask = ((a > 120) & (r < 68) & (g < 68) & (b < 68)).astype(np.uint8) * 255
    cnts_d, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    dark_boxes = [(x, y, x + w, y + h) for c in cnts_d for x, y, w, h in [cv2.boundingRect(c)] if w >= 450 and h >= 70 and y >= 450]
    dark_boxes.sort(key=lambda bx: bx[1])
    if len(dark_boxes) >= 2:
        boxes["title_box"], boxes["sub_box"] = dark_boxes[0], dark_boxes[1]
    elif len(dark_boxes) == 1:
        boxes["title_box"] = dark_boxes[0]
    return boxes


def render_reel_frame_overlay(frame_path: str, badge: str, headline: str, subtitle: str, work_dir: str) -> str:
    frame = Image.open(frame_path).convert("RGBA").resize((1080, 1920), Image.Resampling.LANCZOS)
    boxes = detect_reel_frame_boxes(frame)
    draw = ImageDraw.Draw(frame)

    draw_centered_block_in_box(draw, boxes["red_badge"], badge or "خبر فوری", "display", (255, 255, 255, 255), max_size=44, min_size=24, max_lines=1, align="center", pad_x=16, pad_y=8)
    draw_centered_block_in_box(draw, boxes["title_box"], headline or BRAND_TITLE_FA, "display", (255, 255, 255, 255), max_size=56, min_size=26, max_lines=2, align="right", pad_x=30, pad_y=12, shadow=True)
    sub_text = subtitle.strip() if subtitle and subtitle.strip() else f"پوشش لحظه‌ای اخبار شیراز و فارس | {BRAND_HANDLE}"
    draw_centered_block_in_box(draw, boxes["sub_box"], sub_text, "bold", (235, 240, 248, 255), max_size=38, min_size=22, max_lines=3, align="center", pad_x=32, pad_y=14)

    out_p = os.path.join(work_dir, f"filled_reel_frame_{int(time.time()*1000)}.png")
    frame.save(out_p, format="PNG")
    return out_p


# ==================== سیستم دقیق «قلاب دوطبقه کاغذ سوخته» (۳ ثانیه اول) ====================
def validate_and_balance_burnt_hook(line1: str, line2: str, fallback_text: str = "") -> tuple:
    """اعتبارسنجی سخت‌گیرانه قواعد نگارش فارسی و توازن ۵۰-۵۰ برای دو سطر قلاب کاغذ سوخته."""
    def clean_part(s: str) -> str:
        s = strip_emojis_for_font(s).replace("|", " ").replace("«", "").replace("»", "").strip()
        for bad in HOOK_CLICKBAIT_PHRASES:
            s = s.replace(bad, "")
        return re.sub(r"\s+", " ", s).strip()

    l1 = clean_part(line1).rstrip("!؟?.،؛:")
    l2 = clean_part(line2).rstrip(".،؛:")

    # بررسی نشکستن ترکیب‌های دوقسمتی و حذف حرف اضافه معلق از پایان سطر ۱
    def is_valid_split(a_words: list, b_words: list) -> bool:
        if not (2 <= len(a_words) <= 4 and 2 <= len(b_words) <= 4):
            return False
        if a_words[-1] in HOOK_FORBIDDEN_END_WORDS:
            return False
        if b_words[0] == "را" or b_words[-1].rstrip("!؟") in HOOK_FORBIDDEN_END_WORDS:
            return False
        s_a, s_b = " ".join(a_words), " ".join(b_words)
        if len(s_a) > 24 or len(s_b) > 24:
            return False
        boundary = f"{a_words[-1]} {b_words[0]}"
        for comp in HOOK_COMPOUND_PHRASES:
            if boundary == comp:
                return False
        return True

    w1, w2 = l1.split(), l2.split()
    if is_valid_split(w1, w2):
        final_l2 = l2 if (l2.endswith("!") or l2.endswith("؟!")) else (l2.rstrip("؟") + "؟!" if l2.endswith("؟") else l2 + "!")
        return l1, final_l2[:24]

    # تلاش برای بازچینش متوازن کلمات ترکیبی (۴ تا ۸ کلمه)
    combined = (l1 + " " + l2).strip() or clean_part(fallback_text)
    words = combined.split()[:8]
    if len(words) < 4:
        words = ["خبر", "فوری", "شیراز", "جزئیات", "تازه!"]

    best = None
    best_score = 999
    for cut in range(2, min(5, len(words) - 1)):
        a_w, b_w = words[:cut], words[cut:]
        if not (2 <= len(b_w) <= 4):
            continue
        if a_w[-1] in HOOK_FORBIDDEN_END_WORDS or b_w[0] == "را" or b_w[-1].rstrip("!؟") in HOOK_FORBIDDEN_END_WORDS:
            continue
        boundary = f"{a_w[-1]} {b_w[0]}"
        if any(boundary == comp for comp in HOOK_COMPOUND_PHRASES):
            continue
        sa, sb = " ".join(a_w), " ".join(b_w)
        if len(sa) <= 24 and len(sb) <= 23:
            score = abs(len(sa) - len(sb)) + abs(len(a_w) - len(b_w)) * 3
            if score < best_score:
                best_score = score
                best = (sa, sb)

    if best:
        sa, sb = best
    else:
        mid = max(2, min(4, (len(words) + 1) // 2))
        sa = " ".join(words[:mid])[:24]
        sb = " ".join(words[mid:mid + 4])[:23]
        if not sb:
            sb = "جزئیات تکمیلی خبر"

    sb = sb.rstrip(".،؛:")
    if not (sb.endswith("!") or sb.endswith("؟!")):
        sb = (sb.rstrip("؟") + "؟!") if sb.endswith("؟") else (sb + "!")
    return sa.strip(), sb.strip()


def _make_torn_polygon(w: int, h: int, margin: int, jitter_v: float, jitter_h: float, pts_x: int = 48, pts_y: int = 16, seed: int = 11) -> list:
    rng = random.Random(seed)
    pts = []
    # لبه بالا (چپ به راست)
    for i in range(pts_x + 1):
        x = margin + (w - 2 * margin) * (i / pts_x)
        y = margin + rng.uniform(-jitter_v, jitter_v)
        pts.append((x, y))
    # لبه راست (بالا به پایین)
    for j in range(1, pts_y + 1):
        x = (w - margin) + rng.uniform(-jitter_h, jitter_h)
        y = margin + (h - 2 * margin) * (j / pts_y)
        pts.append((x, y))
    # لبه پایین (راست به چپ)
    for i in range(pts_x - 1, -1, -1):
        x = margin + (w - 2 * margin) * (i / pts_x)
        y = (h - margin) + rng.uniform(-jitter_v, jitter_v)
        pts.append((x, y))
    # لبه چپ (پایین به بالا)
    for j in range(pts_y - 1, 0, -1):
        x = margin + rng.uniform(-jitter_h, jitter_h)
        y = margin + (h - 2 * margin) * (j / pts_y)
        pts.append((x, y))
    return pts


def _render_single_burnt_strip(
    text: str,
    sc: float,
    min_w_base: int,
    max_w_base: int,
    h_base: int,
    center_rgb: tuple,
    warm_rgb: tuple,
    charcoal_rgb: tuple,
    text_rgb: tuple,
    stroke_rgb: tuple,
    stroke_w_base: int,
    font_base: int,
    font_min: int,
    text_shadow: bool = False,
    seed: int = 17,
) -> Image.Image:
    """رندر یک نوار کاغذ سوخته و پاره‌شده با مرکز ۱۰۰٪ تمیز و سوختگی نرم فقط در لبه‌ها."""
    clean = strip_emojis_for_font(text)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    max_w = int(round(max_w_base * sc))
    min_w = int(round(min_w_base * sc))
    pad_total = int(round(170 * sc))  # 85px در هر طرف
    strip_h = int(round(h_base * sc))

    # تطبیق خودکار سایز فونت تا متن حتماً در ۱ خط جا بگیرد
    chosen_font = load_font("bold", int(round(font_min * sc)))
    text_w = 0
    for sz_base in range(font_base, font_min - 1, -2):
        f = load_font("bold", max(16, int(round(sz_base * sc))))
        td, kw = prepare_text_and_kwargs(clean, is_rtl=True)
        bb = probe.textbbox((0, 0), td, font=f, **kw)
        tw = bb[2] - bb[0]
        if tw + pad_total <= max_w:
            chosen_font = f
            text_w = tw
            break
    else:
        td, kw = prepare_text_and_kwargs(clean, is_rtl=True)
        bb = probe.textbbox((0, 0), td, font=chosen_font, **kw)
        text_w = bb[2] - bb[0]

    strip_w = min(max_w, max(text_w + pad_total, min_w))

    margin = max(12, int(round(26 * sc)))
    jv = 4.0 * sc
    jh = 8.0 * sc
    poly = _make_torn_polygon(strip_w, strip_h, margin, jv, jh, pts_x=48, pts_y=16, seed=seed)

    # بوم کار با فضای کافی برای سایه و لبه بیرونی
    extra = int(round(26 * sc))
    cw, ch = strip_w + extra * 2, strip_h + extra * 2
    poly_sh = [(x + extra, y + extra) for x, y in poly]

    out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

    # لایه ۱: سایه زیر کاغذ روی ویدئو (+6px, +12px، مشکی alpha=215، blur=10)
    sh_dx, sh_dy = int(round(6 * sc)), int(round(12 * sc))
    shadow_lay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(shadow_lay).polygon([(x + sh_dx, y + sh_dy) for x, y in poly_sh], fill=(0, 0, 0, 215))
    shadow_lay = shadow_lay.filter(ImageFilter.GaussianBlur(radius=max(2, round(10 * sc))))
    out = Image.alpha_composite(out, shadow_lay)

    # لایه ۲: لبه نازک زغالی بیرونی (گسترش +5px افقی، +4px عمودی، alpha=250)
    cx_p, cy_p = cw / 2.0, ch / 2.0
    ex_x, ex_y = 5.0 * sc, 4.0 * sc
    outer_poly = []
    for x, y in poly_sh:
        dx = ex_x if x >= cx_p else -ex_x
        dy = ex_y if y >= cy_p else -ex_y
        outer_poly.append((x + dx, y + dy))
    charcoal_lay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(charcoal_lay).polygon(outer_poly, fill=charcoal_rgb + (250,))
    out = Image.alpha_composite(out, charcoal_lay)

    # لایه ۳: بدنه تمیز کاغذ + گرادینت سوختگی نرم فقط در لبه‌های داخلی (برش با ماسک کاغذ)
    paper_mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(paper_mask).polygon(poly_sh, fill=255)

    paper_body = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(paper_body).polygon(poly_sh, fill=center_rgb + (255,))

    burn_layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    bd = ImageDraw.Draw(burn_layer)
    closed_poly = poly_sh + [poly_sh[0]]
    bd.line(closed_poly, fill=warm_rgb + (235,), width=max(4, int(round(26 * sc))), joint="curve")
    bd.line(closed_poly, fill=charcoal_rgb + (245,), width=max(2, int(round(9 * sc))), joint="curve")
    burn_layer = burn_layer.filter(ImageFilter.GaussianBlur(radius=max(2, round(11 * sc))))

    # برش دقیق سوختگی روی ماسک کاغذ تا مرکز ۱۰۰٪ صاف و تمیز بماند
    paper_combined = Image.alpha_composite(paper_body, burn_layer)
    r_c, g_c, b_c, a_c = paper_combined.split()
    clipped_a = Image.fromarray(np.minimum(np.array(a_c), np.array(paper_mask)))
    paper_clipped = Image.merge("RGBA", (r_c, g_c, b_c, clipped_a))
    out = Image.alpha_composite(out, paper_clipped)

    # چاپ متن وسط‌چین با جابه‌جایی 10px به بالا
    td_final, kw_final = prepare_text_and_kwargs(clean, is_rtl=True)
    tdraw = ImageDraw.Draw(out)
    stroke_px = max(1, int(round(stroke_w_base * sc)))
    tbb = tdraw.textbbox((0, 0), td_final, font=chosen_font, stroke_width=stroke_px, **kw_final)
    tx = (cw - (tbb[0] + tbb[2])) // 2
    ty = (ch - (tbb[1] + tbb[3])) // 2 - int(round(10 * sc))

    if text_shadow:
        ts_dx, ts_dy = int(round(4 * sc)), int(round(6 * sc))
        tdraw.text(
            (tx + ts_dx, ty + ts_dy), td_final, font=chosen_font,
            fill=(0, 0, 0, 230), stroke_width=stroke_px, stroke_fill=(0, 0, 0, 230), **kw_final
        )
    tdraw.text(
        (tx, ty), td_final, font=chosen_font,
        fill=text_rgb + (255,), stroke_width=stroke_px, stroke_fill=stroke_rgb + (255,), **kw_final
    )
    return out


def render_burnt_paper_hook_png(line1: str, line2: str, out_path: str, width: int = 1080, height: int = 1920) -> str:
    """تولید لایه شفاف PNG قلاب دوطبقه کاغذ سوخته مطابق مشخصات دقیق و مقیاس‌پذیر."""
    sc = width / 1080.0
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # نوار اول (بالا — کاغذ کرم قدیمی)
    top_strip = _render_single_burnt_strip(
        text=line1, sc=sc,
        min_w_base=600, max_w_base=1020, h_base=188,
        center_rgb=(248, 234, 202), warm_rgb=(135, 78, 30), charcoal_rgb=(38, 18, 6),
        text_rgb=(15, 10, 8), stroke_rgb=(255, 250, 240), stroke_w_base=4,
        font_base=64, font_min=42, text_shadow=False, seed=101,
    )

    # نوار دوم (پایین — کاغذ قرمز زرشکی)
    bot_strip = _render_single_burnt_strip(
        text=line2, sc=sc,
        min_w_base=630, max_w_base=1030, h_base=198,
        center_rgb=(196, 18, 24), warm_rgb=(95, 10, 12), charcoal_rgb=(22, 4, 4),
        text_rgb=(255, 232, 20), stroke_rgb=(12, 8, 8), stroke_w_base=7,
        font_base=70, font_min=44, text_shadow=True, seed=202,
    )

    extra = int(round(26 * sc))
    top_y = int(round(height * (0.18 if width > height else 0.25))) - extra
    bot_y = top_y + int(round(124 * sc))

    # ترتیب لایه‌ها: ابتدا نوار قرمز پایین، سپس نوار کرم بالا روی آن برای هم‌پوشانی طبیعی
    bot_x = (width - bot_strip.width) // 2
    top_x = (width - top_strip.width) // 2
    canvas.alpha_composite(bot_strip, (bot_x, bot_y))
    canvas.alpha_composite(top_strip, (top_x, top_y))

    canvas.save(out_path, format="PNG")
    return out_path


# ==================== موتور گوینده فارسی اختصاصی (اعراب‌گذاری + بانک تلفظ + DSP رادیویی) ====================
def apply_pronunciation_dict(text: str) -> str:
    merged = dict(DEFAULT_PRONUNCIATION_DICT)
    merged.update(CONFIG.get("custom_pronunciations") or {})
    out = text
    for k in sorted(merged.keys(), key=len, reverse=True):
        if k in out:
            out = out.replace(k, merged[k])
    return out


async def diacritize_persian_for_tts(session: aiohttp.ClientSession, text: str) -> str:
    base = apply_pronunciation_dict(strip_emojis_for_font(text))
    if not GEMINI_API_KEY or not base:
        return base
    res = await gemini_generate(session, f"{DIACRITIZE_PROMPT}\n\nمتن:\n{base}")
    return apply_pronunciation_dict(res) if res else base


def probe_audio_duration(audio_path: str) -> float:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return max(0.5, float(json.loads(res.stdout).get("format", {}).get("duration", 2.0)))
    except Exception:
        return 2.0


async def synthesize_broadcast_tts(session: aiohttp.ClientSession, raw_text: str, out_wav: str, work_dir: str) -> float:
    """تولید صدای شفاف، شمرده و گرم گوینده خبری با نرخ نمونه‌برداری اصلاح‌شده (بدون تند شدن صدا)."""
    if not HAS_EDGE_TTS or edge_tts is None:
        return 0.0

    diac_text = await diacritize_persian_for_tts(session, raw_text)
    raw_mp3 = os.path.join(work_dir, f"tts_raw_{int(time.time()*1000)}_{random.randint(10,99)}.mp3")

    profile = CONFIG.get("tts_profile", "studio_baritone")
    if profile == "studio_anchor_f":
        voice_name, rate_str, pitch_str = "fa-IR-DilaraNeural", "-4%", "-2Hz"
        # ابتدا تبدیل دقیق از 24kHz به 44.1kHz تا سرعت صدا کاملاً طبیعی بماند
        dsp_chain = (
            "aresample=44100,"
            "asetrate=44100*0.985,aresample=44100,atempo=1.015,"
            "highpass=f=85,"
            "equalizer=f=220:t=q:w=1.2:g=2.0,"
            "equalizer=f=3200:t=q:w=1.4:g=2.2,"
            "acompressor=threshold=-18dB:ratio=2.8:attack=15:release=140,"
            "loudnorm=I=-15:TP=-1.5:LRA=8"
        )
    else:
        # گوینده مرد خبری با سرعت شمرده (-4%) و گرمای ملایم رادیویی
        voice_name, rate_str, pitch_str = "fa-IR-FaridNeural", "-4%", "-3Hz"
        dsp_chain = (
            "aresample=44100,"
            "asetrate=44100*0.975,aresample=44100,atempo=1.026,"
            "highpass=f=80,"
            "equalizer=f=170:t=q:w=1.1:g=2.8,"
            "equalizer=f=2900:t=q:w=1.4:g=2.2,"
            "lowpass=f=11500,"
            "acompressor=threshold=-18dB:ratio=3.0:attack=14:release=130,"
            "loudnorm=I=-15:TP=-1.5:LRA=8"
        )

    try:
        comm = edge_tts.Communicate(diac_text, voice=voice_name, rate=rate_str, pitch=pitch_str)
        await comm.save(raw_mp3)
        if not os.path.exists(raw_mp3) or os.path.getsize(raw_mp3) < 500:
            return 0.0
        run_ffmpeg([
            "ffmpeg", "-y", "-i", raw_mp3,
            "-af", dsp_chain,
            "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", out_wav,
        ])
        return probe_audio_duration(out_wav)
    except Exception:
        return 0.0


# ==================== کیبوردهای دسته‌بندی‌شده جدید (منوی اصلی خلوت ۲×۲) ====================
def kb_main_menu() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_CAT_REELS}, {"text": BTN_CAT_STORY}],
            [{"text": BTN_CAT_QUICK}, {"text": BTN_CAT_SETTINGS}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_cat_reels() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_INCIDENT}, {"text": BTN_MAP}],
            [{"text": BTN_DAILY60}, {"text": BTN_VIDEO}],
            [{"text": BTN_HOOK_ONLY}, {"text": BTN_AUDIO}],
            [{"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_cat_story() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_CARD_STORY}, {"text": BTN_CARD_POST}],
            [{"text": BTN_CAPTION}, {"text": BTN_SHADOWBAN}],
            [{"text": BTN_OCCASION}, {"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_cat_quick() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_ONE_TAP}],
            [{"text": BTN_CLEAN_LOGO}, {"text": BTN_WEATHER}],
            [{"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_cat_settings() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_STUDIO_OPTS}, {"text": BTN_THEME}],
            [{"text": BTN_PRONOUNCE}, {"text": BTN_STATUS}],
            [{"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_studio_opts() -> dict:
    def st(b):
        return "روشن ✅" if b else "خاموش ❌"

    v_lbl = "گوینده مرد گرم" if CONFIG.get("tts_profile") != "studio_anchor_f" else "گوینده زن رسمی"
    return {
        "keyboard": [
            [{"text": f"🔥 قلاب کاغذ سوخته: {st(CONFIG['use_burnt_hook'])}"}, {"text": f"🖼️ قاب ریلز: {st(CONFIG['use_repo_frame'])}"}],
            [{"text": f"🧩 کاور گرید ۴:۵: {st(CONFIG['make_grid_cover'])}"}, {"text": f"📰 زیرنویس متحرک: {st(CONFIG['video_ticker'])}"}],
            [{"text": f"🧬 اصالت‌سازی: {st(CONFIG['video_antidup'])}"}, {"text": f"👤 ردیابی چهره: {st(CONFIG['video_facetrack'])}"}],
            [{"text": f"🏷️ اند-اسکرین فالو: {st(CONFIG['video_brand'])}"}, {"text": f"🎙️ صدای گوینده: {v_lbl}"}],
            [{"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_theme_menu() -> dict:
    return {
        "keyboard": [
            [{"text": THEMES["navy"]["btn"]}, {"text": THEMES["incident"]["btn"]}],
            [{"text": THEMES["mourning"]["btn"]}, {"text": THEMES["sports"]["btn"]}],
            [{"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_daily_collect() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_STYLE_BROADCAST}, {"text": BTN_STYLE_SPLIT}],
            [{"text": BTN_STYLE_EDITORIAL}, {"text": BTN_STYLE_KINETIC}],
            [{"text": BTN_STYLE_LIVE}, {"text": BTN_STYLE_HOLOGRAM}],
            [{"text": BTN_CLEAR_DAILY}, {"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_hook_confirm() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_HOOK_CONFIRM}],
            [{"text": BTN_HOOK_EDIT}, {"text": BTN_HOOK_REGEN}],
            [{"text": BTN_CANCEL}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_logo_corners() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_CORNER_TL}, {"text": BTN_CORNER_TR}],
            [{"text": BTN_CORNER_BL}, {"text": BTN_CORNER_BR}],
            [{"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_shadowban_actions() -> dict:
    return {
        "keyboard": [[{"text": BTN_SAFE_REWRITE}], [{"text": BTN_BACK}]],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_cancel(extra_row: list = None) -> dict:
    rows = []
    if extra_row:
        rows.append(extra_row)
    rows.append([{"text": BTN_CANCEL}])
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


def build_status_text() -> str:
    now_str = to_persian_digits(get_tehran_now().strftime("%H:%M"))
    t_name = THEMES[CONFIG["theme"]]["name"]
    ai_st = "متصل ✅" if GEMINI_API_KEY else "کلید GEMINI_API_KEY ثبت نشده ⚠️"
    r_fr = find_repo_reel_frame()
    lg = find_repo_logo()
    inc_mp3 = find_repo_audio("incident")
    tts_st = "فعال ✅ (اعراب‌گذاری + DSP رادیویی)" if HAS_EDGE_TTS else "غیرفعال"

    return (
        f"🎬 استودیوی تحریریه {BRAND_HANDLE}\n\n"
        f"🕒 ساعت تهران: {now_str} | 🎨 {t_name}\n"
        f"🏛️ لوگوی دروازه قرآن: {'فعال ✅ (' + os.path.basename(lg) + ')' if lg else 'آیکون پیش‌فرض'}\n"
        f"🖼️ قاب ریلز ۳ باکسه: {'فعال ✅' if r_fr else 'آپلود نشده (reel_frame.png)'}\n"
        f"🔥 قلاب کاغذ سوخته ۳ ثانیه‌ای: {'روشن ✅' if CONFIG['use_burnt_hook'] else 'خاموش ❌'}\n"
        f"🚨 موزیک حادثه‌ای: {os.path.basename(inc_mp3) if inc_mp3 else 'آژیر داخلی'}\n"
        f"🎙️ گوینده فارسی اختصاصی: {tts_st}\n"
        f"🧠 هوش مصنوعی سردبیری: {ai_st}\n"
        f"📦 صف جمع‌بندی روزانه: {to_persian_digits(str(len(DAILY_ITEMS)))} خبر\n\n"
        "یکی از ۴ اتاق کار زیر را از منوی پایین انتخاب کنید:"
    )


# ==================== ارتباط با Telegram API و ذخیره تنظیمات ====================
async def tg_api(session: aiohttp.ClientSession, method: str, payload: dict):
    if not BOT_TOKEN:
        return None
    url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){BOT_TOKEN}/{method}"
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            return await resp.json()
    except Exception:
        return None


async def send_message(session: aiohttp.ClientSession, chat_id: str, text: str, reply_markup: dict = None):
    if not chat_id:
        return None
    payload = {"chat_id": chat_id, "text": text[:4090]}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await tg_api(session, "sendMessage", payload)


async def send_photo_file(session: aiohttp.ClientSession, chat_id: str, path: str, caption: str = "", reply_markup: dict = None):
    url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){BOT_TOKEN}/sendPhoto"
    form = aiohttp.FormData()
    form.add_field("chat_id", str(chat_id))
    if caption:
        form.add_field("caption", caption[:1000])
    if reply_markup:
        form.add_field("reply_markup", json.dumps(reply_markup, ensure_ascii=False))
    with open(path, "rb") as f:
        form.add_field("photo", f.read(), filename=os.path.basename(path), content_type="image/jpeg")
    async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=60)) as resp:
        return await resp.json()


async def send_video_file(session: aiohttp.ClientSession, chat_id: str, path: str, caption: str = "", reply_markup: dict = None):
    url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){BOT_TOKEN}/sendVideo"
    form = aiohttp.FormData()
    form.add_field("chat_id", str(chat_id))
    form.add_field("supports_streaming", "true")
    if caption:
        form.add_field("caption", caption[:1000])
    if reply_markup:
        form.add_field("reply_markup", json.dumps(reply_markup, ensure_ascii=False))
    with open(path, "rb") as f:
        form.add_field("video", f.read(), filename=os.path.basename(path), content_type="video/mp4")
    async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=180)) as resp:
        return await resp.json()


async def download_tg_file(session: aiohttp.ClientSession, file_id: str, ext: str = ".bin") -> str:
    info = await tg_api(session, "getFile", {"file_id": file_id})
    if not info or not info.get("ok"):
        return ""
    file_path = info["result"]["file_path"]
    dl_url = f"[https://api.telegram.org/file/bot](https://api.telegram.org/file/bot){BOT_TOKEN}/{file_path}"
    out_path = os.path.join(TMP_ROOT, f"dl_{int(time.time()*1000)}_{random.randint(100,999)}{ext}")
    async with session.get(dl_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
        if resp.status != 200:
            return ""
        data = await resp.read()
    with open(out_path, "wb") as f:
        f.write(data)
    return out_path


async def load_config_from_pin(session: aiohttp.ClientSession):
    global CONFIG_MSG_ID
    if not ADMIN_ID:
        return
    res = await tg_api(session, "getChat", {"chat_id": ADMIN_ID})
    if not res or not res.get("ok"):
        return
    pinned = res.get("result", {}).get("pinned_message")
    if not pinned:
        return
    txt = pinned.get("text", "")
    if txt.startswith(CONFIG_PIN_PREFIX):
        CONFIG_MSG_ID = pinned.get("message_id")
        try:
            saved = json.loads(txt[len(CONFIG_PIN_PREFIX):].strip())
            if isinstance(saved, dict):
                for k in CONFIG:
                    if k in saved:
                        CONFIG[k] = saved[k]
        except Exception:
            pass


async def save_config_to_pin(session: aiohttp.ClientSession):
    global CONFIG_MSG_ID
    if not ADMIN_ID:
        return
    payload_text = CONFIG_PIN_PREFIX + "\n" + json.dumps(CONFIG, ensure_ascii=False)
    if CONFIG_MSG_ID:
        res = await tg_api(session, "editMessageText", {"chat_id": ADMIN_ID, "message_id": CONFIG_MSG_ID, "text": payload_text})
        if res and res.get("ok"):
            return
    sent = await send_message(session, ADMIN_ID, payload_text)
    if sent and sent.get("ok"):
        CONFIG_MSG_ID = sent["result"]["message_id"]
        await tg_api(session, "pinChatMessage", {"chat_id": ADMIN_ID, "message_id": CONFIG_MSG_ID, "disable_notification": True})


# ==================== موتور هوش مصنوعی Gemini ====================
async def gemini_upload_file(session: aiohttp.ClientSession, file_path: str, mime_type: str) -> str:
    file_size = os.path.getsize(file_path)
    init_url = f"[https://generativelanguage.googleapis.com/upload/v1beta/files?key=](https://generativelanguage.googleapis.com/upload/v1beta/files?key=){GEMINI_API_KEY}"
    headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(file_size),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "Content-Type": "application/json",
    }
    async with session.post(init_url, headers=headers, json={"file": {"display_name": os.path.basename(file_path)}}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        upload_url = resp.headers.get("X-Goog-Upload-URL")
        if not upload_url:
            return ""
    with open(file_path, "rb") as f:
        raw = f.read()
    up_headers = {"Content-Length": str(file_size), "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"}
    async with session.post(upload_url, headers=up_headers, data=raw, timeout=aiohttp.ClientTimeout(total=120)) as resp:
        if resp.status != 200:
            return ""
        info = await resp.json()
    file_obj = info.get("file", {})
    file_uri, file_name, state = file_obj.get("uri", ""), file_obj.get("name", ""), file_obj.get("state", "")
    for _ in range(30):
        if state == "ACTIVE" or not file_name:
            break
        await asyncio.sleep(2)
        st_url = f"[https://generativelanguage.googleapis.com/v1beta/](https://generativelanguage.googleapis.com/v1beta/){file_name}?key={GEMINI_API_KEY}"
        async with session.get(st_url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                d = await r.json()
                state = d.get("state", "ACTIVE")
                if state == "FAILED":
                    return ""
    return file_uri


async def gemini_generate(session: aiohttp.ClientSession, prompt: str, media_path: str = None, mime_type: str = None) -> str:
    if not GEMINI_API_KEY:
        return ""
    parts = []
    if media_path and os.path.exists(media_path) and mime_type:
        size = os.path.getsize(media_path)
        if mime_type.startswith("image/") and size < 4 * 1024 * 1024:
            with open(media_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            parts.append({"inline_data": {"mime_type": mime_type, "data": b64}})
        else:
            uri = await gemini_upload_file(session, media_path, mime_type)
            if uri:
                parts.append({"file_data": {"mime_type": mime_type, "file_uri": uri}})
    parts.append({"text": prompt})
    body = {"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.4}}

    tried = []
    for model in GEMINI_MODELS:
        if not model or model in tried:
            continue
        tried.append(model)
        url = f"[https://generativelanguage.googleapis.com/v1beta/models/](https://generativelanguage.googleapis.com/v1beta/models/){model}:generateContent?key={GEMINI_API_KEY}"
        try:
            async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    cands = data.get("candidates", [])
                    if cands:
                        out = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", [])).strip()
                        if out:
                            return clean_caption_markdown(out)
        except Exception:
            continue
    return ""


async def generate_editorial_caption(
    session: aiohttp.ClientSession, news_text: str = "", media_path: str = None, mime_type: str = None, force_incident: bool = False
) -> str:
    extra = "\nتوجه ویژه: این خبر یک خبر فوری/حادثه‌ای است؛ تیتر خط اول حتماً با «⭕ فوری | ...» شروع شود.\n" if force_incident else ""
    full_prompt = (
        f"{EDITORIAL_CAPTION_PROMPT}{extra}\n\n"
        f"متن خبر و منبع (در صورت ارسال فیلم/عکس/صدا، تصویر و صدای فایل را دقیق تحلیل کن):\n"
        f"{news_text or 'محتوای داخل فایل پیوست‌شده را کامل ببین و بشنو و بر اساس آن کپشن ۶ بخشی دقیق بنویس.'}"
    )
    res = await gemini_generate(session, full_prompt, media_path=media_path, mime_type=mime_type)
    if res:
        return res
    hl = strip_emojis_for_font(news_text.splitlines()[0] if news_text else "گزارش خبری جدید")[:70]
    prefix = "⭕ فوری |" if force_incident else "⭕ خبر شیراز |"
    return (
        f"{prefix} {hl}\n\n"
        f"{(news_text or 'جزئیات تکمیلی این خبر به‌زودی منتشر می‌شود.')[:220]}\n\n"
        "💬 نظر شما درباره این موضوع چیست؟ (۱: موافقم | ۲: مخالفم)\n\n"
        "🔔 پوشش لحظه‌ای اخبار شیراز و استان فارس در استوری‌ها و ریلزها\n"
        "📲 برای پیگیری ادامه خبر فالو کنید: @shirazlastnews\n\n"
        "#شیراز #استان_فارس #اخبار_شیراز #خبر_فوری #فارس"
    )


async def generate_burnt_hook_text(session: aiohttp.ClientSession, news_text: str, media_path: str = None, mime_type: str = None) -> tuple:
    """تولید هوشمند دو سطر قلاب کاغذ سوخته توسط Gemini + اعتبارسنجی سخت‌گیرانه فارسی."""
    if GEMINI_API_KEY:
        prompt = f"{BURNT_HOOK_PROMPT}\n\nمتن یا موضوع خبر:\n{news_text or 'محتوای فایل پیوست‌شده را ببین و دقیق‌ترین قلاب خبری دوطبقه را بساز.'}"
        raw = await gemini_generate(session, prompt, media_path=media_path, mime_type=mime_type)
        if raw:
            m = re.search(r"\{.*?\}", raw, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(0))
                    l1 = str(data.get("hook_line1", "")).strip()
                    l2 = str(data.get("hook_line2", "")).strip()
                    if l1 and l2:
                        return validate_and_balance_burnt_hook(l1, l2, fallback_text=news_text)
                except Exception:
                    pass
    return validate_and_balance_burnt_hook("", "", fallback_text=news_text)


async def extract_news_parts(session: aiohttp.ClientSession, news_text: str, is_incident: bool = False) -> tuple:
    clean_input = strip_emojis_for_font(news_text)
    if GEMINI_API_KEY and clean_input:
        p = (
            "از خبر زیر دقیقاً ۳ خط بدون هیچ ایموجی، علامت ستاره یا شماره بساز:\n"
            "خط ۱: برچسب بسیار کوتاه (۱ تا ۲ کلمه مثل: خبر فوری، حوادث، خبر شیراز، ورزشی، اقتصادی)\n"
            "خط ۲: تیتر اصلی کامل، رسا و کوتاه (حداکثر ۱۰ کلمه، بدون بریده شدن جمله)\n"
            "خط ۳: زیرتیتر تکمیلی دقیق در یک جمله کوتاه (حداکثر ۱۶ کلمه)\n\n"
            f"خبر:\n{clean_input}"
        )
        out = await gemini_generate(session, p)
        lines = [strip_emojis_for_font(ln.lstrip("•-*0123456789.: ")) for ln in out.splitlines() if strip_emojis_for_font(ln)]
        if len(lines) >= 3:
            return ("خبر فوری" if is_incident else lines[0][:22]), lines[1][:105], lines[2][:150]
        if len(lines) == 2:
            return ("خبر فوری" if is_incident else lines[0][:22]), lines[1][:105], f"پوشش لحظه‌ای اخبار شیراز و فارس | {BRAND_HANDLE}"
    raw_lines = [strip_emojis_for_font(ln) for ln in (news_text or "").splitlines() if strip_emojis_for_font(ln)]
    hl = raw_lines[0][:100] if raw_lines else BRAND_TITLE_FA
    sub = raw_lines[1][:145] if len(raw_lines) > 1 else f"پوشش لحظه‌ای اخبار شیراز و فارس | {BRAND_HANDLE}"
    return ("خبر فوری" if is_incident else "خبر شیراز"), hl, sub


async def rewrite_shadowban_safe(session: aiohttp.ClientSession, caption_text: str) -> str:
    if not GEMINI_API_KEY:
        safe = caption_text
        for bad, alt in SENSITIVE_WORDS.items():
            safe = safe.replace(bad, alt.split("/")[0].strip())
        return safe
    p = (
        "متن کپشن اینستاگرام زیر را با حفظ دقیق ساختار ۶ بخشی، لحن رسمی، دعوت به فالو و ۵ هشتگ، "
        "طوری بازنویسی کن که تمام کلمات حساس و خطرناک برای الگوریتم اینستاگرام (شدوبن در حوادث و اخبار نظامی) "
        "با معادل‌های رسمی و ایمن جایگزین شوند. هیچ مارک‌داون یا توضیح اضافه‌ای ننویس:\n\n"
        f"{caption_text}"
    )
    return (await gemini_generate(session, p)) or caption_text
    # ==================== نوار زیرنویس متحرک شبکه خبر ====================
def build_scrolling_ticker_strip(
    text: str, duration_sec: float, bg_color=(185, 28, 28, 240), text_color=(255, 255, 255, 255), height: int = 74
) -> Image.Image:
    clean = strip_emojis_for_font(text) or f"{BRAND_TITLE_FA} — پوشش لحظه‌ای اخبار شیراز و استان فارس"
    item = f"   ●   {clean}   ●   {BRAND_TITLE_FA} ({BRAND_HANDLE})"
    font = load_font("bold", 34)

    probe = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    pd = ImageDraw.Draw(probe)
    t_draw, kw = prepare_text_and_kwargs(item, is_rtl=True)
    bb = pd.textbbox((0, 0), t_draw, font=font, **kw)
    unit_w = max(420, (bb[2] - bb[0]) + 40)

    needed_w = min(14000, max(2600, int(duration_sec * 175) + 1800))
    reps = max(2, (needed_w // unit_w) + 2)
    full_text = item * reps
    ft_draw, fkw = prepare_text_and_kwargs(full_text, is_rtl=True)
    fbb = pd.textbbox((0, 0), ft_draw, font=font, **fkw)
    strip_w = max(needed_w, (fbb[2] - fbb[0]) + 120)

    strip = Image.new("RGBA", (strip_w, height), bg_color)
    sd = ImageDraw.Draw(strip)
    sd.rectangle([(0, 0), (strip_w, 4)], fill=(250, 204, 21, 255))
    sd.rectangle([(0, height - 4), (strip_w, height)], fill=(250, 204, 21, 255))

    ty = (height - (fbb[3] - fbb[1])) // 2 - fbb[1]
    sd.text((strip_w - 40 - fbb[2], ty), ft_draw, font=font, fill=text_color, **fkw)
    return strip


# ==================== ۱. استوری رسمی پیج، کارت پست و کاور گرید ۴:۵ ====================
def draw_quran_gate_fallback(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 112):
    w_c = (255, 255, 255, 255)
    draw.rectangle([(x + 12, y + 26), (x + size - 12, y + size - 12)], outline=w_c, width=4)
    draw.rectangle([(x + 30, y + 10), (x + size - 30, y + 26)], outline=w_c, width=4)
    draw.rounded_rectangle([(x + 38, y + 48), (x + size - 38, y + size - 10)], radius=18, outline=w_c, width=4)
    draw.rounded_rectangle([(x + 18, y + 58), (x + 34, y + size - 10)], radius=8, outline=w_c, width=3)
    draw.rounded_rectangle([(x + size - 34, y + 58), (x + size - 18, y + size - 10)], radius=8, outline=w_c, width=3)


def render_brand_story_sync(photo_path: str, badge: str, headline: str, subtext: str, source_name: str = "") -> str:
    """تولید دقیق استوری مطابق هویت بصری رسمی @ShirazLastNews."""
    w, h = 1080, 1920
    canvas = Image.new("RGBA", (w, h), (19, 20, 23, 255))
    draw = ImageDraw.Draw(canvas)

    # ۱. نوار قرمز اریب بالا سمت راست
    draw.polygon([(535, 42), (1080, 42), (1080, 212), (462, 212)], fill=(204, 18, 28, 255))
    top_label = strip_emojis_for_font(badge) or "خبر فوری"
    draw_centered_block_in_box(draw, (530, 52, 1052, 202), top_label, "bold", (255, 255, 255, 255), max_size=62, min_size=34, max_lines=1, align="center", pad_x=16, pad_y=6)

    # ۲. لوگوی دروازه قرآن بالا سمت چپ
    logo_path = find_repo_logo()
    if logo_path:
        try:
            lg = Image.open(logo_path).convert("RGBA")
            lg.thumbnail((138, 108), Image.Resampling.LANCZOS)
            canvas.alpha_composite(lg, (78 + (138 - lg.width) // 2, 38 + (108 - lg.height) // 2))
        except Exception:
            draw_quran_gate_fallback(draw, 84, 38, 110)
    else:
        draw_quran_gate_fallback(draw, 84, 38, 110)

    # ۳. نشانگر LIVE زیر لوگو
    draw.rounded_rectangle([(68, 158), (222, 212)], radius=27, fill=(28, 29, 34, 255), outline=(48, 50, 56, 255), width=2)
    draw.ellipse([(88, 173), (112, 197)], fill=(212, 28, 38, 255))
    draw_rtl_text(draw, (124, 169), "LIVE", load_font("bold", 28), (196, 44, 52, 255), align="left", shadow=False, is_rtl=False)

    # ۴. کادر اصلی عکس
    px1, py1, px2, py2 = 46, 276, 1034, 1236
    pw, ph = px2 - px1, py2 - py1
    if photo_path and os.path.exists(photo_path):
        pic = fit_cover(Image.open(photo_path).convert("RGB"), pw, ph)
    else:
        pic = Image.new("RGB", (pw, ph), THEMES.get(CONFIG["theme"], THEMES["navy"])["bg"])
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (pw, ph)], radius=34, fill=255)
    canvas.paste(pic, (px1, py1), mask)
    draw.rounded_rectangle([(px1, py1), (px2, py2)], radius=34, outline=(105, 108, 118, 220), width=3)

    # ۵. کارت سفید هم‌پوشان روی لبه پایینی عکس
    wx1, wy1, wx2, wy2 = 66, 1142, 1014, 1720
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([(wx1, wy1 + 10), (wx2, wy2 + 12)], radius=38, fill=(0, 0, 0, 125))
    sh = sh.filter(ImageFilter.GaussianBlur(radius=16))
    canvas = Image.alpha_composite(canvas, sh)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([(wx1, wy1), (wx2, wy2)], radius=38, fill=(255, 255, 255, 255))

    # ۶. تیتر مشکی و خلاصه داخل کارت سفید
    text_max_w = (wx2 - wx1) - 96
    hl_font, hl_lines, hl_lh = fit_text_in_box(draw, headline or BRAND_TITLE_FA, "bold", text_max_w, 225, max_size=50, min_size=30, max_lines=3, line_spacing=1.38)
    cur_y = wy1 + 46
    for ln in hl_lines:
        draw_rtl_text(draw, (wx2 - 48, cur_y), ln, hl_font, (18, 20, 24, 255), align="right", shadow=False)
        cur_y += hl_lh

    if subtext:
        rem_h = max(65, (wy2 - 148) - (cur_y + 14))
        sub_font, sub_lines, sub_lh = fit_text_in_box(draw, subtext, "regular", text_max_w, rem_h, max_size=35, min_size=24, max_lines=3, line_spacing=1.42)
        sy = cur_y + 18
        for sl in sub_lines:
            draw_rtl_text(draw, (wx2 - 48, sy), sl, sub_font, (38, 42, 48, 255), align="right", shadow=False)
            sy += sub_lh

    # ۷. کپسول قرمز گوشه پایین راست
    bx1, by1, bx2, by2 = 768, 1594, 962, 1662
    draw.rounded_rectangle([(bx1, by1), (bx2, by2)], radius=22, fill=(204, 18, 28, 255))
    short_tag = "فوری" if "فوری" in top_label else (top_label.split("|")[0].strip().split()[-1] if top_label.split() else "فوری")
    draw_centered_block_in_box(draw, (bx1, by1, bx2, by2), short_tag[:12], "bold", (255, 255, 255, 255), max_size=30, min_size=20, max_lines=1, align="center", pad_x=10, pad_y=4)

    # ۸. تاریخ و آیدی گوشه پایین چپ
    jnow = jdatetime.datetime.fromgregorian(datetime=get_tehran_now())
    date_slash = to_persian_digits(f"{jnow.year:04d}/{jnow.month:02d}/{jnow.day:02d}")
    f_meta = load_font("bold", 29)
    d_txt, d_kw = prepare_text_and_kwargs(date_slash, is_rtl=False)
    dbb = draw.textbbox((0, 0), d_txt, font=f_meta, **d_kw)
    draw_rtl_text(draw, (wx1 + 48, 1612), date_slash, f_meta, (95, 100, 110, 255), align="left", shadow=False, is_rtl=False)
    draw_rtl_text(draw, (wx1 + 48 + (dbb[2] - dbb[0]) + 10, 1612), f"| {BRAND_HANDLE}", f_meta, (95, 100, 110, 255), align="left", shadow=False, is_rtl=False)

    # ۹. نوار فوتر پایین صفحه با برش قرمز اریب سمت چپ
    draw.rectangle([(0, 1794), (w, 1884)], fill=(36, 39, 44, 255))
    draw.polygon([(0, 1794), (275, 1794), (235, 1884), (0, 1884)], fill=(204, 18, 28, 255))
    src_clean = strip_emojis_for_font(source_name)
    footer_txt = f"منبع: {src_clean}  |  آخرین خبرهای شیراز و استان فارس" if src_clean else "آخرین خبرهای شیراز و استان فارس"
    draw_centered_block_in_box(draw, (285, 1802, 1032, 1876), footer_txt, "bold", (245, 247, 250, 255), max_size=30, min_size=20, max_lines=1, align="right", pad_x=6, pad_y=4)

    out_path = os.path.join(TMP_ROOT, f"story_brand_{int(time.time()*1000)}.jpg")
    canvas.convert("RGB").save(out_path, quality=94)
    return out_path


def render_news_card_sync(photo_path: str, badge: str, headline: str, subtext: str, fmt: str = "post", theme_key: str = "navy", source_name: str = "") -> str:
    if fmt == "story":
        return render_brand_story_sync(photo_path, badge, headline, subtext, source_name=source_name)

    theme = THEMES.get(theme_key, THEMES["navy"])
    w, h = 1080, 1350
    canvas = fit_cover(Image.open(photo_path).convert("RGB"), w, h).convert("RGBA") if (photo_path and os.path.exists(photo_path)) else Image.new("RGBA", (w, h), theme["bg"] + (255,))

    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad)
    bg_r, bg_g, bg_b = theme["bg"]
    for y in range(260):
        gdraw.line([(0, y), (w, y)], fill=(bg_r, bg_g, bg_b, int(195 * (1 - y / 260))))
    for y in range(int(h * 0.40), h):
        ratio = (y - int(h * 0.40)) / (h - int(h * 0.40))
        gdraw.line([(0, y), (w, y)], fill=(bg_r, bg_g, bg_b, int(250 * (ratio ** 1.3))))

    canvas = Image.alpha_composite(canvas, grad)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([(0, 0), (w, 16)], fill=theme["accent"] + (255,))

    jnow = jdatetime.datetime.fromgregorian(datetime=get_tehran_now())
    date_str = to_persian_digits(f"{jnow.day} {JALALI_MONTHS[jnow.month]} {jnow.year}")
    draw_rtl_text(draw, (w - 54, 46), BRAND_TITLE_FA, load_font("bold", 34), theme["text"] + (255,), align="right")
    draw_rtl_text(draw, (54, 52), BRAND_HANDLE, load_font("regular", 28), theme["accent"] + (255,), align="left", shadow=False, is_rtl=False)
    draw_rtl_text(draw, (w - 54, 96), date_str, load_font("regular", 24), theme["subtext"] + (230,), align="right", shadow=False)

    f_title, lines, line_h = fit_text_in_box(draw, headline, "display", w - 130, 270, max_size=66, min_size=34, max_lines=4)
    block_h = max(line_h, len(lines) * line_h)
    sub_h = 110 if subtext else 0
    title_start_y = h - 210 - sub_h - block_h

    f_badge = load_font("bold", 34)
    clean_badge = strip_emojis_for_font(badge) or "خبر شیراز"
    b_txt, b_kw = prepare_text_and_kwargs(clean_badge, is_rtl=True)
    bb = draw.textbbox((0, 0), b_txt, font=f_badge, **b_kw)
    bw, bh = (bb[2] - bb[0]) + 56, 62
    badge_y = title_start_y - bh - 26

    draw.rounded_rectangle([(w - 56 - bw, badge_y), (w - 56, badge_y + bh)], radius=12, fill=theme["badge_bg"] + (255,))
    draw_rtl_text(draw, (w - 56 - bw // 2, badge_y + 10), clean_badge, f_badge, theme["badge_text"] + (255,), align="center", shadow=False)
    draw.rectangle([(w - 42, title_start_y + 8), (w - 30, title_start_y + block_h - 10)], fill=theme["accent"] + (255,))

    cur_y = title_start_y
    for ln in lines:
        draw_rtl_text(draw, (w - 64, cur_y), ln, f_title, theme["text"] + (255,), align="right", shadow=True, shadow_offset=5)
        cur_y += line_h
    if subtext:
        draw_centered_block_in_box(draw, (60, cur_y + 12, w - 64, cur_y + 115), subtext, "regular", theme["subtext"] + (240,), max_size=30, min_size=22, max_lines=2, align="right", pad_x=0, pad_y=2)

    footer_y = h - 88
    draw.line([(54, footer_y - 18), (w - 54, footer_y - 18)], fill=theme["accent"] + (130,), width=2)
    draw_rtl_text(draw, (w - 54, footer_y), "پوشش لحظه‌ای اخبار شیراز و فارس", load_font("regular", 26), theme["subtext"] + (220,), align="right", shadow=False)
    draw_rtl_text(draw, (54, footer_y), BRAND_HANDLE, load_font("bold", 28), theme["accent"] + (255,), align="left", shadow=False, is_rtl=False)

    out_path = os.path.join(TMP_ROOT, f"card_{fmt}_{int(time.time()*1000)}.jpg")
    canvas.convert("RGB").save(out_path, quality=94)
    return out_path


def render_reel_grid_cover_sync(photo_path: str, badge: str, headline: str) -> str:
    """ساخت کاور گرید ۴:۵ منظم و هم‌هویت برای نمای پروفایل اینستاگرام."""
    w, h = 1080, 1350
    if photo_path and os.path.exists(photo_path):
        canvas = fit_cover(Image.open(photo_path).convert("RGB"), w, h).convert("RGBA")
    else:
        canvas = Image.new("RGBA", (w, h), (18, 20, 26, 255))

    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(280):
        gd.line([(0, y), (w, y)], fill=(14, 16, 22, int(215 * (1 - y / 280))))
    for y in range(520, h):
        r = (y - 520) / (h - 520)
        gd.line([(0, y), (w, y)], fill=(14, 16, 22, int(248 * (r ** 1.2))))
    canvas = Image.alpha_composite(canvas, grad)
    draw = ImageDraw.Draw(canvas)

    # نوار اریب قرمز برند بالا سمت راست + لوگو بالا چپ
    draw.polygon([(630, 36), (1080, 36), (1080, 146), (578, 146)], fill=(204, 18, 28, 255))
    draw_centered_block_in_box(draw, (615, 42, 1055, 140), strip_emojis_for_font(badge) or "خبر فوری", "bold", (255, 255, 255, 255), max_size=46, min_size=26, max_lines=1)

    lg_p = find_repo_logo()
    if lg_p:
        try:
            lg = Image.open(lg_p).convert("RGBA")
            lg.thumbnail((116, 90), Image.Resampling.LANCZOS)
            canvas.alpha_composite(lg, (48, 38))
        except Exception:
            draw_quran_gate_fallback(draw, 48, 38, 86)
    else:
        draw_quran_gate_fallback(draw, 48, 38, 86)

    # تیتر مرکزی بزرگ در ناحیه امن گرید مربع (مرکز کادر)
    draw.rectangle([(w - 66, 760), (w - 50, 1135)], fill=(204, 18, 28, 255))
    draw_centered_block_in_box(draw, (64, 750, w - 86, 1145), headline or BRAND_TITLE_FA, "display", (255, 255, 255, 255), max_size=76, min_size=38, max_lines=3, align="right", shadow=True)

    # نوار فوتر قرمز و ذغالی
    draw.rectangle([(0, h - 92), (w, h)], fill=(24, 26, 32, 245))
    draw.polygon([(0, h - 92), (245, h - 92), (210, h), (0, h)], fill=(204, 18, 28, 255))
    draw_rtl_text(draw, (w - 50, h - 66), BRAND_TITLE_FA, load_font("bold", 30), (245, 247, 250, 255), align="right", shadow=False)
    draw_rtl_text(draw, (265, h - 64), BRAND_HANDLE, load_font("bold", 28), (220, 226, 236, 235), align="left", shadow=False, is_rtl=False)

    out_p = os.path.join(TMP_ROOT, f"grid_cover_{int(time.time()*1000)}.jpg")
    canvas.convert("RGB").save(out_p, quality=94)
    return out_p


def extract_video_thumbnail_sync(video_path: str, work_dir: str) -> str:
    out_jpg = os.path.join(work_dir, "vid_thumb.jpg")
    try:
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 30
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(total - 1, max(0, int(total * 0.25))))
        ok, frame = cap.read()
        cap.release()
        if ok and frame is not None:
            cv2.imwrite(out_jpg, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            return out_jpg
    except Exception:
        pass
    return ""


# ==================== ۲. ریلز فوری و حادثه‌ای (شوک + آژیر + تایپ زنده + زیرنویس) ====================
def build_incident_reel_sync(photo_path: str, headline: str, subtext: str = "") -> str:
    w, h, fps, duration = 1080, 1920, 25, 12.0
    total_frames = int(fps * duration)
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)

    bg_big = fit_cover(Image.open(photo_path).convert("RGB"), 1260, 2240) if (photo_path and os.path.exists(photo_path)) else Image.new("RGB", (1260, 2240), (24, 10, 14))
    bg_arr = np.array(bg_big, dtype=np.uint8)

    def make_siren_layer(c_left, c_right):
        lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        d.ellipse([(-280, -200), (620, 720)], fill=c_left + (200,))
        d.ellipse([(w - 620, -200), (w + 280, 720)], fill=c_right + (200,))
        d.rectangle([(0, 0), (46, h)], fill=c_left + (145,))
        d.rectangle([(w - 46, 0), (w, h)], fill=c_right + (145,))
        d.rectangle([(0, h - 500), (w, h)], fill=(185, 20, 35, 90))
        return lay.filter(ImageFilter.GaussianBlur(radius=85))

    siren_a = make_siren_layer((239, 25, 45), (29, 78, 216))
    siren_b = make_siren_layer((29, 78, 216), (239, 25, 45))

    shock_red = Image.new("RGBA", (w, h), (210, 20, 32, 200))
    sd = ImageDraw.Draw(shock_red)
    sd.rounded_rectangle([(90, 740), (w - 90, 1140)], radius=28, fill=(10, 10, 14, 240), outline=(250, 204, 21, 255), width=8)
    draw_rtl_text(sd, (w // 2, 795), "خبر فوری", load_font("display", 120), (250, 204, 21, 255), align="center")
    draw_rtl_text(sd, (w // 2, 970), "گزارش اضطراری حادثه", load_font("bold", 54), (255, 255, 255, 255), align="center")
    shock_white = Image.new("RGBA", (w, h), (255, 255, 255, 215))

    static_ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(static_ov)
    for y in range(440):
        od.line([(0, y), (w, y)], fill=(8, 6, 10, int(238 * (1 - y / 440))))
    for y in range(900, h):
        r = (y - 900) / (h - 900)
        od.line([(0, y), (w, y)], fill=(10, 4, 8, int(252 * (r ** 1.15))))

    def draw_hazard_bar(y_top, bh, c1, c2=(14, 14, 18, 255)):
        od.rectangle([(0, y_top), (w, y_top + bh)], fill=c2)
        for x in range(-bh, w + 56, 56):
            od.polygon([(x, y_top + bh), (x + 28, y_top + bh), (x + 28 + bh, y_top), (x + bh, y_top)], fill=c1)

    draw_hazard_bar(0, 32, (230, 30, 40, 255))
    draw_hazard_bar(h - 32, 32, (250, 204, 21, 255))

    od.rounded_rectangle([(w - 490, 110), (w - 44, 206)], radius=14, fill=(220, 24, 34, 252), outline=(250, 204, 21, 255), width=5)
    draw_rtl_text(od, (w - 295, 128), "فوری | حادثه", load_font("display", 52), (255, 255, 255, 255), align="center", shadow=False)

    now_t = to_persian_digits(get_tehran_now().strftime("%H:%M"))
    od.rounded_rectangle([(44, 118), (315, 200)], radius=12, fill=(12, 12, 16, 235), outline=(220, 38, 38, 255), width=4)
    draw_rtl_text(od, (180, 136), f"ساعت {now_t}", load_font("bold", 34), (250, 204, 21, 255), align="center", shadow=False)

    box_top, box_bot = 1150, 1540
    od.rounded_rectangle([(42, box_top), (w - 42, box_bot)], radius=20, fill=(12, 8, 12, 235), outline=(235, 30, 40, 255), width=6)
    od.rectangle([(w - 62, box_top + 24), (w - 46, box_bot - 24)], fill=(250, 204, 21, 255))
    draw_rtl_text(od, (w - 50, 1565), BRAND_TITLE_FA, load_font("bold", 32), (250, 204, 21, 255), align="right")
    draw_rtl_text(od, (50, 1565), BRAND_HANDLE, load_font("bold", 32), (255, 255, 255, 255), align="left", is_rtl=False)

    clean_hl = strip_emojis_for_font(headline) or "حادثه فوری در حال بررسی است"
    hl_words = clean_hl.split()
    tw_box = (66, box_top + 26, w - 82, box_bot - 24)
    probe_d = ImageDraw.Draw(Image.new("RGBA", (w, h)))
    hl_font, _, hl_lh = fit_text_in_box(probe_d, clean_hl, "display", tw_box[2] - tw_box[0], tw_box[3] - tw_box[1], max_size=76, min_size=36, max_lines=3)

    type_overlays = []
    for k in range(1, len(hl_words) + 1):
        partial = " ".join(hl_words[:k])
        lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        p_lines = wrap_all_words(ld, partial, hl_font, tw_box[2] - tw_box[0])[:3]
        tot_h = len(p_lines) * hl_lh
        cy = tw_box[1] + ((tw_box[3] - tw_box[1]) - tot_h) // 2
        for ln in p_lines:
            draw_rtl_text(ld, (tw_box[2], cy), ln, hl_font, (255, 255, 255, 255), align="right", shadow=True, shadow_offset=5)
            cy += hl_lh
        type_overlays.append(lay)

    ticker_msg = f"فوری: {clean_hl}" + (f"  —  {strip_emojis_for_font(subtext)}" if subtext else "")
    ticker_strip = build_scrolling_ticker_strip(ticker_msg, duration, bg_color=(195, 22, 32, 248), height=78)
    strip_w = ticker_strip.size[0]
    audio_path = get_audio_track(work_dir, duration, mode="incident")
    out_mp4 = os.path.join(TMP_ROOT, f"incident_reel_{int(time.time()*1000)}.mp4")

    def frame_gen():
        bh_src, bw_src = bg_arr.shape[:2]
        for i in range(total_frames):
            t = i / fps
            zoom = 1.0 + 0.14 * (t / duration)
            crop_w, crop_h = int(bw_src / zoom), int(bh_src / zoom)
            shake_x = int(math.sin(t * 58.0) * 18 * max(0.0, 1.0 - t / 1.5))
            shake_y = int(math.cos(t * 64.0) * 18 * max(0.0, 1.0 - t / 1.5))
            x0 = max(0, min(bw_src - crop_w, (bw_src - crop_w) // 2 + shake_x))
            y0 = max(0, min(bh_src - crop_h, (bh_src - crop_h) // 2 + shake_y))
            resized = cv2.resize(bg_arr[y0:y0 + crop_h, x0:x0 + crop_w], (w, h), interpolation=cv2.INTER_LINEAR)
            frame = Image.fromarray(resized).convert("RGBA")

            frame.alpha_composite(siren_a if (int(t / 0.38) % 2 == 0) else siren_b)
            frame.alpha_composite(static_ov)
            if int(t * 3.5) % 2 == 0:
                ImageDraw.Draw(frame).ellipse([(w - 102, 142), (w - 70, 174)], fill=(250, 204, 21, 255))
            if t >= 1.1 and type_overlays:
                prog = min(1.0, (t - 1.1) / max(1.8, min(3.8, len(type_overlays) * 0.35)))
                frame.alpha_composite(type_overlays[min(len(type_overlays) - 1, int(prog * len(type_overlays)))])
            src_x = max(0, min(strip_w - w, (strip_w - w) - int(t * 175)))
            frame.alpha_composite(ticker_strip.crop((src_x, 0, src_x + w, 78)), (0, 1665))
            if t < 0.16 or (0.48 <= t < 0.60):
                frame.alpha_composite(shock_white)
            elif t < 1.25:
                frame.alpha_composite(shock_red)
            yield np.array(frame.convert("RGB"), dtype=np.uint8)

    pipe_frames_to_mp4(frame_gen(), out_mp4, audio_path, fps=fps)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۳. ریلز زوم سینمایی روی نقشه (۳ سرور پشتیبان) ====================
def latlon_to_tile_float(lat: float, lon: float, zoom: int):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    return (lon + 180.0) / 360.0 * n, (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n


async def resolve_location_coords(session: aiohttp.ClientSession, loc_name: str):
    clean = strip_emojis_for_font(loc_name)
    for key, val in FARS_LOCATIONS.items():
        if key in clean:
            return val
    try:
        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "ShirazLastNewsMedia/2.0 (contact@shirazlastnews.local)"}
        async with session.get(url, params={"q": f"{clean}, Iran", "format": "json", "limit": 1}, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"]), 14
    except Exception:
        pass
    return FARS_LOCATIONS["شیراز"]


async def fetch_reliable_map_image(session: aiohttp.ClientSession, lat: float, lon: float, zoom: int) -> Image.Image:
    xf, yf = latlon_to_tile_float(lat, lon, zoom)
    cx, cy = int(xf), int(yf)
    max_t = (2 ** zoom) - 1
    providers = [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"}

    for template in providers:
        grid = Image.new("RGB", (256 * 5, 256 * 5), (20, 30, 46))
        loaded = [0]

        async def get_tile(dx, dy):
            tx, ty = max(0, min(max_t, cx + dx)), max(0, min(max_t, cy + dy))
            try:
                async with session.get(template.format(z=zoom, x=tx, y=ty), headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        grid.paste(Image.open(io.BytesIO(await r.read())).convert("RGB"), ((dx + 2) * 256, (dy + 2) * 256))
                        loaded[0] += 1
            except Exception:
                pass

        await asyncio.gather(*(get_tile(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)))
        if loaded[0] >= 9:
            px, py = int((xf - (cx - 2)) * 256), int((yf - (cy - 2)) * 256)
            left = max(0, min(grid.width - 720, px - 360))
            top = max(0, min(grid.height - 1280, py - 640))
            return grid.crop((left, top, left + 720, top + 1280)).resize((1200, 2134), Image.Resampling.LANCZOS)

    fallback = Image.new("RGB", (1200, 2134), (15, 26, 42))
    fd = ImageDraw.Draw(fallback)
    for x in range(0, 1200, 80):
        fd.line([(x, 0), (x, 2134)], fill=(30, 48, 72), width=2)
    for y in range(0, 2134, 80):
        fd.line([(0, y), (1200, y)], fill=(30, 48, 72), width=2)
    return fallback


def build_map_zoom_reel_sync(wide_map: Image.Image, close_map: Image.Image, photo_path: str, loc_name: str, badge: str, headline: str, subtext: str) -> str:
    w, h, fps, duration = 1080, 1920, 25, 12.0
    total_frames = int(fps * duration)
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)

    wide_arr = np.array(wide_map.convert("RGB"), dtype=np.uint8)
    close_arr = np.array(close_map.convert("RGB"), dtype=np.uint8)
    news_arr = np.array(fit_cover(Image.open(photo_path).convert("RGB"), 1200, 2134), dtype=np.uint8) if (photo_path and os.path.exists(photo_path)) else close_arr.copy()

    map_hud = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(map_hud)
    for y in range(240):
        hd.line([(0, y), (w, y)], fill=(10, 18, 32, int(225 * (1 - y / 240))))
    for y in range(1580, h):
        hd.line([(0, y), (w, y)], fill=(10, 18, 32, int(235 * ((y - 1580) / (h - 1580)))))
    draw_rtl_text(hd, (w // 2, 56), f"گزارش مکانی  |  {BRAND_TITLE_FA}", load_font("bold", 40), (250, 204, 21, 255), align="center")

    loc_clean = strip_emojis_for_font(loc_name)
    loc_txt = f"موقعیت: {loc_clean}"
    f_loc = load_font("display", 54)
    l_draw, l_kw = prepare_text_and_kwargs(loc_txt, is_rtl=True)
    lb = hd.textbbox((0, 0), l_draw, font=f_loc, **l_kw)
    lw = min(w - 100, (lb[2] - lb[0]) + 90)
    cx, cy = w // 2, h // 2
    hd.rounded_rectangle([(cx - lw // 2, cy + 95), (cx + lw // 2, cy + 185)], radius=16, fill=(220, 38, 38, 245), outline=(255, 255, 255, 240), width=4)
    draw_rtl_text(hd, (cx, cy + 110), loc_txt, f_loc, (255, 255, 255, 255), align="center", shadow=False)

    repo_frame = find_repo_reel_frame() if CONFIG["use_repo_frame"] else ""
    if repo_frame:
        news_ov = Image.open(render_reel_frame_overlay(repo_frame, badge or loc_clean, headline, subtext, work_dir)).convert("RGBA")
    else:
        news_ov = Image.open(render_brand_story_sync(photo_path, badge or loc_clean, headline, subtext)).convert("RGBA")

    ticker_strip = build_scrolling_ticker_strip(f"{loc_clean}: {headline}", duration, bg_color=(15, 23, 42, 235), height=70)
    strip_w = ticker_strip.size[0]
    audio_path = get_audio_track(work_dir, duration, mode="news")
    out_mp4 = os.path.join(TMP_ROOT, f"map_reel_{int(time.time()*1000)}.mp4")

    def zoom_slice(arr, zoom_val):
        ah, aw = arr.shape[:2]
        cw, ch = int(aw / zoom_val), int(ah / zoom_val)
        x0, y0 = (aw - cw) // 2, (ah - ch) // 2
        return cv2.resize(arr[y0:y0 + ch, x0:x0 + cw], (w, h), interpolation=cv2.INTER_LINEAR)

    def frame_gen():
        for i in range(total_frames):
            t = i / fps
            if t < 2.6:
                frame = Image.fromarray(zoom_slice(wide_arr, 1.0 + 0.55 * (t / 2.6))).convert("RGBA")
                frame.alpha_composite(map_hud)
            elif t < 5.6:
                close_rgb = zoom_slice(close_arr, 1.0 + 0.25 * ((t - 2.6) / 3.0))
                if t < 3.1:
                    alpha = (t - 2.6) / 0.5
                    close_rgb = cv2.addWeighted(zoom_slice(wide_arr, 1.55), 1.0 - alpha, close_rgb, alpha, 0)
                frame = Image.fromarray(close_rgb).convert("RGBA")
                frame.alpha_composite(map_hud)
                rd = ImageDraw.Draw(frame)
                pulse_r = int(35 + ((t * 160) % 180))
                pulse_a = max(30, int(230 * (1.0 - (pulse_r - 35) / 180.0)))
                rd.ellipse([(cx - pulse_r, cy - pulse_r), (cx + pulse_r, cy + pulse_r)], outline=(239, 68, 68, pulse_a), width=6)
                rd.ellipse([(cx - 42, cy - 42), (cx + 42, cy + 42)], fill=(239, 68, 68, 120), outline=(255, 255, 255, 240), width=4)
                rd.ellipse([(cx - 16, cy - 16), (cx + 16, cy + 16)], fill=(220, 38, 38, 255))
            else:
                n_rgb = zoom_slice(news_arr, 1.0 + 0.10 * ((t - 5.6) / 6.4))
                if t < 6.1:
                    alpha = (t - 5.6) / 0.5
                    n_rgb = cv2.addWeighted(zoom_slice(close_arr, 1.25), 1.0 - alpha, n_rgb, alpha, 0)
                frame = Image.fromarray(n_rgb).convert("RGBA")
                frame.alpha_composite(news_ov)
            if CONFIG.get("video_ticker", True):
                src_x = max(0, min(strip_w - w, (strip_w - w) - int(t * 165)))
                frame.alpha_composite(ticker_strip.crop((src_x, 0, src_x + w, 70)), (0, 1795))
            yield np.array(frame.convert("RGB"), dtype=np.uint8)

    pipe_frames_to_mp4(frame_gen(), out_mp4, audio_path, fps=fps)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۴. موتور ۶ سبکی ریلز جمع‌بندی (بدون قلاب کاغذ سوخته) ====================
async def prepare_hologram_narration_audio(session: aiohttp.ClientSession, items: list, work_dir: str) -> dict:
    """تولید گویندگی شمرده با مکث طبیعی در شروع هر اسلاید و میکس شفاف روی موزیک پس‌زمینه."""
    selected = items[:8]
    ordinals = ["یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت"]
    scripts = ["خبر فوری! مرور مهم‌ترین خبرهای امروز شیراز و استان فارس."]
    for idx, it in enumerate(selected):
        hl = strip_emojis_for_font(it.get("headline", ""))
        ord_w = ordinals[idx] if idx < len(ordinals) else str(idx + 1)
        scripts.append(f"{ord_w}، {hl}.")
    scripts.append("برای پیگیری لحظه‌ای خبرها، آخرین خبرهای شیراز را فالو کنید.")

    seg_wavs = []
    seg_durs = []
    any_ok = False
    for k, sc_txt in enumerate(scripts):
        w_p = os.path.join(work_dir, f"nar_{k:02d}.wav")
        dur = await synthesize_broadcast_tts(session, sc_txt, w_p, work_dir)
        if dur > 0.3 and os.path.exists(w_p):
            any_ok = True
            padded = os.path.join(work_dir, f"nar_pad_{k:02d}.wav")
            target_d = max(2.4 if k in (0, len(scripts) - 1) else 3.8, dur + 0.85)
            # 0.25 ثانیه مکث در ابتدای هر خبر + فضای تنفس در انتها
            run_ffmpeg([
                "ffmpeg", "-y", "-i", w_p,
                "-af", f"adelay=250|250,apad=whole_dur={target_d:.2f}",
                "-ar", "44100", "-ac", "2", padded,
            ])
            seg_wavs.append(padded)
            seg_durs.append(target_d)
        else:
            sil = os.path.join(work_dir, f"sil_{k:02d}.wav")
            def_d = 2.4 if k in (0, len(scripts) - 1) else 4.2
            run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-t", f"{def_d:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", sil])
            seg_wavs.append(sil)
            seg_durs.append(def_d)

    total_sec = sum(seg_durs)
    bg_music = get_audio_track(work_dir, total_sec + 2.0, mode="hologram")
    if not any_ok:
        return {"audio_path": bg_music, "durs": seg_durs, "loop_audio": True, "narrated": False}

    list_f = os.path.join(work_dir, "nar_list.txt")
    with open(list_f, "w") as f:
        for sw in seg_wavs:
            f.write(f"file '{sw}'\n")
    voice_full = os.path.join(work_dir, "voice_full.wav")
    run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_f, "-c", "copy", voice_full])

    mixed_wav = os.path.join(work_dir, "holo_mixed.wav")
    run_ffmpeg([
        "ffmpeg", "-y",
        "-i", voice_full,
        "-stream_loop", "-1", "-i", bg_music,
        "-filter_complex", "[0:a]volume=1.85[v];[1:a]volume=0.22[m];[v][m]amix=inputs=2:duration=first:dropout_transition=1,alimiter=limit=0.95[out]",
        "-map", "[out]", "-ar", "44100", "-ac", "2", "-t", f"{total_sec:.2f}", mixed_wav,
    ])
    return {"audio_path": mixed_wav, "durs": seg_durs, "loop_audio": False, "narrated": True}


def build_daily_summary_reel_sync(items: list, style: str = "broadcast", narration_plan: dict = None) -> str:
    """موتور ۶ سبکی ریلز جمع‌بندی (برودکست، دوپنجره‌ای، مطبوعاتی، اکسپلور تند، بولتین زنده و هولوگرام+گوینده). بدون قلاب کاغذ سوخته."""
    w, h, fps = 1080, 1920, 25
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)
    selected = items[:8]
    n_news = max(1, len(selected))

    gw, gh = 135, 240
    gy_grid, gx_grid = np.mgrid[0:gh, 0:gw].astype(np.float32)
    gx_norm, gy_norm = gx_grid / gw, gy_grid / gh

    def make_dark_gradient_bg(t_sec: float, tint_rgb=(196, 22, 34)):
        c1x = 0.25 + 0.18 * math.sin(t_sec * 0.65)
        c1y = 0.28 + 0.14 * math.cos(t_sec * 0.50)
        c2x = 0.78 + 0.16 * math.cos(t_sec * 0.55)
        c2y = 0.76 + 0.12 * math.sin(t_sec * 0.70)
        d1 = np.exp(-((gx_norm - c1x) ** 2 + ((gy_norm - c1y) * 1.45) ** 2) / 0.18)
        d2 = np.exp(-((gx_norm - c2x) ** 2 + ((gy_norm - c2y) * 1.45) ** 2) / 0.22)
        r = np.clip(13.0 + d1 * (tint_rgb[0] * 0.42) + d2 * 22.0, 0, 255)
        g = np.clip(16.0 + d1 * (tint_rgb[1] * 0.42) + d2 * 38.0, 0, 255)
        b = np.clip(23.0 + d1 * (tint_rgb[2] * 0.42) + d2 * 68.0, 0, 255)
        return cv2.resize(np.stack([r, g, b], axis=-1).astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR)

    def apply_glass_box(bg_rgb: np.ndarray, box: tuple, radius: int = 34, tint=(14, 17, 25), alpha: float = 0.62) -> Image.Image:
        x1, y1, x2, y2 = max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3])
        bw, bh = x2 - x1, y2 - y1
        if bw < 20 or bh < 20:
            return Image.fromarray(bg_rgb).convert("RGBA")
        crop = bg_rgb[y1:y2, x1:x2]
        blurred = cv2.GaussianBlur(cv2.resize(crop, (max(8, bw // 4), max(8, bh // 4)), interpolation=cv2.INTER_LINEAR), (21, 21), 0)
        frosted = cv2.resize(blurred, (bw, bh), interpolation=cv2.INTER_LINEAR)
        glass = cv2.addWeighted(frosted, 1.0 - alpha, np.full_like(frosted, tint, dtype=np.uint8), alpha, 0)
        out = bg_rgb.copy()
        mask_pil = Image.new("L", (bw, bh), 0)
        ImageDraw.Draw(mask_pil).rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=radius, fill=255)
        mask_arr = (np.array(mask_pil, dtype=np.float32) / 255.0)[:, :, None]
        out[y1:y2, x1:x2] = (glass * mask_arr + out[y1:y2, x1:x2] * (1.0 - mask_arr)).astype(np.uint8)
        return Image.fromarray(out).convert("RGBA")

    def warp_3d_card_rgba(card_pil: Image.Image, yaw_deg: float, pitch_deg: float) -> Image.Image:
        """زاویه‌دهی سه‌بعدی پرسپکتیو برای کارت هولوگرام معلق (سبک ۶)."""
        arr = np.array(card_pil, dtype=np.uint8)
        ch, cw = arr.shape[:2]
        pad_x, pad_y = 90, 90
        src = np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]])
        dx = math.sin(math.radians(yaw_deg)) * 62.0
        dy = math.sin(math.radians(pitch_deg)) * 34.0
        shrink = abs(math.sin(math.radians(yaw_deg))) * 48.0
        dst = np.float32([
            [pad_x + (shrink if dx > 0 else 0), pad_y + max(0.0, dy)],
            [pad_x + cw - (shrink if dx < 0 else 0), pad_y + max(0.0, -dy)],
            [pad_x + cw - (shrink if dx < 0 else 0), pad_y + ch - max(0.0, -dy)],
            [pad_x + (shrink if dx > 0 else 0), pad_y + ch - max(0.0, dy)],
        ])
        M = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(arr, M, (cw + pad_x * 2, ch + pad_y * 2), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        return Image.fromarray(warped, mode="RGBA")

    def draw_broadcast_wipe(frame_rgba: Image.Image, mode: str, progress: float):
        d = ImageDraw.Draw(frame_rgba)
        slant, stripe_w = 260, 88
        charcoal, crimson = (18, 20, 25, 255), (204, 18, 28, 255)
        if mode == "in":
            lead_x = int(1380 - 1500 * (progress ** 1.35))
            d.polygon([(lead_x, 0), (lead_x + stripe_w, 0), (lead_x + stripe_w - slant, h), (lead_x - slant, h)], fill=crimson)
            d.polygon([(lead_x + stripe_w, 0), (w + 400, 0), (w + 400, h), (lead_x + stripe_w - slant, h)], fill=charcoal)
        else:
            trail_x = int(1460 - 1540 * (progress ** 0.78))
            d.polygon([(-400, 0), (trail_x - stripe_w, 0), (trail_x - stripe_w - slant, h), (-400, h)], fill=charcoal)
            d.polygon([(trail_x - stripe_w, 0), (trail_x, 0), (trail_x - slant, h), (trail_x - stripe_w - slant, h)], fill=crimson)

    def draw_laser_wipe(frame_rgba: Image.Image, progress: float, color=(0, 232, 255)):
        """ترنزیشن خط لیزری درخشان برای سبک ۶ (هولوگرام)."""
        lx = int(-160 + (w + 320) * progress)
        lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        ld.polygon([(lx - 44, 0), (lx + 44, 0), (lx - 130, h), (lx - 218, h)], fill=color + (165,))
        ld.polygon([(lx - 12, 0), (lx + 12, 0), (lx - 162, h), (lx - 186, h)], fill=(255, 255, 255, 250))
        frame_rgba.alpha_composite(lay.filter(ImageFilter.GaussianBlur(radius=10)))

    def draw_progress_bars(frame_rgba: Image.Image, current_idx: int, frac: float, bar_y: int = 58, active_c=(220, 28, 38, 255)):
        pd = ImageDraw.Draw(frame_rgba)
        margin_x, gap, bar_h = 46, 12, 9
        seg_w = (w - margin_x * 2 - gap * (n_news - 1)) / n_news
        for s in range(n_news):
            sx1, sx2 = int(margin_x + s * (seg_w + gap)), int(margin_x + s * (seg_w + gap) + seg_w)
            pd.rounded_rectangle([(sx1, bar_y), (sx2, bar_y + bar_h)], radius=5, fill=(255, 255, 255, 72))
            if s < current_idx:
                pd.rounded_rectangle([(sx1, bar_y), (sx2, bar_y + bar_h)], radius=5, fill=(255, 255, 255, 238))
            elif s == current_idx:
                fw = max(10, int(seg_w * max(0.0, min(1.0, frac))))
                pd.rounded_rectangle([(sx1, bar_y), (sx1 + fw, bar_y + bar_h)], radius=5, fill=active_c)

    def get_accent_for_tag(tag_txt: str) -> tuple:
        if "فوری" in tag_txt or "حادثه" in tag_txt:
            return (214, 22, 34)
        if "ورزش" in tag_txt:
            return (22, 163, 74)
        if "اقتصاد" in tag_txt:
            return (217, 152, 16)
        return (204, 18, 28)

    logo_img = None
    logo_path = find_repo_logo()
    if logo_path:
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
        except Exception:
            logo_img = None

    def paste_logo(target_rgba, draw_obj, x, y, mw=110, mh=82):
        if logo_img:
            lg = logo_img.copy()
            lg.thumbnail((mw, mh), Image.Resampling.LANCZOS)
            target_rgba.alpha_composite(lg, (x, y))
        else:
            draw_quran_gate_fallback(draw_obj, x, y, min(mw, mh))

    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for y in range(340):
        vd.line([(0, y), (w, y)], fill=(10, 12, 18, int(215 * (1.0 - y / 340.0))))
    for y in range(980, h):
        vd.line([(0, y), (w, y)], fill=(10, 12, 18, int(242 * (((y - 980) / (h - 980)) ** 1.25))))

    now_tehran = get_tehran_now()
    jnow = jdatetime.datetime.fromgregorian(datetime=now_tehran)
    date_str = to_persian_digits(f"{JALALI_WEEKDAYS[jnow.weekday()]} {jnow.day} {JALALI_MONTHS[jnow.month]} {jnow.year}")
    clock_str = to_persian_digits(now_tehran.strftime("%H:%M"))

    # مقدمه مشترک (بدون عدد تعداد خبرها روی اسلاید اول)
    intro_box = (66, 610, w - 66, 1270)
    intro_ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(intro_ov)
    accent_intro = (0, 212, 255) if style == "hologram" else (204, 18, 28)
    idraw.rounded_rectangle(intro_box, radius=36, outline=accent_intro + (150,) if style == "hologram" else (255, 255, 255, 68), width=3)
    idraw.rectangle([(w - 92, 665), (w - 80, 1215)], fill=accent_intro + (255,))
    paste_logo(intro_ov, idraw, (w - 140) // 2, 360, 170, 130)
    intro_tag_map = {
        "broadcast": "بسته خبری روزانه", "split": "گزارش تحریریه", "editorial": "پرونده خبری امروز",
        "kinetic": "مرور سریع اخبار", "live": "بولتین زنده خبری", "hologram": "گزارش صوتی و تصویری",
    }
    idraw.polygon([(310, 566), (790, 566), (762, 636), (282, 636)], fill=(204, 18, 28, 255))
    draw_rtl_text(idraw, (536, 578), intro_tag_map.get(style, "بسته خبری روزانه"), load_font("bold", 38), (255, 255, 255, 255), align="center", shadow=False)
    draw_rtl_text(idraw, (w // 2, 720), "۶۰ ثانیه با مهم‌ترین اخبار", load_font("display", 90), (255, 255, 255, 255), align="center")
    draw_rtl_text(idraw, (w // 2, 875), date_str, load_font("bold", 40), (210, 218, 232, 255), align="center", shadow=False)
    idraw.line([(210, 965), (w - 210, 965)], fill=(255, 255, 255, 55), width=2)
    draw_rtl_text(idraw, (w // 2, 1015), "مرور سریع برگزیده اخبار ایران و شیراز", load_font("bold", 36), (242, 200, 68, 255), align="center", shadow=False)
    draw_rtl_text(idraw, (w // 2, 1140), BRAND_HANDLE, load_font("bold", 36), (205, 212, 224, 255), align="center", shadow=False, is_rtl=False)

    # پایان مشترک
    outro_box = (72, 690, w - 72, 1210)
    outro_ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(outro_ov)
    od.rounded_rectangle(outro_box, radius=36, outline=accent_intro + (150,) if style == "hologram" else (255, 255, 255, 72), width=3)
    draw_rtl_text(od, (w // 2, 755), BRAND_TITLE_FA, load_font("display", 82), (255, 255, 255, 255), align="center")
    draw_rtl_text(od, (w // 2, 895), "برای پیگیری لحظه‌ای اخبار شیراز و فارس فالو کنید", load_font("bold", 36), (210, 218, 232, 255), align="center", shadow=False)
    od.rounded_rectangle([(255, 1005), (825, 1115)], radius=24, fill=(204, 18, 28, 255))
    draw_rtl_text(od, (w // 2, 1034), BRAND_HANDLE, load_font("bold", 46), (255, 255, 255, 255), align="center", shadow=False, is_rtl=False)

    # زمان‌بندی دقیق (برای سبک هولوگرام هماهنگ با زمان صدای گوینده)
    if style == "hologram" and narration_plan and len(narration_plan.get("durs", [])) == (len(selected) + 2):
        durs_list = narration_plan["durs"]
        intro_dur, outro_dur = durs_list[0], durs_list[-1]
        item_durs = durs_list[1:-1]
        audio_path = narration_plan["audio_path"]
        loop_audio = narration_plan.get("loop_audio", False)
    else:
        intro_dur = 1.8 if style == "kinetic" else 2.4
        outro_dur = 1.8 if style == "kinetic" else 2.2
        item_durs = [3.5 if style == "kinetic" else 4.8 for _ in selected]
        total_sec_est = intro_dur + sum(item_durs) + outro_dur
        audio_path = get_audio_track(work_dir, total_sec_est, mode="hologram" if style == "hologram" else "news")
        loop_audio = True

    total_sec = intro_dur + sum(item_durs) + outro_dur
    out_mp4 = os.path.join(TMP_ROOT, f"daily_{style}_{int(time.time()*1000)}.mp4")

    ticker_strip = None
    if style in ("split", "live"):
        all_hls = "   ●   ".join(strip_emojis_for_font(it["headline"]) for it in selected if it.get("headline"))
        ticker_strip = build_scrolling_ticker_strip(all_hls, total_sec + 4.0, bg_color=(192, 20, 30, 245) if style == "live" else (24, 28, 38, 245), height=74)

    paper_bg_arr = None
    if style == "editorial":
        rng = np.random.default_rng(42)
        base_p = np.full((h, w, 3), (22, 24, 30), dtype=np.int16)
        noise = rng.integers(-8, 9, size=(h // 2, w // 2, 1), dtype=np.int16)
        paper_bg_arr = np.clip(base_p + cv2.resize(noise.astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)[:, :, None].astype(np.int16), 0, 255).astype(np.uint8)

    # ذرات نورانی معلق برای سبک ۶ (هولوگرام)
    particles = []
    if style == "hologram":
        prng = random.Random(77)
        for _ in range(38):
            particles.append((prng.uniform(0, w), prng.uniform(0, h), prng.uniform(22, 68), prng.uniform(3, 8), prng.choice([(0, 232, 255), (255, 206, 54), (240, 56, 72)])))

    prepared = []
    for idx, item in enumerate(selected, start=1):
        photo_p = item.get("photo")
        has_photo = bool(photo_p and os.path.exists(photo_p))
        tag_txt = strip_emojis_for_font(item.get("tag", "خبر شیراز")) or "خبر شیراز"
        hl_txt = strip_emojis_for_font(item.get("headline", "")) or BRAND_TITLE_FA
        accent_c = get_accent_for_tag(tag_txt)
        t_lbl = to_persian_digits(item.get("time", ""))
        cnt_str = to_persian_digits(f"{idx:02d} / {n_news:02d}")
        entry = {"idx": idx, "tag": tag_txt, "headline": hl_txt, "accent": accent_c, "time": t_lbl, "cnt": cnt_str, "dur": item_durs[idx - 1], "photo_arr": None}

        if style == "broadcast":
            if has_photo:
                entry["photo_arr"] = np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1220, 2168), dtype=np.uint8)
            cb_w, cb_h = w - 104, 420
            card_content = Image.new("RGBA", (cb_w, cb_h), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card_content)
            cd.rounded_rectangle([(0, 0), (cb_w - 1, cb_h - 1)], radius=34, outline=(255, 255, 255, 78), width=3)
            cd.rounded_rectangle([(cb_w - 28, 34), (cb_w - 14, cb_h - 34)], radius=7, fill=accent_c + (255,))
            cd.polygon([(cb_w - 310, 26), (cb_w - 46, 26), (cb_w - 46, 82), (cb_w - 332, 82)], fill=accent_c + (255,))
            draw_centered_block_in_box(cd, (cb_w - 312, 30, cb_w - 50, 78), tag_txt, "bold", (255, 255, 255, 255), max_size=30, min_size=20, max_lines=1)
            if t_lbl:
                draw_rtl_text(cd, (36, 40), f"ساعت {t_lbl}", load_font("regular", 26), (195, 205, 220, 220), align="left", shadow=False)
            draw_centered_block_in_box(cd, (34, 98, cb_w - 50, cb_h - 32), hl_txt, "display", (255, 255, 255, 255), max_size=62, min_size=32, max_lines=3, align="right", pad_x=12, pad_y=6, shadow=True)
            hud_top = Image.new("RGBA", (w, 260), (0, 0, 0, 0))
            hd = ImageDraw.Draw(hud_top)
            paste_logo(hud_top, hd, 52, 102, 110, 82)
            draw_rtl_text(hd, (172, 128), BRAND_HANDLE, load_font("bold", 28), (235, 240, 248, 220), align="left", shadow=True, is_rtl=False)
            hd.rounded_rectangle([(w - 260, 106), (w - 48, 174)], radius=34, fill=(16, 18, 24, 210), outline=(255, 255, 255, 75), width=2)
            hd.ellipse([(w - 92, 128), (w - 68, 152)], fill=accent_c + (255,))
            draw_rtl_text(hd, (w - 175, 120), cnt_str, load_font("bold", 34), (255, 255, 255, 255), align="center", shadow=False, is_rtl=False)
            entry["card_content"], entry["hud_top"] = card_content, hud_top

        elif style == "split":
            if has_photo:
                entry["photo_arr"] = np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1220, 1152), dtype=np.uint8)
            static_split = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(static_split)
            for y in range(220):
                sd.line([(0, y), (w, y)], fill=(12, 14, 20, int(195 * (1.0 - y / 220.0))))
            sd.rectangle([(0, 1020), (w, h)], fill=(17, 20, 27, 255))
            sd.rectangle([(0, 1012), (w, 1024)], fill=accent_c + (255,))
            paste_logo(static_split, sd, 48, 92, 104, 78)
            sd.rounded_rectangle([(w - 255, 96), (w - 46, 162)], radius=30, fill=(14, 16, 22, 220), outline=(255, 255, 255, 80), width=2)
            draw_rtl_text(sd, (w - 150, 108), cnt_str, load_font("bold", 32), (255, 255, 255, 255), align="center", shadow=False, is_rtl=False)
            sd.polygon([(w - 350, 976), (w - 46, 976), (w - 46, 1052), (w - 380, 1052)], fill=accent_c + (255,))
            draw_centered_block_in_box(sd, (w - 350, 982, w - 54, 1046), tag_txt, "bold", (255, 255, 255, 255), max_size=32, min_size=22, max_lines=1)
            draw_rtl_text(sd, (54, 1072), f"{BRAND_HANDLE}  |  {date_str}", load_font("regular", 26), (170, 180, 198, 230), align="left", shadow=False, is_rtl=False)
            sd.line([(54, 1126), (w - 54, 1126)], fill=(255, 255, 255, 42), width=2)
            text_layer = Image.new("RGBA", (w, 560), (0, 0, 0, 0))
            td = ImageDraw.Draw(text_layer)
            td.rectangle([(w - 66, 36), (w - 52, 430)], fill=accent_c + (255,))
            draw_centered_block_in_box(td, (60, 26, w - 90, 440), hl_txt, "display", (255, 255, 255, 255), max_size=70, min_size=36, max_lines=4, align="right", pad_x=10, pad_y=6, shadow=True)
            if t_lbl:
                draw_rtl_text(td, (w - 90, 466), f"ساعت مخابره خبر: {t_lbl}", load_font("regular", 28), (185, 195, 212, 225), align="right", shadow=False)
            entry["static_split"], entry["text_layer"] = static_split, text_layer

        elif style == "editorial":
            if has_photo:
                entry["photo_arr"] = np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1020, 820), dtype=np.uint8)
            ed_frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ed = ImageDraw.Draw(ed_frame)
            paste_logo(ed_frame, ed, 54, 96, 102, 76)
            draw_rtl_text(ed, (w - 54, 108), f"پرونده خبری  |  {date_str}", load_font("bold", 30), (225, 216, 196, 240), align="right", shadow=False)
            ed.line([(54, 198), (w - 54, 198)], fill=(225, 216, 196, 110), width=2)
            ed.rounded_rectangle([(w - 320, 1068), (w - 64, 1130)], radius=10, fill=accent_c + (255,))
            draw_centered_block_in_box(ed, (w - 314, 1072, w - 70, 1126), tag_txt, "bold", (255, 255, 255, 255), max_size=30, min_size=20, max_lines=1)
            draw_rtl_text(ed, (64, 1080), cnt_str, load_font("bold", 34), (225, 216, 196, 210), align="left", shadow=False, is_rtl=False)
            ed.line([(54, 1740), (w - 54, 1740)], fill=(225, 216, 196, 85), width=2)
            draw_rtl_text(ed, (w - 54, 1766), BRAND_TITLE_FA, load_font("bold", 30), (225, 216, 196, 220), align="right", shadow=False)
            draw_rtl_text(ed, (54, 1768), BRAND_HANDLE, load_font("bold", 30), (242, 200, 68, 240), align="left", shadow=False, is_rtl=False)
            hl_lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            hd = ImageDraw.Draw(hl_lay)
            f_ed, ed_lines, ed_lh = fit_text_in_box(hd, hl_txt, "display", w - 148, 460, max_size=68, min_size=36, max_lines=4, line_spacing=1.42)
            line_rects, cur_y = [], 1175
            for ln in ed_lines:
                t_draw, kw = prepare_text_and_kwargs(ln, is_rtl=True)
                bb = hd.textbbox((0, 0), t_draw, font=f_ed, **kw)
                line_rects.append((max(68, (w - 68) - (bb[2] - bb[0]) - 24), cur_y + int(ed_lh * 0.56), w - 60, cur_y + int(ed_lh * 0.86)))
                draw_rtl_text(hd, (w - 74, cur_y), ln, f_ed, (250, 248, 242, 255), align="right", shadow=True, shadow_offset=3)
                cur_y += ed_lh
            entry["ed_frame"], entry["hl_lay"], entry["line_rects"] = ed_frame, hl_lay, line_rects

        elif style == "kinetic":
            if has_photo:
                entry["photo_arr"] = cv2.convertScaleAbs(np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1280, 2276), dtype=np.uint8), alpha=1.14, beta=-8)
            k_hud = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            kd = ImageDraw.Draw(k_hud)
            kd.rounded_rectangle([(52, 102), (350, 174)], radius=14, fill=accent_c + (248,))
            draw_centered_block_in_box(kd, (60, 106, 342, 170), tag_txt, "bold", (255, 255, 255, 255), max_size=34, min_size=22, max_lines=1)
            draw_rtl_text(kd, (w - 56, 84), to_persian_digits(f"{idx:02d}"), load_font("display", 118), (255, 255, 255, 235), align="right", shadow=True, shadow_offset=6)
            draw_rtl_text(kd, (w // 2, 1775), BRAND_HANDLE, load_font("bold", 34), (255, 255, 255, 230), align="center", shadow=True, is_rtl=False)
            probe = ImageDraw.Draw(Image.new("RGBA", (w, h)))
            fk, k_lines, k_lh = fit_text_in_box(probe, hl_txt, "display", w - 160, 460, max_size=74, min_size=38, max_lines=4, line_spacing=1.42)
            start_y = 1130 + (460 - len(k_lines) * k_lh) // 2
            line_layers = []
            for li, ln in enumerate(k_lines):
                lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                ld = ImageDraw.Draw(lay)
                t_draw, kw = prepare_text_and_kwargs(ln, is_rtl=True)
                bb = ld.textbbox((0, 0), t_draw, font=fk, **kw)
                lw, lh_b, ly = bb[2] - bb[0], bb[3] - bb[1], start_y + li * k_lh
                ld.rounded_rectangle([(w // 2 - lw // 2 - 34, ly - 10), (w // 2 + lw // 2 + 34, ly + lh_b + 26)], radius=14, fill=(accent_c + (245,)) if li == 0 else (12, 14, 18, 238))
                draw_rtl_text(ld, (w // 2, ly), ln, fk, (255, 255, 255, 255), align="center", shadow=False)
                line_layers.append(lay)
            entry["k_hud"], entry["line_layers"] = k_hud, line_layers

        elif style == "live":
            if has_photo:
                entry["photo_arr"] = np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1080, 1080), dtype=np.uint8)
            live_ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ld = ImageDraw.Draw(live_ov)
            ld.rectangle([(0, 0), (w, 198)], fill=(15, 19, 28, 255))
            ld.rectangle([(0, 192), (w, 200)], fill=(204, 18, 28, 255))
            paste_logo(live_ov, ld, 46, 36, 105, 80)
            ld.rounded_rectangle([(46, 126), (192, 174)], radius=24, fill=(30, 32, 40, 255), outline=(204, 18, 28, 220), width=2)
            draw_rtl_text(ld, (104, 134), "LIVE", load_font("bold", 26), (255, 255, 255, 255), align="left", shadow=False, is_rtl=False)
            ld.rounded_rectangle([(w - 280, 44), (w - 46, 114)], radius=14, fill=(204, 18, 28, 255))
            draw_rtl_text(ld, (w - 163, 56), f"ساعت {clock_str}", load_font("bold", 34), (255, 255, 255, 255), align="center", shadow=False)
            draw_rtl_text(ld, (w - 48, 132), f"{date_str}  |  بولتین خبری", load_font("regular", 26), (205, 214, 228, 235), align="right", shadow=False)
            ld.rounded_rectangle([(46, 252), (w - 46, 1226)], radius=26, outline=(255, 255, 255, 88), width=4)
            ld.polygon([(w - 400, 1152), (w - 50, 1152), (w - 50, 1222), (w - 432, 1222)], fill=accent_c + (245,))
            draw_centered_block_in_box(ld, (w - 396, 1156, w - 58, 1218), f"{tag_txt}  |  {cnt_str}", "bold", (255, 255, 255, 255), max_size=28, min_size=20, max_lines=1)
            ld.rounded_rectangle([(46, 1268), (w - 46, 1666)], radius=24, fill=(20, 26, 38, 248), outline=(255, 255, 255, 65), width=3)
            ld.rectangle([(w - 72, 1296), (w - 56, 1638)], fill=accent_c + (255,))
            draw_centered_block_in_box(ld, (76, 1294, w - 92, 1640), hl_txt, "display", (255, 255, 255, 255), max_size=64, min_size=34, max_lines=3, align="right", pad_x=10, pad_y=6, shadow=True)
            draw_rtl_text(ld, (w // 2, 1844), f"{BRAND_TITLE_FA}  |  {BRAND_HANDLE}", load_font("bold", 28), (205, 214, 228, 225), align="center", shadow=False)
            entry["live_ov"] = live_ov

        else:  # style == "hologram" (سبک ۶: کارت هولوگرام شیشه‌ای کج‌شده سه‌بعدی + گوینده فارسی)
            neon_c = (0, 226, 255) if (idx % 2 == 1) else (255, 198, 42)
            entry["neon"] = neon_c
            card_w, card_h = 860, 1140
            holo_card = Image.new("RGBA", (card_w, card_h), (14, 20, 34, 222))
            hcd = ImageDraw.Draw(holo_card)
            if has_photo:
                pic_h = fit_cover(Image.open(photo_p).convert("RGB"), card_w - 44, 650)
            else:
                pic_h = Image.fromarray(make_dark_gradient_bg(idx * 1.7, neon_c)[0:650, 0:card_w - 44])
            pmask = Image.new("L", (card_w - 44, 650), 0)
            ImageDraw.Draw(pmask).rounded_rectangle([(0, 0), (card_w - 44, 650)], radius=26, fill=255)
            holo_card.paste(pic_h, (22, 22), pmask)
            hcd.rounded_rectangle([(22, 22), (card_w - 22, 672)], radius=26, outline=neon_c + (180,), width=3)
            hcd.rounded_rectangle([(2, 2), (card_w - 3, card_h - 3)], radius=36, outline=neon_c + (235,), width=5)
            # نشان شماره خبر و برچسب
            hcd.rounded_rectangle([(card_w - 300, 696), (card_w - 32, 758)], radius=14, fill=accent_c + (250,))
            draw_centered_block_in_box(hcd, (card_w - 294, 700, card_w - 38, 754), tag_txt, "bold", (255, 255, 255, 255), max_size=30, min_size=20, max_lines=1)
            draw_rtl_text(hcd, (42, 704), f"خبر {to_persian_digits(str(idx))}", load_font("display", 44), neon_c + (255,), align="left", shadow=False)
            draw_centered_block_in_box(hcd, (36, 774, card_w - 36, card_h - 34), hl_txt, "display", (255, 255, 255, 255), max_size=60, min_size=32, max_lines=3, align="right", shadow=True)
            entry["holo_card"] = holo_card

            holo_hud = Image.new("RGBA", (w, 240), (0, 0, 0, 0))
            hhd = ImageDraw.Draw(holo_hud)
            paste_logo(holo_hud, hhd, 52, 98, 108, 80)
            draw_rtl_text(hhd, (172, 124), BRAND_HANDLE, load_font("bold", 28), neon_c + (235,), align="left", shadow=True, is_rtl=False)
            hhd.rounded_rectangle([(w - 255, 102), (w - 48, 170)], radius=34, fill=(10, 16, 28, 215), outline=neon_c + (190,), width=3)
            draw_rtl_text(hhd, (w - 151, 116), cnt_str, load_font("bold", 34), (255, 255, 255, 255), align="center", shadow=False, is_rtl=False)
            entry["holo_hud"] = holo_hud

        prepared.append(entry)

    def frame_gen():
        global_t = 0.0
        wipe_dur = 0.25

        # ۱. مقدمه
        for i in range(int(intro_dur * fps)):
            lt = i / fps
            global_t += 1.0 / fps
            bg = make_dark_gradient_bg(global_t, (0, 175, 235) if style == "hologram" else (204, 18, 28))
            dy = int(75 * ((1.0 - min(1.0, lt / 0.50)) ** 3))
            frame = apply_glass_box(bg, (intro_box[0], intro_box[1] + dy, intro_box[2], intro_box[3] + dy), radius=36, alpha=0.58)
            frame.alpha_composite(intro_ov, (0, dy))
            if lt > (intro_dur - wipe_dur):
                if style == "hologram":
                    draw_laser_wipe(frame, (lt - (intro_dur - wipe_dur)) / wipe_dur)
                else:
                    draw_broadcast_wipe(frame, "in", (lt - (intro_dur - wipe_dur)) / wipe_dur)
            yield np.array(frame.convert("RGB"), dtype=np.uint8)

        # ۲. خبرها
        for s_idx, sl in enumerate(prepared):
            dur = sl["dur"]
            n_f = int(dur * fps)
            photo_arr = sl["photo_arr"]

            for i in range(n_f):
                lt = i / fps
                global_t += 1.0 / fps

                if style == "broadcast":
                    if photo_arr is not None:
                        ah, aw = photo_arr.shape[:2]
                        z = 1.0 + 0.09 * (lt / dur)
                        cw, ch = int(aw / z), int(ah / z)
                        bg_rgb = cv2.resize(photo_arr[(ah - ch) // 2:(ah - ch) // 2 + ch, (aw - cw) // 2:(aw - cw) // 2 + cw], (w, h), interpolation=cv2.INTER_LINEAR)
                    else:
                        bg_rgb = make_dark_gradient_bg(global_t, sl["accent"])
                    base_rgba = Image.fromarray(bg_rgb).convert("RGBA")
                    base_rgba.alpha_composite(vignette)
                    dy = int(115 * ((1.0 - min(1.0, max(0.0, (lt - 0.12) / 0.55))) ** 3))
                    cur_box = (52, 1235 + dy, w - 52, 1655 + dy)
                    frame = apply_glass_box(np.array(base_rgba.convert("RGB"), dtype=np.uint8), cur_box, radius=34, alpha=0.60)
                    frame.alpha_composite(sl["card_content"], (cur_box[0], cur_box[1]))
                    frame.alpha_composite(sl["hud_top"], (0, 0))
                    draw_progress_bars(frame, s_idx, lt / dur)
                    draw_rtl_text(ImageDraw.Draw(frame), (w // 2, 1790), "بسته خبری روزانه  |  آخرین خبرهای شیراز و استان فارس", load_font("regular", 26), (200, 208, 222, 200), align="center", shadow=False)
                    if lt < wipe_dur:
                        draw_broadcast_wipe(frame, "out", lt / wipe_dur)
                    elif lt > (dur - wipe_dur):
                        draw_broadcast_wipe(frame, "in", (lt - (dur - wipe_dur)) / wipe_dur)

                elif style == "split":
                    canvas_rgb = np.full((h, w, 3), (17, 20, 27), dtype=np.uint8)
                    if photo_arr is not None:
                        ah, aw = photo_arr.shape[:2]
                        z = 1.0 + 0.08 * (lt / dur)
                        cw, ch = int(aw / z), int(ah / z)
                        canvas_rgb[0:1020, 0:w] = cv2.resize(photo_arr[(ah - ch) // 2:(ah - ch) // 2 + ch, (aw - cw) // 2:(aw - cw) // 2 + cw], (w, 1020), interpolation=cv2.INTER_LINEAR)
                    else:
                        canvas_rgb[0:1020, 0:w] = make_dark_gradient_bg(global_t, sl["accent"])[0:1020, 0:w]
                    frame = Image.fromarray(canvas_rgb).convert("RGBA")
                    frame.alpha_composite(sl["static_split"])
                    dx = int(140 * ((1.0 - min(1.0, lt / 0.45)) ** 3))
                    frame.alpha_composite(sl["text_layer"], (dx, 1150))
                    draw_progress_bars(frame, s_idx, lt / dur, bar_y=46)
                    if ticker_strip is not None:
                        avail = max(1, ticker_strip.width - w)
                        src_x = avail - (int(global_t * 165) % avail)
                        frame.alpha_composite(ticker_strip.crop((src_x, 0, src_x + w, 74)), (0, 1792))
                    if lt < wipe_dur:
                        draw_broadcast_wipe(frame, "out", lt / wipe_dur)
                    elif lt > (dur - wipe_dur):
                        draw_broadcast_wipe(frame, "in", (lt - (dur - wipe_dur)) / wipe_dur)

                elif style == "editorial":
                    frame = Image.fromarray(paper_bg_arr.copy()).convert("RGBA")
                    px1, py1, px2, py2 = 66, 246, w - 66, 1020
                    pw, ph = px2 - px1, py2 - py1
                    if photo_arr is not None:
                        ah, aw = photo_arr.shape[:2]
                        z = 1.0 + 0.07 * (lt / dur)
                        cw, ch = int(aw / z), int(ah / z)
                        pic_pil = Image.fromarray(cv2.resize(photo_arr[(ah - ch) // 2:(ah - ch) // 2 + ch, (aw - cw) // 2:(aw - cw) // 2 + cw], (pw, ph), interpolation=cv2.INTER_LINEAR))
                    else:
                        pic_pil = Image.fromarray(make_dark_gradient_bg(global_t, sl["accent"])[0:ph, 0:pw])
                    fd = ImageDraw.Draw(frame)
                    fd.rectangle([(px1 + 14, py1 + 14), (px2 + 14, py2 + 14)], fill=(8, 9, 12, 190))
                    frame.paste(pic_pil, (px1, py1))
                    fd.rectangle([(px1, py1), (px2, py2)], outline=(225, 216, 196, 220), width=4)
                    frame.alpha_composite(sl["ed_frame"])
                    hl_prog = min(1.0, max(0.0, (lt - 0.30) / 1.10))
                    n_rects = max(1, len(sl["line_rects"]))
                    for ri, (rx1, ry1, rx2, ry2) in enumerate(sl["line_rects"]):
                        lp = min(1.0, max(0.0, hl_prog * n_rects - ri))
                        if lp > 0:
                            fd.rectangle([(int(rx2 - (rx2 - rx1) * lp), ry1), (rx2, ry2)], fill=sl["accent"] + (210,))
                    frame.alpha_composite(sl["hl_lay"])
                    draw_progress_bars(frame, s_idx, lt / dur, bar_y=46)
                    if lt < 0.22:
                        frame.alpha_composite(Image.new("RGBA", (w, h), (16, 18, 24, int(230 * (1.0 - lt / 0.22)))))
                    elif lt > (dur - 0.22):
                        frame.alpha_composite(Image.new("RGBA", (w, h), (16, 18, 24, int(230 * ((lt - (dur - 0.22)) / 0.22)))))

                elif style == "kinetic":
                    if photo_arr is not None:
                        ah, aw = photo_arr.shape[:2]
                        z = 1.04 + 0.14 * ((1.0 - min(1.0, lt / 0.35)) ** 2) + 0.05 * (lt / dur)
                        cw, ch = int(aw / z), int(ah / z)
                        bg_rgb = cv2.resize(photo_arr[(ah - ch) // 2:(ah - ch) // 2 + ch, (aw - cw) // 2:(aw - cw) // 2 + cw], (w, h), interpolation=cv2.INTER_LINEAR)
                    else:
                        bg_rgb = make_dark_gradient_bg(global_t, sl["accent"])
                    frame = Image.fromarray(bg_rgb).convert("RGBA")
                    frame.alpha_composite(vignette)
                    frame.alpha_composite(sl["k_hud"])
                    for li, lay in enumerate(sl["line_layers"]):
                        if lt >= (0.14 + li * 0.22):
                            frame.alpha_composite(lay)
                    draw_progress_bars(frame, s_idx, lt / dur, bar_y=44)
                    if lt < 0.08:
                        frame.alpha_composite(Image.new("RGBA", (w, h), (255, 255, 255, 165)))

                elif style == "live":
                    frame = Image.fromarray(make_dark_gradient_bg(global_t, (24, 58, 128))).convert("RGBA")
                    mx1, my1, mx2, my2 = 50, 256, w - 50, 1222
                    mw, mh = mx2 - mx1, my2 - my1
                    if photo_arr is not None:
                        ah, aw = photo_arr.shape[:2]
                        z = 1.0 + 0.08 * (lt / dur)
                        cw, ch = int(aw / z), int(ah / z)
                        mon_pil = Image.fromarray(cv2.resize(photo_arr[(ah - ch) // 2:(ah - ch) // 2 + ch, (aw - cw) // 2:(aw - cw) // 2 + cw], (mw, mh), interpolation=cv2.INTER_LINEAR))
                    else:
                        mon_pil = Image.fromarray(make_dark_gradient_bg(global_t * 1.4, sl["accent"])[0:mh, 0:mw])
                    mmask = Image.new("L", (mw, mh), 0)
                    ImageDraw.Draw(mmask).rounded_rectangle([(0, 0), (mw, mh)], radius=24, fill=255)
                    frame.paste(mon_pil, (mx1, my1), mmask)
                    frame.alpha_composite(sl["live_ov"])
                    if int(global_t * 3.0) % 2 == 0:
                        ImageDraw.Draw(frame).ellipse([(66, 138), (90, 162)], fill=(239, 35, 48, 255))
                    if ticker_strip is not None:
                        avail = max(1, ticker_strip.width - w)
                        src_x = avail - (int(global_t * 170) % avail)
                        frame.alpha_composite(ticker_strip.crop((src_x, 0, src_x + w, 74)), (0, 1732))
                    if lt < wipe_dur:
                        draw_broadcast_wipe(frame, "out", lt / wipe_dur)
                    elif lt > (dur - wipe_dur):
                        draw_broadcast_wipe(frame, "in", (lt - (dur - wipe_dur)) / wipe_dur)

                else:  # style == "hologram" (سبک ۶: کارت هولوگرام سه‌بعدی + ذرات + لیزر + گوینده)
                    neon_c = sl["neon"]
                    frame = Image.fromarray(make_dark_gradient_bg(global_t * 1.1, neon_c)).convert("RGBA")
                    fd = ImageDraw.Draw(frame)
                    # شبکه هولوگرامی ظریف در کف و سقف
                    for gx in range(0, w, 90):
                        fd.line([(gx, 1480), (w // 2 + (gx - w // 2) * 2, h)], fill=neon_c + (26,), width=2)
                    # ذرات نورانی معلق
                    for px0, py0, spd, rad, pcol in particles:
                        py = (py0 - global_t * spd) % h
                        px = (px0 + math.sin(global_t * 1.6 + py0 * 0.01) * 18) % w
                        fd.ellipse([(px - rad, py - rad), (px + rad, py + rad)], fill=pcol + (155,))

                    # چرخش و شناوری آرام کارت شیشه‌ای سه‌بعدی
                    base_yaw = 11.0 if (s_idx % 2 == 0) else -11.0
                    yaw = base_yaw * math.cos(lt * 0.85)
                    pitch = 4.5 * math.sin(lt * 1.1)
                    float_y = int(16 * math.sin(lt * 1.8))
                    warped = warp_3d_card_rgba(sl["holo_card"], yaw, pitch)
                    frame.alpha_composite(warped, ((w - warped.width) // 2, 310 + float_y))
                    frame.alpha_composite(sl["holo_hud"], (0, 0))
                    draw_progress_bars(frame, s_idx, lt / dur, bar_y=52, active_c=neon_c + (255,))
                    draw_rtl_text(ImageDraw.Draw(frame), (w // 2, 1785), "گزارش صوتی و تصویری اختصاصی  |  آخرین خبرهای شیراز", load_font("bold", 28), (215, 226, 240, 215), align="center", shadow=False)
                    if lt < 0.28:
                        draw_laser_wipe(frame, lt / 0.28, color=neon_c)
                    elif lt > (dur - 0.28):
                        draw_laser_wipe(frame, (lt - (dur - 0.28)) / 0.28, color=neon_c)

                yield np.array(frame.convert("RGB"), dtype=np.uint8)

        # ۳. پایان
        for i in range(int(outro_dur * fps)):
            lt = i / fps
            global_t += 1.0 / fps
            bg = make_dark_gradient_bg(global_t, (0, 175, 235) if style == "hologram" else (204, 18, 28))
            frame = apply_glass_box(bg, outro_box, radius=36, alpha=0.58)
            frame.alpha_composite(outro_ov)
            if lt < wipe_dur:
                if style == "hologram":
                    draw_laser_wipe(frame, lt / wipe_dur)
                else:
                    draw_broadcast_wipe(frame, "out", lt / wipe_dur)
            yield np.array(frame.convert("RGB"), dtype=np.uint8)

    pipe_frames_to_mp4(frame_gen(), out_mp4, audio_path, fps=fps, loop_audio=loop_audio)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۵. ریلز موج صوتی (Audiogram) ====================
def build_audiogram_reel_sync(audio_path: str, badge: str, headline: str, subtext: str, speaker_photo: str = None) -> str:
    w, h = 1080, 1920
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)
    theme = THEMES.get(CONFIG["theme"], THEMES["navy"])

    bg = Image.new("RGBA", (w, h), theme["bg"] + (255,))
    draw = ImageDraw.Draw(bg)
    draw.rectangle([(0, 0), (w, 18)], fill=theme["accent"] + (255,))
    draw.rectangle([(0, h - 18), (w, h)], fill=theme["accent"] + (255,))

    circle_r, cx, cy = 215, w // 2, 540
    draw.ellipse([(cx - circle_r - 12, cy - circle_r - 12), (cx + circle_r + 12, cy + circle_r + 12)], fill=theme["accent"] + (255,))
    if speaker_photo and os.path.exists(speaker_photo):
        sp = fit_cover(Image.open(speaker_photo).convert("RGB"), circle_r * 2, circle_r * 2)
        mask = Image.new("L", (circle_r * 2, circle_r * 2), 0)
        ImageDraw.Draw(mask).ellipse([(0, 0), (circle_r * 2, circle_r * 2)], fill=255)
        bg.paste(sp, (cx - circle_r, cy - circle_r), mask)
    else:
        draw.ellipse([(cx - circle_r, cy - circle_r), (cx + circle_r, cy + circle_r)], fill=(25, 42, 72, 255))
        draw_rtl_text(draw, (cx, cy - 34), "گزارش صوتی", load_font("display", 56), theme["text"] + (255,), align="center")

    repo_frame = find_repo_reel_frame() if CONFIG["use_repo_frame"] else ""
    wave_y = 795 if repo_frame else 1235
    if repo_frame:
        bg.alpha_composite(Image.open(render_reel_frame_overlay(repo_frame, badge or "گزارش صوتی", headline, subtext, work_dir)).convert("RGBA"))
    else:
        draw_rtl_text(draw, (w // 2, 145), "گزارش صوتی اختصاصی", load_font("bold", 40), theme["accent"] + (255,), align="center")
        draw_rtl_text(draw, (w // 2, 210), BRAND_TITLE_FA, load_font("display", 54), theme["text"] + (255,), align="center")
        draw_centered_block_in_box(draw, (70, 820, w - 70, 1170), headline, "display", theme["text"] + (255,), max_size=68, min_size=30, max_lines=3)
        draw.rounded_rectangle([(60, 1210), (w - 60, 1490)], radius=24, fill=(0, 0, 0, 100), outline=theme["accent"] + (160,), width=3)
        draw_rtl_text(draw, (w // 2, 1630), BRAND_HANDLE, load_font("bold", 38), theme["accent"] + (255,), align="center", is_rtl=False)

    bg_path = os.path.join(work_dir, "audio_bg.png")
    bg.convert("RGB").save(bg_path)
    out_mp4 = os.path.join(TMP_ROOT, f"audiogram_{int(time.time()*1000)}.mp4")
    run_ffmpeg([
        "ffmpeg", "-y", "-loop", "1", "-i", bg_path, "-i", audio_path,
        "-filter_complex",
        f"[1:a]showwaves=s=920x190:mode=cline:rate=25:colors={theme['wave_hex']}[w];"
        f"[0:v][w]overlay=(W-w)/2:{wave_y}:shortest=1,format=yuv420p[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out_mp4,
    ])
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۶. استودیو تدوین ویدئو + قلاب‌گذار مستقل کاغذ سوخته ====================
def probe_video_info(video_path: str) -> dict:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", video_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    info = {"width": 1080, "height": 1920, "duration": 10.0, "has_audio": False}
    try:
        data = json.loads(res.stdout)
        info["duration"] = float(data.get("format", {}).get("duration", 10.0))
        for st in data.get("streams", []):
            if st.get("codec_type") == "video":
                info["width"] = int(st.get("width", 1080))
                info["height"] = int(st.get("height", 1920))
            elif st.get("codec_type") == "audio":
                info["has_audio"] = True
    except Exception:
        pass
    return info


def detect_face_center_x(video_path: str) -> int:
    try:
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
        xs = []
        for i in range(1, 10):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i / 10.0)))
            ok, frame = cap.read()
            if not ok:
                continue
            faces = detector.detectMultiScale(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 1.15, 5, minSize=(45, 45))
            if len(faces) > 0:
                largest = max(faces, key=lambda f: f[2] * f[3])
                xs.append(int(largest[0] + largest[2] / 2))
        cap.release()
        if xs:
            xs.sort()
            return xs[len(xs) // 2]
    except Exception:
        pass
    return -1


def build_endscreen_clip_sync(work_dir: str, duration: float = 2.2, with_silent_audio: bool = False) -> str:
    theme = THEMES.get(CONFIG["theme"], THEMES["navy"])
    im = Image.new("RGB", (1080, 1920), theme["bg"])
    d = ImageDraw.Draw(im)
    d.rectangle([(0, 0), (1080, 22)], fill=theme["accent"])
    d.rectangle([(0, 1898), (1080, 1920)], fill=theme["accent"])
    draw_rtl_text(d, (540, 740), BRAND_TITLE_FA, load_font("display", 84), theme["text"], align="center")
    draw_rtl_text(d, (540, 880), "برای پیگیری لحظه‌ای اخبار شیراز و فارس فالو کنید", load_font("bold", 38), theme["subtext"], align="center")
    d.rounded_rectangle([(260, 990), (820, 1100)], radius=20, fill=theme["accent"])
    draw_rtl_text(d, (540, 1018), BRAND_HANDLE, load_font("bold", 48), (15, 23, 42), align="center", shadow=False, is_rtl=False)

    img_p = os.path.join(work_dir, "endscreen.jpg")
    im.save(img_p, quality=92)
    mp4_p = os.path.join(work_dir, "endscreen.mp4")
    cmd = ["ffmpeg", "-y", "-loop", "1", "-t", str(duration), "-i", img_p]
    if with_silent_audio:
        cmd += ["-f", "lavfi", "-t", str(duration), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    cmd += ["-vf", "scale=1080:1920,fps=25,format=yuv420p,setsar=1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]
    if with_silent_audio:
        cmd += ["-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k"]
    cmd += ["-t", str(duration), mp4_p]
    run_ffmpeg(cmd)
    return mp4_p


def apply_burnt_hook_to_video_sync(video_path: str, line1: str, line2: str) -> str:
    """ابزار سریع و مستقل: اعمال لایه شفاف قلاب دوطبقه کاغذ سوخته فقط در ۰ تا ۳ ثانیه اول هر ویدئو."""
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)
    info = probe_video_info(video_path)
    vw, vh = info["width"], info["height"]
    hook_png = render_burnt_paper_hook_png(line1, line2, os.path.join(work_dir, "burnt_hook.png"), width=vw, height=vh)
    out_mp4 = os.path.join(TMP_ROOT, f"burnt_hook_{int(time.time()*1000)}.mp4")
    # فرمول ایمن بدون کاما: not(floor(t/3)) دقیقاً از ثانیه 0 تا 2.999 فعال است و رأس 3:00 محو می‌شود
    cmd = [
        "ffmpeg", "-y", "-i", video_path, "-loop", "1", "-i", hook_png,
        "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1:enable='not(floor(t/3))',format=yuv420p[vout]",
        "-map", "[vout]",
    ]
    if info["has_audio"]:
        cmd += ["-map", "0:a", "-c:a", "copy"]
    cmd += ["-map_metadata", "-1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-movflags", "+faststart", out_mp4]
    run_ffmpeg(cmd)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


def build_photo_hook_reel_sync(photo_path: str, badge: str, headline: str, subtext: str, hook_lines: tuple = None) -> str:
    """تبدیل سریع عکس خبر به ریلز ۱۰ ثانیه‌ای با زوم آرام + قاب ۳ باکسه + قلاب کاغذ سوخته در ۳ ثانیه اول (برای بسته کامل)."""
    w, h, fps, duration = 1080, 1920, 25, 10.0
    total_frames = int(fps * duration)
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)

    bg_arr = np.array(fit_cover(Image.open(photo_path).convert("RGB"), 1240, 2204), dtype=np.uint8) if (photo_path and os.path.exists(photo_path)) else np.full((2204, 1240, 3), (18, 22, 32), dtype=np.uint8)
    repo_frame = find_repo_reel_frame() if CONFIG["use_repo_frame"] else ""
    frame_ov = Image.open(render_reel_frame_overlay(repo_frame, badge, headline, subtext, work_dir)).convert("RGBA") if repo_frame else None
    hook_ov = Image.open(render_burnt_paper_hook_png(hook_lines[0], hook_lines[1], os.path.join(work_dir, "pk_hook.png"), w, h)).convert("RGBA") if hook_lines else None
    ticker_strip = build_scrolling_ticker_strip(f"{headline} — {subtext}", duration + 2.0, bg_color=(185, 28, 28, 240), height=68) if CONFIG.get("video_ticker", True) else None
    audio_path = get_audio_track(work_dir, duration, mode="news")
    out_mp4 = os.path.join(TMP_ROOT, f"pack_reel_{int(time.time()*1000)}.mp4")

    def frame_gen():
        ah, aw = bg_arr.shape[:2]
        for i in range(total_frames):
            t = i / fps
            z = 1.0 + 0.12 * (t / duration)
            cw, ch = int(aw / z), int(ah / z)
            rgb = cv2.resize(bg_arr[(ah - ch) // 2:(ah - ch) // 2 + ch, (aw - cw) // 2:(aw - cw) // 2 + cw], (w, h), interpolation=cv2.INTER_LINEAR)
            frame = Image.fromarray(rgb).convert("RGBA")
            if frame_ov is not None:
                frame.alpha_composite(frame_ov)
            if ticker_strip is not None:
                avail = max(1, ticker_strip.width - w)
                src_x = avail - (int(t * 165) % avail)
                frame.alpha_composite(ticker_strip.crop((src_x, 0, src_x + w, 68)), (0, 1795))
            if hook_ov is not None and t < 3.0:
                frame.alpha_composite(hook_ov)
            yield np.array(frame.convert("RGB"), dtype=np.uint8)

    pipe_frames_to_mp4(frame_gen(), out_mp4, audio_path, fps=fps)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


def process_video_studio_sync(video_path: str, badge: str, headline: str, subtext: str, hook_lines: tuple = None) -> tuple:
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)
    info = probe_video_info(video_path)
    w, h, has_audio, dur = info["width"], info["height"], info["has_audio"], info["duration"]

    applied = []
    use_antidup = CONFIG["video_antidup"]
    use_facetrack = CONFIG["video_facetrack"]
    use_brand = CONFIG["video_brand"]
    use_ticker = CONFIG.get("video_ticker", True)
    repo_frame = find_repo_reel_frame() if CONFIG["use_repo_frame"] else ""

    if use_facetrack and w > h:
        face_x = detect_face_center_x(video_path)
        if face_x >= 0:
            crop_w = min(w, max(16, int(h * 9 / 16)))
            crop_x = max(0, min(w - crop_w, face_x - crop_w // 2))
            v_chain = f"[0:v]crop={crop_w}:{h}:{crop_x}:0,scale=1080:1920:flags=lanczos"
            applied.append("ردیابی چهره ۹:۱۶ ✅")
        else:
            v_chain = "[0:v]split[orig][bg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[b];[orig]scale=1080:-2[f];[b][f]overlay=(W-w)/2:(H-h)/2"
            applied.append("تبدیل ۹:۱۶ با پس‌زمینه تار ✅")
    else:
        v_chain = "[0:v]split[orig][bg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[b];[orig]scale=1080:1920:force_original_aspect_ratio=decrease[f];[b][f]overlay=(W-w)/2:(H-h)/2"

    if use_antidup:
        v_chain += ",scale=1112:1978,crop=1080:1920,eq=contrast=1.02:saturation=1.03:brightness=0.008,setpts=PTS/1.015"
        applied.append("اصالت‌سازی و حذف متادیتا ✅")

    v_chain += ",fps=25,setsar=1,format=rgba[cur0]"
    cur_label = "cur0"
    inputs = ["-i", video_path]
    inp_idx = 1

    if repo_frame:
        filled_fr = render_reel_frame_overlay(repo_frame, badge, headline, subtext, work_dir)
        inputs += ["-loop", "1", "-i", filled_fr]
        v_chain += f";[{cur_label}][{inp_idx}:v]overlay=0:0:shortest=1[cur{inp_idx}]"
        cur_label = f"cur{inp_idx}"
        inp_idx += 1
        applied.append("قاب ۳ باکسه ریلز با متن خودکار ✅")

    if use_ticker and headline:
        t_path = os.path.join(work_dir, "ticker.png")
        build_scrolling_ticker_strip(f"{headline} — {subtext}", dur + 2.0, bg_color=(185, 28, 28, 240), height=68).save(t_path, format="PNG")
        inputs += ["-loop", "1", "-i", t_path]
        v_chain += f";[{cur_label}][{inp_idx}:v]overlay=x='-w+1080+165*t':y=1795:shortest=1[cur{inp_idx}]"
        cur_label = f"cur{inp_idx}"
        inp_idx += 1
        applied.append("نوار زیرنویس متحرک شبکه خبر ✅")

    # قلاب دوطبقه کاغذ سوخته فقط در ۳ ثانیه اول (۰ تا ۳ ثانیه — محو کامل در ثانیه ۳:۰۰)
    if hook_lines and hook_lines[0] and hook_lines[1]:
        hook_png = render_burnt_paper_hook_png(hook_lines[0], hook_lines[1], os.path.join(work_dir, "studio_hook.png"), 1080, 1920)
        inputs += ["-loop", "1", "-i", hook_png]
        v_chain += f";[{cur_label}][{inp_idx}:v]overlay=0:0:shortest=1:enable='not(floor(t/3))'[cur{inp_idx}]"
        cur_label = f"cur{inp_idx}"
        inp_idx += 1
        applied.append("قلاب دوطبقه کاغذ سوخته (۰ تا ۳ ثانیه) ✅")

    v_chain += f";[{cur_label}]format=yuv420p[vout]"
    main_processed = os.path.join(work_dir, "main_proc.mp4")
    cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", v_chain, "-map", "[vout]"]
    if has_audio:
        if use_antidup:
            cmd += ["-filter:a", "atempo=1.015"]
        cmd += ["-map", "0:a", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k"]
    cmd += ["-map_metadata", "-1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-movflags", "+faststart", main_processed]
    run_ffmpeg(cmd)

    out_mp4 = os.path.join(TMP_ROOT, f"studio_vid_{int(time.time()*1000)}.mp4")
    if use_brand:
        end_clip = build_endscreen_clip_sync(work_dir, duration=2.2, with_silent_audio=has_audio)
        applied.append("اند-اسکرین دعوت به فالو ✅")
        c_cmd = ["ffmpeg", "-y", "-i", main_processed, "-i", end_clip]
        if has_audio:
            c_cmd += ["-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k"]
        else:
            c_cmd += ["-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]"]
        c_cmd += ["-map_metadata", "-1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-movflags", "+faststart", out_mp4]
        run_ffmpeg(c_cmd)
    else:
        shutil.copy(main_processed, out_mp4)

    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4, applied


# ==================== ۷. حذف واترمارک و لوگوی خبرگزاری‌ها از ۴ گوشه ====================
def calc_corner_rect(w: int, h: int, corner: str) -> tuple:
    rw, rh = max(60, int(w * 0.24)), max(45, int(h * 0.12))
    margin = max(8, int(min(w, h) * 0.015))
    if corner == "tr":
        return w - rw - margin, margin, rw, rh
    if corner == "tl":
        return margin, margin, rw, rh
    if corner == "br":
        return w - rw - margin, h - rh - margin, rw, rh
    return margin, h - rh - margin, rw, rh


def clean_corner_logo_photo_sync(photo_path: str, corner: str) -> str:
    img = cv2.imread(photo_path)
    h, w = img.shape[:2]
    x, y, rw, rh = calc_corner_rect(w, h, corner)
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[y:y + rh, x:x + rw] = 255
    cleaned = cv2.inpaint(img, mask, 9, cv2.INPAINT_TELEA)
    out_p = os.path.join(TMP_ROOT, f"clean_logo_{int(time.time()*1000)}.jpg")
    cv2.imwrite(out_p, cleaned, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return out_p


def clean_corner_logo_video_sync(video_path: str, corner: str) -> str:
    info = probe_video_info(video_path)
    w, h = info["width"], info["height"]
    x, y, rw, rh = calc_corner_rect(w, h, corner)
    x, y = max(2, min(w - rw - 2, x)), max(2, min(h - rh - 2, y))
    out_mp4 = os.path.join(TMP_ROOT, f"clean_logo_{int(time.time()*1000)}.mp4")
    run_ffmpeg([
        "ffmpeg", "-y", "-i", video_path, "-vf", f"delogo=x={x}:y={y}:w={rw}:h={rh}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "copy",
        "-map_metadata", "-1", "-movflags", "+faststart", out_mp4,
    ])
    return out_mp4


# ==================== ۸. کارت مناسبت امروز + استوری زنده هواشناسی شیراز ====================
async def build_daily_occasion_card(session: aiohttp.ClientSession) -> tuple:
    jnow = jdatetime.datetime.fromgregorian(datetime=get_tehran_now())
    wd, day_str, month_str, year_str = JALALI_WEEKDAYS[jnow.weekday()], to_persian_digits(str(jnow.day)), JALALI_MONTHS[jnow.month], to_persian_digits(str(jnow.year))
    full_date = f"{wd} {day_str} {month_str} {year_str}"
    occasion = SHAMSI_OCCASIONS.get((jnow.month, jnow.day), "")
    if not occasion and GEMINI_API_KEY:
        occasion = await gemini_generate(
            session,
            f"امروز {full_date} هجری شمسی است. فقط در یک جمله بسیار کوتاه و بدون ایموجی (حداکثر ۱۰ کلمه) مهم‌ترین مناسبت رسمی یا فرهنگی امروز در ایران یا شیراز را بنویس (اگر مناسبت خاصی نیست، یک جمله باوقار صبح‌بخیر شیراز بنویس).",
        )
    if not occasion:
        occasion = "صبح بخیر شیراز؛ همراه لحظه‌به‌لحظه خبرهای استان فارس"

    def draw_card():
        theme = THEMES.get(CONFIG["theme"], THEMES["navy"])
        w, h = 1080, 1920
        im = Image.new("RGB", (w, h), theme["bg"])
        d = ImageDraw.Draw(im)
        d.rectangle([(0, 0), (w, 26)], fill=theme["accent"])
        d.rectangle([(0, h - 26), (w, h)], fill=theme["accent"])
        d.rounded_rectangle([(64, 150), (w - 64, h - 180)], radius=36, outline=theme["accent"], width=4)
        draw_rtl_text(d, (w // 2, 260), "تقویم روزانه", load_font("bold", 44), theme["accent"], align="center")
        draw_rtl_text(d, (w // 2, 340), BRAND_TITLE_FA, load_font("display", 66), theme["text"], align="center")
        d.ellipse([(w // 2 - 210, 530), (w // 2 + 210, 950)], fill=theme["accent"])
        draw_rtl_text(d, (w // 2, 625), day_str, load_font("display", 210), theme["bg"], align="center", shadow=False)
        draw_rtl_text(d, (w // 2, 1020), f"{wd}  |  {month_str} {year_str}", load_font("display", 72), theme["text"], align="center")
        d.line([(200, 1150), (w - 200, 1150)], fill=theme["accent"], width=4)
        draw_centered_block_in_box(d, (110, 1190, w - 110, 1520), occasion, "bold", theme["subtext"], max_size=46, min_size=28, max_lines=3, align="center")
        draw_rtl_text(d, (w // 2, 1620), BRAND_HANDLE, load_font("bold", 42), theme["accent"], align="center", is_rtl=False)
        out = os.path.join(TMP_ROOT, f"occasion_{int(time.time()*1000)}.jpg")
        im.save(out, quality=94)
        return out

    return await asyncio.to_thread(draw_card), f"📅 {full_date}\n\n{strip_emojis_for_font(occasion)}\n\n🔔 {BRAND_HANDLE}"


async def build_shiraz_weather_story(session: aiohttp.ClientSession) -> tuple:
    """دریافت دمای لحظه‌ای و پیش‌بینی امروز شیراز و شهرهای اصلی فارس و تولید استوری رسمی."""
    cities = [("شیراز", 29.5918, 52.5837), ("مرودشت", 29.8742, 52.8025), ("جهرم", 28.5000, 53.5605), ("کازرون", 29.6195, 51.6541), ("سپیدان", 30.2606, 51.9810)]
    wmo_fa = {0: "آسمان صاف", 1: "عمدتاً صاف", 2: "نیمه‌ابری", 3: "ابری", 45: "مه‌آلود", 51: "نم‌نم باران", 61: "بارانی", 63: "باران متوسط", 65: "باران شدید", 71: "برفی", 80: "رگبار باران", 95: "رعدوبرق"}

    async def fetch_city(name, lat, lon):
        url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": lat, "longitude": lon, "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code", "daily": "temperature_2m_max,temperature_2m_min", "timezone": "Asia/Tehran", "forecast_days": 1}
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    d = await r.json()
                    cur, day = d.get("current", {}), d.get("daily", {})
                    code = int(cur.get("weather_code", 0))
                    desc = wmo_fa.get(code, "نیمه‌ابری" if code < 50 else "بارانی")
                    return {
                        "name": name, "temp": round(float(cur.get("temperature_2m", 20))),
                        "hum": round(float(cur.get("relative_humidity_2m", 35))),
                        "wind": round(float(cur.get("wind_speed_10m", 10))),
                        "tmax": round(float((day.get("temperature_2m_max") or [24])[0])),
                        "tmin": round(float((day.get("temperature_2m_min") or [10])[0])),
                        "desc": desc,
                    }
        except Exception:
            pass
        return {"name": name, "temp": 20, "hum": 35, "wind": 10, "tmax": 24, "tmin": 10, "desc": "آسمان صاف"}

    results = await asyncio.gather(*(fetch_city(n, la, lo) for n, la, lo in cities))
    shz, others = results[0], results[1:]
    jnow = jdatetime.datetime.fromgregorian(datetime=get_tehran_now())
    date_str = to_persian_digits(f"{JALALI_WEEKDAYS[jnow.weekday()]} {jnow.day} {JALALI_MONTHS[jnow.month]} {jnow.year}")

    def draw_weather():
        w, h = 1080, 1920
        canvas = Image.new("RGBA", (w, h), (19, 20, 24, 255))
        draw = ImageDraw.Draw(canvas)
        # نوار قرمز اریب بالا سمت راست + لوگوی دروازه قرآن
        draw.polygon([(480, 46), (1080, 46), (1080, 206), (412, 206)], fill=(204, 18, 28, 255))
        draw_centered_block_in_box(draw, (475, 56, 1050, 196), "هواشناسی شیراز و فارس", "bold", (255, 255, 255, 255), max_size=50, min_size=30, max_lines=1)
        lg_p = find_repo_logo()
        if lg_p:
            try:
                lg = Image.open(lg_p).convert("RGBA")
                lg.thumbnail((130, 100), Image.Resampling.LANCZOS)
                canvas.alpha_composite(lg, (70, 46))
            except Exception:
                draw_quran_gate_fallback(draw, 70, 46, 100)
        else:
            draw_quran_gate_fallback(draw, 70, 46, 100)

        draw_rtl_text(draw, (w // 2, 265), date_str, load_font("bold", 36), (205, 212, 224, 235), align="center", shadow=False)

        # کارت اصلی دمای شیراز
        draw.rounded_rectangle([(62, 345), (w - 62, 955)], radius=36, fill=(28, 32, 42, 255), outline=(204, 18, 28, 220), width=4)
        draw_rtl_text(draw, (w // 2, 395), "دمای لحظه‌ای کلان‌شهر شیراز", load_font("bold", 42), (242, 200, 68, 255), align="center", shadow=False)
        draw_rtl_text(draw, (w // 2, 485), f"{to_persian_digits(str(shz['temp']))}°", load_font("display", 220), (255, 255, 255, 255), align="center", shadow=True, is_rtl=False)
        draw_rtl_text(draw, (w // 2, 745), shz["desc"], load_font("bold", 48), (225, 232, 242, 255), align="center", shadow=False)
        meta_line = f"بیشینه {to_persian_digits(str(shz['tmax']))}°   |   کمینه {to_persian_digits(str(shz['tmin']))}°   |   رطوبت {to_persian_digits(str(shz['hum']))}%"
        draw_rtl_text(draw, (w // 2, 845), meta_line, load_font("bold", 32), (185, 196, 212, 240), align="center", shadow=False)

        # جدول شهرهای اصلی استان فارس
        draw_rtl_text(draw, (w - 72, 1015), "وضعیت شهرهای استان فارس", load_font("bold", 38), (255, 255, 255, 255), align="right", shadow=False)
        ry = 1095
        for c in others:
            draw.rounded_rectangle([(62, ry), (w - 62, ry + 132)], radius=22, fill=(28, 32, 42, 255), outline=(70, 76, 90, 180), width=2)
            draw_rtl_text(draw, (w - 102, ry + 36), c["name"], load_font("bold", 42), (255, 255, 255, 255), align="right", shadow=False)
            draw_rtl_text(draw, (w // 2 + 20, ry + 42), c["desc"], load_font("regular", 32), (195, 204, 218, 235), align="center", shadow=False)
            draw_rtl_text(draw, (105, ry + 32), f"{to_persian_digits(str(c['temp']))}°", load_font("display", 56), (242, 200, 68, 255), align="left", shadow=False, is_rtl=False)
            ry += 156

        # نوار فوتر رسمی پیج
        draw.rectangle([(0, 1794), (w, 1884)], fill=(36, 39, 44, 255))
        draw.polygon([(0, 1794), (275, 1794), (235, 1884), (0, 1884)], fill=(204, 18, 28, 255))
        draw_rtl_text(draw, (w - 54, 1818), f"هواشناسی لحظه‌ای  |  {BRAND_TITLE_FA}", load_font("bold", 30), (245, 247, 250, 255), align="right", shadow=False)
        draw_rtl_text(draw, (285, 1820), BRAND_HANDLE, load_font("bold", 28), (210, 218, 230, 235), align="left", shadow=False, is_rtl=False)

        out = os.path.join(TMP_ROOT, f"weather_shz_{int(time.time()*1000)}.jpg")
        canvas.convert("RGB").save(out, quality=94)
        return out

    card_p = await asyncio.to_thread(draw_weather)
    cap = f"🌤️ وضعیت آب‌وهوای شیراز ({date_str})\nدمای فعلی: {to_persian_digits(str(shz['temp']))} درجه | {shz['desc']}\n\n🔔 {BRAND_HANDLE}"
    return card_p, cap
    # ==================== ارسال کپشن + سپر ضدشدوبن و پیش‌نمایش قلاب کاغذ سوخته ====================
async def send_caption_with_shield(session: aiohttp.ClientSession, chat_id: str, caption: str, back_kb: dict = None):
    LAST_CAPTION[chat_id] = caption
    menu_kb = back_kb or kb_main_menu()
    if CONFIG["auto_shadowban"]:
        hits = check_shadowban_words(caption)
        if hits:
            await send_message(session, chat_id, caption)
            lines = ["🛡️ هشدار سپر ضدشدوبن — کلمات حساس شناسایی‌شده در کپشن:"]
            for w, alt in hits[:6]:
                lines.append(f"• «{w}» ← پیشنهاد ایمن: {alt}")
            lines.append("\nبرای اصلاح خودکار، دکمه «✨ بازنویسی ایمن آخرین کپشن» را از منوی پایین صفحه بزنید.")
            await send_message(session, chat_id, "\n".join(lines), kb_shadowban_actions())
            return
    await send_message(session, chat_id, caption, menu_kb)


async def send_hook_preview(session: aiohttp.ClientSession, chat_id: str, line1: str, line2: str, target_title: str):
    preview_txt = (
        f"🔥 پیش‌نمایش «قلاب دوطبقه کاغذ سوخته» ({target_title})\n"
        "این قلاب فقط از ثانیه ۰ تا ثانیه ۳ روی ویدئو نمایش داده می‌شود:\n\n"
        f"🟨 سطر ۱ (کاغذ کرم بالا): {line1}\n"
        f"🟥 سطر ۲ (کاغذ قرمز پایین): {line2}\n\n"
        "اگر متن دقیق است «✅ تایید و ساخت ویدئو» را بزنید، یا آن را ویرایش/تولید مجدد کنید:"
    )
    await send_message(session, chat_id, preview_txt, kb_hook_confirm())


# ==================== اجرای کارهای ویدئویی و پردازشی در پس‌زمینه ====================
async def run_daily60_job(session: aiohttp.ClientSession, chat_id: str, style_key: str = "broadcast", style_title: str = "برودکست شیشه‌ای"):
    nar_dir = None
    try:
        items_copy = list(DAILY_ITEMS[-8:])
        narration_plan = None
        if style_key == "hologram":
            nar_dir = tempfile.mkdtemp(dir=TMP_ROOT)
            await send_message(session, chat_id, "🗣️ در حال اعراب‌گذاری دقیق متن‌ها، تولید صدای گوینده رادیویی اختصاصی و میکس صوتی...")
            narration_plan = await prepare_hologram_narration_audio(session, items_copy, nar_dir)

        mp4 = await asyncio.to_thread(build_daily_summary_reel_sync, items_copy, style_key, narration_plan)
        voice_note = "\n🎙️ گویندگی فارسی اعراب‌گذاری‌شده و میکس اختصاصی انجام شد." if (narration_plan and narration_plan.get("narrated")) else ""
        await send_video_file(
            session,
            chat_id,
            mp4,
            caption=(
                f"🎬 ریلز جمع‌بندی سبک «{style_title}» ({to_persian_digits(str(len(items_copy)))} خبر) آماده انتشار است!{voice_note}\n"
                "💡 خبرها هنوز در صف ذخیره هستند؛ می‌توانید با سبک‌های دیگر هم خروجی بگیرید."
            ),
        )
        if CONFIG.get("make_grid_cover", True) and items_copy:
            first_photo = next((it.get("photo") for it in items_copy if it.get("photo") and os.path.exists(it["photo"])), "")
            cov = await asyncio.to_thread(render_reel_grid_cover_sync, first_photo, "بسته خبری امروز", "۶۰ ثانیه با اخبار شیراز و فارس")
            await send_photo_file(session, chat_id, cov, caption="🧩 کاور گرید ۴:۵ هماهنگ با پروفایل")
            if os.path.exists(cov):
                os.remove(cov)

        headlines_text = "\n".join(f"- {it['headline']}" for it in items_copy)
        cap = await generate_editorial_caption(session, f"جمع‌بندی مهم‌ترین اخبار امروز شیراز و استان فارس:\n{headlines_text}")
        await send_caption_with_shield(session, chat_id, cap, back_kb=kb_daily_collect())
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در ساخت ریلز ({style_title}):\n{e}", kb_daily_collect())
    finally:
        if nar_dir:
            shutil.rmtree(nar_dir, ignore_errors=True)


async def run_incident_job(session: aiohttp.ClientSession, chat_id: str, photo_path: str, news_text: str):
    try:
        cap = await generate_editorial_caption(
            session,
            news_text=news_text,
            media_path=photo_path or None,
            mime_type="image/jpeg" if photo_path else None,
            force_incident=True,
        )
        source_for_parts = news_text if len(news_text) >= 15 else cap
        _, hl, sub = await extract_news_parts(session, source_for_parts, is_incident=True)
        mp4 = await asyncio.to_thread(build_incident_reel_sync, photo_path, hl, sub)
        await send_video_file(session, chat_id, mp4, caption="🚨 ریلز فوری و حادثه‌ای آماده انتشار است.")
        if CONFIG.get("make_grid_cover", True):
            cov = await asyncio.to_thread(render_reel_grid_cover_sync, photo_path, "فوری | حادثه", hl)
            await send_photo_file(session, chat_id, cov, caption="🧩 کاور گرید ۴:۵ هماهنگ با پروفایل")
            if os.path.exists(cov):
                os.remove(cov)
        await send_caption_with_shield(session, chat_id, cap, back_kb=kb_cat_reels())
        add_to_daily_items(hl, photo_path, tag="خبر فوری")
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در تولید ریلز حادثه‌ای:\n{e}", kb_cat_reels())


async def run_map_job(session: aiohttp.ClientSession, chat_id: str, loc_name: str, photo_path: str, news_text: str):
    try:
        lat, lon, close_zoom = await resolve_location_coords(session, loc_name)
        wide_zoom = max(7, close_zoom - 3)
        wide_map, close_map = await asyncio.gather(
            fetch_reliable_map_image(session, lat, lon, wide_zoom),
            fetch_reliable_map_image(session, lat, lon, close_zoom),
        )
        cap = await generate_editorial_caption(
            session,
            news_text=f"موقعیت خبر: {loc_name}\n{news_text}",
            media_path=photo_path or None,
            mime_type="image/jpeg" if photo_path else None,
        )
        source_for_parts = news_text if len(news_text) >= 15 else cap
        badge, hl, sub = await extract_news_parts(session, source_for_parts)
        mp4 = await asyncio.to_thread(build_map_zoom_reel_sync, wide_map, close_map, photo_path, loc_name, badge, hl, sub)
        await send_video_file(session, chat_id, mp4, caption=f"🗺️ ریلز زوم دومرحله‌ای روی نقشه «{loc_name}» آماده است.")
        if CONFIG.get("make_grid_cover", True):
            cov = await asyncio.to_thread(render_reel_grid_cover_sync, photo_path, f"گزارش از {loc_name}", hl)
            await send_photo_file(session, chat_id, cov, caption="🧩 کاور گرید ۴:۵ هماهنگ با پروفایل")
            if os.path.exists(cov):
                os.remove(cov)
        await send_caption_with_shield(session, chat_id, cap, back_kb=kb_cat_reels())
        add_to_daily_items(hl, photo_path, tag=loc_name)
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در ساخت ریلز نقشه:\n{e}", kb_cat_reels())


async def run_audiogram_job(session: aiohttp.ClientSession, chat_id: str, audio_path: str, speaker_photo: str, raw_title: str):
    try:
        cap = await generate_editorial_caption(
            session,
            news_text=f"تیتر گزارش صوتی: {raw_title}",
            media_path=audio_path,
            mime_type="audio/ogg",
        )
        source_for_parts = raw_title if len(raw_title) >= 15 else cap
        badge, hl, sub = await extract_news_parts(session, source_for_parts)
        mp4 = await asyncio.to_thread(build_audiogram_reel_sync, audio_path, badge or "گزارش صوتی", hl, sub, speaker_photo)
        await send_video_file(session, chat_id, mp4, caption="🎙️ ریلز موج صوتی آماده است.")
        await send_caption_with_shield(session, chat_id, cap, back_kb=kb_cat_reels())
        add_to_daily_items(hl, speaker_photo, tag="صوتی")
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در ساخت ریلز صوتی:\n{e}", kb_cat_reels())


async def run_hook_only_job(session: aiohttp.ClientSession, chat_id: str, vid_path: str, line1: str, line2: str, user_caption: str = ""):
    try:
        out_mp4 = await asyncio.to_thread(apply_burnt_hook_to_video_sync, vid_path, line1, line2)
        await send_video_file(
            session,
            chat_id,
            out_mp4,
            caption=f"🔥 قلاب دوطبقه کاغذ سوخته (۰ تا ۳ ثانیه) روی ویدئو اعمال شد:\n• سطر ۱: {line1}\n• سطر ۲: {line2}",
            reply_markup=kb_cat_reels(),
        )
        if CONFIG.get("make_grid_cover", True):
            tdir = tempfile.mkdtemp(dir=TMP_ROOT)
            thumb = await asyncio.to_thread(extract_video_thumbnail_sync, vid_path, tdir)
            cov = await asyncio.to_thread(render_reel_grid_cover_sync, thumb, "خبر فوری", f"{line1} {line2}")
            await send_photo_file(session, chat_id, cov, caption="🧩 کاور گرید ۴:۵ هماهنگ با پروفایل", reply_markup=kb_cat_reels())
            shutil.rmtree(tdir, ignore_errors=True)
            if os.path.exists(cov):
                os.remove(cov)
        if os.path.exists(out_mp4):
            os.remove(out_mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در اعمال قلاب کاغذ سوخته:\n{e}", kb_cat_reels())


async def run_video_studio_job(session: aiohttp.ClientSession, chat_id: str, vid_path: str, user_caption: str, hook_lines: tuple = None, cached_cap: str = ""):
    try:
        cap = cached_cap or await generate_editorial_caption(session, news_text=user_caption, media_path=vid_path, mime_type="video/mp4")
        source_for_parts = user_caption if len(user_caption) >= 15 else cap
        badge, hl, sub = await extract_news_parts(session, source_for_parts)
        out_mp4, applied = await asyncio.to_thread(process_video_studio_sync, vid_path, badge, hl, sub, hook_lines)
        summary = (
            "🎞️ ویدئو با موفقیت تدوین شد:\n"
            + "\n".join(f"• {a}" for a in applied)
            + f"\n\n🏷️ برچسب: {badge}\n📝 تیتر: {hl}"
        )
        await send_video_file(session, chat_id, out_mp4, caption=summary)
        if CONFIG.get("make_grid_cover", True):
            tdir = tempfile.mkdtemp(dir=TMP_ROOT)
            thumb = await asyncio.to_thread(extract_video_thumbnail_sync, vid_path, tdir)
            cov = await asyncio.to_thread(render_reel_grid_cover_sync, thumb, badge, hl)
            await send_photo_file(session, chat_id, cov, caption="🧩 کاور گرید ۴:۵ هماهنگ با پروفایل")
            shutil.rmtree(tdir, ignore_errors=True)
            if os.path.exists(cov):
                os.remove(cov)
        await send_caption_with_shield(session, chat_id, cap, back_kb=kb_cat_reels())
        add_to_daily_items(hl, None, tag=badge)
        if os.path.exists(out_mp4):
            os.remove(out_mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در پردازش ویدئو:\n{e}", kb_cat_reels())


async def run_one_tap_pack_job(
    session: aiohttp.ClientSession, chat_id: str, photo_path: str, vid_path: str, news_text: str, hook_lines: tuple = None, cached_cap: str = ""
):
    """بسته کامل انتشار با یک کلیک: استوری رسمی پیج + ریلز (با قلاب کاغذ سوخته) + کاور ۴:۵ + کپشن ۶ بخشی."""
    tdir = tempfile.mkdtemp(dir=TMP_ROOT)
    try:
        media_for_ai = vid_path if vid_path else (photo_path or None)
        mime_for_ai = "video/mp4" if vid_path else ("image/jpeg" if photo_path else None)
        cap = cached_cap or await generate_editorial_caption(session, news_text=news_text, media_path=media_for_ai, mime_type=mime_for_ai)
        source_for_parts = news_text if len(news_text) >= 15 else cap
        badge, hl, sub = await extract_news_parts(session, source_for_parts)
        src_name = extract_source_name(news_text) or extract_source_name(cap)

        still_img = photo_path
        if not still_img and vid_path:
            still_img = await asyncio.to_thread(extract_video_thumbnail_sync, vid_path, tdir)

        # ۱. استوری رسمی پیج
        story_p = await asyncio.to_thread(render_brand_story_sync, still_img, badge, hl, sub, src_name)
        await send_photo_file(session, chat_id, story_p, caption="۱/۳ 📱 استوری رسمی آماده انتشار")

        # ۲. ریلز با قلاب دوطبقه کاغذ سوخته
        if vid_path:
            reel_mp4, _ = await asyncio.to_thread(process_video_studio_sync, vid_path, badge, hl, sub, hook_lines)
        else:
            reel_mp4 = await asyncio.to_thread(build_photo_hook_reel_sync, still_img, badge, hl, sub, hook_lines)
        await send_video_file(session, chat_id, reel_mp4, caption="۲/۳ 🎬 ریلز آماده انتشار (همراه با قلاب کاغذ سوخته ۳ ثانیه‌ای)")

        # ۳. کاور گرید ۴:۵
        if CONFIG.get("make_grid_cover", True):
            cov_p = await asyncio.to_thread(render_reel_grid_cover_sync, still_img, badge, hl)
            await send_photo_file(session, chat_id, cov_p, caption="۳/۳ 🧩 کاور گرید ۴:۵ هماهنگ با پروفایل")
            if os.path.exists(cov_p):
                os.remove(cov_p)

        # ۴. کپشن ۶ بخشی + سپر ضدشدوبن
        await send_caption_with_shield(session, chat_id, cap, back_kb=kb_cat_quick())
        add_to_daily_items(hl, still_img, tag=badge)

        for tmp_f in (story_p, reel_mp4):
            if tmp_f and os.path.exists(tmp_f):
                os.remove(tmp_f)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در ساخت بسته کامل خبر:\n{e}", kb_cat_quick())
    finally:
        shutil.rmtree(tdir, ignore_errors=True)


async def run_clean_logo_job(session: aiohttp.ClientSession, chat_id: str, media_path: str, is_video: bool, corner: str):
    cname = {"tr": "بالا راست", "tl": "بالا چپ", "br": "پایین راست", "bl": "پایین چپ"}.get(corner, corner)
    try:
        if is_video:
            out_p = await asyncio.to_thread(clean_corner_logo_video_sync, media_path, corner)
            await send_video_file(session, chat_id, out_p, caption=f"🧹 لوگوی گوشه «{cname}» از روی ویدئو پاک‌سازی شد.", reply_markup=kb_cat_quick())
        else:
            out_p = await asyncio.to_thread(clean_corner_logo_photo_sync, media_path, corner)
            await send_photo_file(session, chat_id, out_p, caption=f"🧹 لوگوی گوشه «{cname}» از روی عکس پاک‌سازی شد.", reply_markup=kb_cat_quick())
        if os.path.exists(out_p):
            os.remove(out_p)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در حذف واترمارک:\n{e}", kb_cat_quick())


# ==================== مدیریت کامل منوی ۴ دسته‌ای و پیام‌های کاربر ====================
async def handle_message(session: aiohttp.ClientSession, msg: dict):
    chat_id = str(msg["chat"]["id"])
    from_id = str(msg.get("from", {}).get("id", chat_id))

    if not ADMIN_ID:
        await send_message(session, chat_id, f"👋 آیدی عددی شما:\n{chat_id}\nاین عدد را در ADMIN_ID گیت‌هاب ثبت کنید.")
        return
    if not is_admin(from_id):
        return

    text = (msg.get("text") or msg.get("caption") or "").strip()
    is_pure_text = bool(msg.get("text")) and not (msg.get("photo") or msg.get("video") or msg.get("voice") or msg.get("audio"))

    # --- منوی اصلی خلوت ۲×۲ و بازگشت ---
    if is_pure_text and text in ("/start", "/menu", BTN_BACK, BTN_CANCEL):
        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, build_status_text(), kb_main_menu())
        return

    # --- ورود به ۴ دسته‌بندی اصلی ---
    if is_pure_text and text == BTN_CAT_REELS:
        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, "🎬 استودیو ریلز و ویدئو\nابزار موردنظر را از منوی پایین انتخاب کنید:", kb_cat_reels())
        return

    if is_pure_text and text == BTN_CAT_STORY:
        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, "🖼️ استودیو استوری، پست و کپشن\nابزار موردنظر را انتخاب کنید:", kb_cat_story())
        return

    if is_pure_text and text == BTN_CAT_QUICK:
        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, "⚡ تولید سریع و ابزارهای کمکی\nگزینه موردنظر را انتخاب کنید:", kb_cat_quick())
        return

    if is_pure_text and text == BTN_CAT_SETTINGS:
        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, "⚙️ تنظیمات استودیو، قاب‌ها، تم و بانک تلفظ گوینده:", kb_cat_settings())
        return

    # --- بازنویسی ایمن آخرین کپشن ---
    if is_pure_text and text == BTN_SAFE_REWRITE:
        orig = LAST_CAPTION.get(chat_id)
        if not orig:
            await send_message(session, chat_id, "⚠️ کپشنی در حافظه نیست.", kb_main_menu())
            return
        await send_message(session, chat_id, "⏳ در حال بازنویسی ایمن و ضدشدوبن...")
        safe = await rewrite_shadowban_safe(session, orig)
        LAST_CAPTION[chat_id] = safe
        await send_message(session, chat_id, "✅ نسخه ایمن و ضدشدوبن (آماده کپی):")
        await send_message(session, chat_id, safe, kb_main_menu())
        return

    # --- زیرمنوی ۴: تنظیمات و وضعیت ---
    if is_pure_text and text == BTN_STATUS:
        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, build_status_text(), kb_cat_settings())
        return

    if is_pure_text and text == BTN_THEME:
        USER_STATE[chat_id] = {"mode": "theme_select"}
        await send_message(session, chat_id, f"🎨 تم فعال فعلی: {THEMES[CONFIG['theme']]['name']}\nتم جدید را انتخاب کنید:", kb_theme_menu())
        return

    if is_pure_text and text == BTN_STUDIO_OPTS:
        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, "🎛️ تنظیمات تدوین ویدئو، قلاب کاغذ سوخته، کاور گرید ۴:۵ و صدای گوینده:", kb_studio_opts())
        return

    if is_pure_text and text == BTN_PRONOUNCE:
        USER_STATE[chat_id] = {"mode": "pronounce_edit"}
        custom = CONFIG.get("custom_pronunciations") or {}
        if custom:
            cur_list = "\n".join(f"• {k} ← {v}" for k, v in list(custom.items())[:25])
        else:
            cur_list = "(هنوز واژه سفارشی ثبت نشده؛ بانک پیش‌فرض محله‌های شیراز و شهرهای فارس فعال است ✅)"
        await send_message(
            session,
            chat_id,
            "🗣️ بانک تلفظ اختصاصی گوینده فارسی\n\n"
            f"واژه‌های سفارشی ثبت‌شده:\n{cur_list}\n\n"
            "• برای افزودن یا اصلاح تلفظ، این‌گونه بفرستید:\n"
            "کلمه = تَلَفُّظِ دَقیق\n"
            "• برای حذف یک واژه بنویسید:\n"
            "حذف کلمه",
            kb_cancel(),
        )
        return

    # --- اعمال تغییر تم گرافیکی ---
    if is_pure_text:
        for tkey, tval in THEMES.items():
            if text == tval["btn"]:
                CONFIG["theme"] = tkey
                await save_config_to_pin(session)
                USER_STATE.pop(chat_id, None)
                await send_message(session, chat_id, f"✅ تم گرافیکی به «{tval['name']}» تغییر کرد.", kb_cat_settings())
                return

    # --- تاگل‌های تنظیمات تدوین ---
    if is_pure_text and text.startswith((
        "🔥 قلاب کاغذ سوخته:", "🖼️ قاب ریلز:", "🧩 کاور گرید ۴:۵:", "📰 زیرنویس متحرک:",
        "🧬 اصالت‌سازی:", "👤 ردیابی چهره:", "🏷️ اند-اسکرین فالو:", "🎙️ صدای گوینده:"
    )):
        if text.startswith("🔥 قلاب کاغذ سوخته:"):
            CONFIG["use_burnt_hook"] = not CONFIG["use_burnt_hook"]
        elif text.startswith("🖼️ قاب ریلز:"):
            CONFIG["use_repo_frame"] = not CONFIG["use_repo_frame"]
        elif text.startswith("🧩 کاور گرید ۴:۵:"):
            CONFIG["make_grid_cover"] = not CONFIG["make_grid_cover"]
        elif text.startswith("📰 زیرنویس متحرک:"):
            CONFIG["video_ticker"] = not CONFIG["video_ticker"]
        elif text.startswith("🧬 اصالت‌سازی:"):
            CONFIG["video_antidup"] = not CONFIG["video_antidup"]
        elif text.startswith("👤 ردیابی چهره:"):
            CONFIG["video_facetrack"] = not CONFIG["video_facetrack"]
        elif text.startswith("🏷️ اند-اسکرین فالو:"):
            CONFIG["video_brand"] = not CONFIG["video_brand"]
        elif text.startswith("🎙️ صدای گوینده:"):
            CONFIG["tts_profile"] = "studio_anchor_f" if CONFIG.get("tts_profile") != "studio_anchor_f" else "studio_baritone"
        await save_config_to_pin(session)
        await send_message(session, chat_id, "✅ تنظیم ذخیره شد.", kb_studio_opts())
        return

    # --- زیرمنوی ۱: استودیو ریلز و ویدئو ---
    if is_pure_text and text == BTN_INCIDENT:
        USER_STATE[chat_id] = {"mode": "incident", "step": "wait_input"}
        await send_message(session, chat_id, "🚨 ریلز فوری و حادثه‌ای\nعکس حادثه را همراه با متن خبر بفرستید:", kb_cancel())
        return

    if is_pure_text and text == BTN_MAP:
        USER_STATE[chat_id] = {"mode": "map_reel", "step": "wait_location", "data": {}}
        await send_message(session, chat_id, "🗺️ ریلز زوم دومرحله‌ای روی نقشه\nمرحله ۱ از ۲: نام محله در شیراز یا شهر استان فارس را بنویسید:", kb_cancel())
        return

    if is_pure_text and text == BTN_DAILY60:
        USER_STATE[chat_id] = {"mode": "daily_collect"}
        cnt = to_persian_digits(str(len(DAILY_ITEMS)))
        await send_message(
            session,
            chat_id,
            f"🎬 استودیو ریلز جمع‌بندی ۶ سبکی (شامل سبک ۶ هولوگرام + گوینده فارسی)\n"
            f"📦 تعداد خبرهای فعلی در صف: {cnt} خبر\n\n"
            "خبرها را (عکس+متن یا فقط متن) پشت‌سرهم بفرستید و سپس یکی از ۶ سبک پایین را انتخاب کنید:",
            kb_daily_collect(),
        )
        return

    if is_pure_text and text == BTN_CLEAR_DAILY:
        for it in DAILY_ITEMS:
            if it.get("photo") and os.path.exists(it["photo"]):
                try:
                    os.remove(it["photo"])
                except Exception:
                    pass
        DAILY_ITEMS.clear()
        USER_STATE[chat_id] = {"mode": "daily_collect"}
        await send_message(session, chat_id, "🧹 صف جمع‌بندی پاک شد (۰ خبر). خبر اول را بفرستید:", kb_daily_collect())
        return

    if is_pure_text and text in DAILY_STYLE_MAP:
        if not DAILY_ITEMS:
            await send_message(session, chat_id, "⚠️ صف خالی است! ابتدا حداقل یک خبر بفرستید.", kb_daily_collect())
            return
        style_key, style_title = DAILY_STYLE_MAP[text]
        await send_message(
            session,
            chat_id,
            f"🎬 در حال رندر ریلز جمع‌بندی با سبک «{style_title}» از {to_persian_digits(str(len(DAILY_ITEMS[-8:])))} خبر...",
            kb_daily_collect(),
        )
        spawn_bg_task(run_daily60_job(session, chat_id, style_key, style_title))
        return

    if is_pure_text and text == BTN_VIDEO:
        USER_STATE[chat_id] = {"mode": "video_studio", "step": "wait_video"}
        h_note = "روشن ✅ (قبل از ساخت از شما تایید می‌گیرد)" if CONFIG["use_burnt_hook"] else "خاموش ❌"
        await send_message(
            session,
            chat_id,
            f"🎞️ استودیو تدوین هوشمند ویدئو\n• قلاب کاغذ سوخته ۳ ثانیه‌ای: {h_note}\n\n"
            "ویدئوی خود را (زیر ۲۰ مگابایت، ترجیحاً با متن خبر در کپشن) بفرستید:",
            kb_cancel(),
        )
        return

    if is_pure_text and text == BTN_HOOK_ONLY:
        USER_STATE[chat_id] = {"mode": "hook_only", "step": "wait_video"}
        await send_message(
            session,
            chat_id,
            "🔥 قلاب‌گذار سریع «کاغذ سوخته دوطبقه» (۳ ثانیه اول ویدئو)\n\n"
            "فیلم خود را (زیر ۲۰ مگابایت) همراه با توضیح کوتاه خبر در کپشن بفرستید.\n"
            "ابتدا دو سطر قلاب را برایتان نمایش می‌دهم تا تایید یا ویرایش کنید:",
            kb_cancel(),
        )
        return

    if is_pure_text and text == BTN_AUDIO:
        USER_STATE[chat_id] = {"mode": "audiogram", "step": "wait_audio", "data": {}}
        await send_message(session, chat_id, "🎙️ ریلز موج صوتی\nمرحله ۱ از ۲: ویس یا فایل صوتی را بفرستید:", kb_cancel())
        return

    # --- زیرمنوی ۲: استودیو استوری و کپشن ---
    if is_pure_text and text in (BTN_CARD_POST, BTN_CARD_STORY):
        fmt = "post" if text == BTN_CARD_POST else "story"
        fmt_fa = "پست (۴:۵)" if fmt == "post" else "استوری رسمی پیج (۹:۱۶)"
        USER_STATE[chat_id] = {"mode": "card", "step": "wait_input", "fmt": fmt}
        await send_message(session, chat_id, f"🖼️ ساخت کارت {fmt_fa}\nعکس خبر را همراه با متن خبر بفرستید (یا فقط متن):", kb_cancel())
        return

    if is_pure_text and text == BTN_CAPTION:
        USER_STATE[chat_id] = {"mode": "caption_active", "step": "wait_input"}
        await send_message(session, chat_id, f"✍️ کپشن‌نویس ۶ بخشی {BRAND_HANDLE}\nفیلم، عکس، ویس یا متن خبر را بفرستید:", kb_cancel())
        return

    if is_pure_text and text == BTN_SHADOWBAN:
        USER_STATE[chat_id] = {"mode": "shadowban_check", "step": "wait_text"}
        await send_message(session, chat_id, "🛡️ سپر ضدشدوبن\nمتن کپشن یا تیتر را بفرستید تا بررسی شود:", kb_cancel())
        return

    if is_pure_text and text == BTN_OCCASION:
        await send_message(session, chat_id, "📅 در حال طراحی کارت مناسبت امروز...")
        card_p, cap = await build_daily_occasion_card(session)
        await send_photo_file(session, chat_id, card_p, caption=cap, reply_markup=kb_cat_story())
        return

    # --- زیرمنوی ۳: تولید سریع و ابزارها ---
    if is_pure_text and text == BTN_ONE_TAP:
        USER_STATE[chat_id] = {"mode": "one_tap_pack", "step": "wait_input"}
        await send_message(
            session,
            chat_id,
            "📦 بسته کامل انتشار (One-Tap Pack)\n"
            "با ارسال یک خبر، ربات به‌صورت یک‌جا تحویل می‌دهد:\n"
            "۱) استوری رسمی پیج  ۲) ریلز با قلاب کاغذ سوخته ۳ ثانیه‌ای  ۳) کاور گرید ۴:۵  ۴) کپشن ۶ بخشی\n\n"
            "عکس یا فیلم خبر را همراه با متن خبر بفرستید:",
            kb_cancel(),
        )
        return

    if is_pure_text and text == BTN_CLEAN_LOGO:
        USER_STATE[chat_id] = {"mode": "clean_logo", "step": "wait_corner"}
        await send_message(session, chat_id, "🧹 حذف واترمارک و لوگو\nمرحله ۱ از ۲: گوشه محل قرارگیری لوگو را انتخاب کنید:", kb_logo_corners())
        return

    if is_pure_text and text == BTN_WEATHER:
        await send_message(session, chat_id, "🌤️ در حال دریافت دمای لحظه‌ای شیراز و شهرهای فارس...")
        w_card, w_cap = await build_shiraz_weather_story(session)
        await send_photo_file(session, chat_id, w_card, caption=w_cap, reply_markup=kb_cat_quick())
        if os.path.exists(w_card):
            os.remove(w_card)
        return

    # ==================== پردازش وضعیت‌های فعال کاربر ====================
    state = USER_STATE.get(chat_id)
    if not state:
        await send_message(session, chat_id, build_status_text(), kb_main_menu())
        return

    mode = state.get("mode")

    # --- مدیریت پیش‌نمایش و تایید/ویرایش دستی قلاب کاغذ سوخته (مشترک برای ۳ ابزار) ---
    if state.get("step") == "hook_confirm":
        if is_pure_text and text == BTN_HOOK_CONFIRM:
            l1, l2 = state["hook_l1"], state["hook_l2"]
            USER_STATE.pop(chat_id, None)
            if mode == "hook_only":
                await send_message(session, chat_id, "🔥 در حال رندر قلاب دوطبقه کاغذ سوخته روی ۳ ثانیه اول ویدئو...", kb_cat_reels())
                spawn_bg_task(run_hook_only_job(session, chat_id, state["vid_path"], l1, l2, state.get("caption", "")))
            elif mode == "video_studio":
                await send_message(session, chat_id, "🎞️ در حال تدوین هوشمند ویدئو + اعمال قلاب کاغذ سوخته (۳۰ تا ۶۰ ثانیه)...", kb_cat_reels())
                spawn_bg_task(run_video_studio_job(session, chat_id, state["vid_path"], state.get("caption", ""), (l1, l2), state.get("cached_cap", "")))
            elif mode == "one_tap_pack":
                await send_message(session, chat_id, "📦 در حال تولید یک‌جای استوری رسمی، ریلز، کاور گرید و کپشن...", kb_cat_quick())
                spawn_bg_task(run_one_tap_pack_job(session, chat_id, state.get("photo_path", ""), state.get("vid_path", ""), state.get("caption", ""), (l1, l2), state.get("cached_cap", "")))
            return

        if is_pure_text and text == BTN_HOOK_REGEN:
            await send_message(session, chat_id, "🔄 در حال ساخت پیشنهاد جدید برای قلاب کاغذ سوخته...")
            src_txt = f"{state.get('caption', '')}\n(متن متفاوت و جذاب‌تر از «{state['hook_l1']} / {state['hook_l2']}» بساز)"
            l1, l2 = await generate_burnt_hook_text(session, src_txt, state.get("media_ai"), state.get("mime_ai"))
            state["hook_l1"], state["hook_l2"] = l1, l2
            await send_hook_preview(session, chat_id, l1, l2, state.get("target_title", "ویدئو"))
            return

        if is_pure_text and text == BTN_HOOK_EDIT:
            state["step"] = "hook_manual_edit"
            await send_message(
                session,
                chat_id,
                "✏️ متن دلخواه دو سطر قلاب را در دو خط جداگانه (یا با علامت | بین دو سطر) بفرستید.\n"
                "نمونه:\nآتش‌سوزی گسترده معالی‌آباد\nجزئیات مهار حریق!",
                kb_cancel(),
            )
            return

    if state.get("step") == "hook_manual_edit":
        if not text:
            await send_message(session, chat_id, "❌ لطفاً دو سطر قلاب را به صورت متنی بفرستید:", kb_cancel())
            return
        if "|" in text:
            parts = [p.strip() for p in text.split("|", 1)]
        else:
            parts = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(parts) >= 2:
            l1 = strip_emojis_for_font(parts[0])[:28]
            l2 = strip_emojis_for_font(parts[1])[:28]
        else:
            l1, l2 = validate_and_balance_burnt_hook("", "", fallback_text=text)
        state["hook_l1"], state["hook_l2"] = l1, l2
        state["step"] = "hook_confirm"
        await send_hook_preview(session, chat_id, l1, l2, state.get("target_title", "ویدئو"))
        return

    # --- ویرایش بانک تلفظ گوینده ---
    if mode == "pronounce_edit":
        if not text:
            await send_message(session, chat_id, "❌ فرمت صحیح: `کلمه = تلفظِ دقیق` یا `حذف کلمه`", kb_cancel())
            return
        custom = dict(CONFIG.get("custom_pronunciations") or {})
        if text.startswith("حذف "):
            key = text[4:].strip()
            if key in custom:
                del custom[key]
                CONFIG["custom_pronunciations"] = custom
                await save_config_to_pin(session)
                await send_message(session, chat_id, f"🗑️ واژه «{key}» از بانک تلفظ حذف شد.", kb_cat_settings())
            else:
                await send_message(session, chat_id, f"⚠️ واژه «{key}» در لیست سفارشی نبود.", kb_cat_settings())
            USER_STATE.pop(chat_id, None)
            return
        if "=" in text:
            k, v = [p.strip() for p in text.split("=", 1)]
            if k and v:
                custom[k] = v
                CONFIG["custom_pronunciations"] = custom
                await save_config_to_pin(session)
                USER_STATE.pop(chat_id, None)
                await send_message(session, chat_id, f"✅ تلفظ ذخیره شد:\n«{k}» ← «{v}»", kb_cat_settings())
                return
        await send_message(session, chat_id, "❌ فرمت اشتباه است. دقیقاً به شکل `کلمه = تلفظِ دقیق` بفرستید:", kb_cancel())
        return

    # --- دریافت ویدئو برای ابزار مستقل قلاب‌گذار کاغذ سوخته ---
    if mode == "hook_only" and state["step"] == "wait_video":
        vid = msg.get("video")
        if not vid:
            await send_message(session, chat_id, "❌ لطفاً فایل ویدئو (زیر ۲۰ مگابایت) بفرستید:", kb_cancel())
            return
        if vid.get("file_size", 0) > 19.5 * 1024 * 1024:
            await send_message(session, chat_id, "⚠️ حجم ویدئو بالای ۲۰ مگابایت است. نسخه کم‌حجم‌تر بفرستید.", kb_cancel())
            return
        await send_message(session, chat_id, "⏳ در حال تحلیل ویدئو و طراحی قلاب دوطبقه کاغذ سوخته...")
        vid_path = await download_tg_file(session, vid["file_id"], ".mp4")
        l1, l2 = await generate_burnt_hook_text(session, text, media_path=vid_path, mime_type="video/mp4")
        state.update({
            "step": "hook_confirm", "vid_path": vid_path, "caption": text,
            "media_ai": vid_path, "mime_ai": "video/mp4",
            "hook_l1": l1, "hook_l2": l2, "target_title": "قلاب‌گذار سریع",
        })
        await send_hook_preview(session, chat_id, l1, l2, "قلاب‌گذار سریع")
        return

    # --- دریافت ویدئو برای استودیو تدوین ویدئو ---
    if mode == "video_studio" and state["step"] == "wait_video":
        vid = msg.get("video")
        if not vid:
            await send_message(session, chat_id, "❌ لطفاً فایل ویدئو (زیر ۲۰ مگابایت) بفرستید:", kb_cancel())
            return
        if vid.get("file_size", 0) > 19.5 * 1024 * 1024:
            await send_message(session, chat_id, "⚠️ حجم ویدئو بالای ۲۰ مگابایت است. نسخه کم‌حجم‌تر بفرستید.", kb_cancel())
            return
        vid_path = await download_tg_file(session, vid["file_id"], ".mp4")
        if CONFIG.get("use_burnt_hook", True):
            await send_message(session, chat_id, "⏳ در حال تحلیل فیلم و طراحی قلاب دوطبقه کاغذ سوخته برای تایید شما...")
            cap = await generate_editorial_caption(session, news_text=text, media_path=vid_path, mime_type="video/mp4")
            l1, l2 = await generate_burnt_hook_text(session, text if len(text) >= 12 else cap, media_path=vid_path, mime_type="video/mp4")
            state.update({
                "step": "hook_confirm", "vid_path": vid_path, "caption": text, "cached_cap": cap,
                "media_ai": vid_path, "mime_ai": "video/mp4",
                "hook_l1": l1, "hook_l2": l2, "target_title": "استودیو تدوین ویدئو",
            })
            await send_hook_preview(session, chat_id, l1, l2, "استودیو تدوین ویدئو")
            return
        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, "🎞️ در حال تدوین هوشمند ویدئو (۳۰ تا ۶۰ ثانیه)...", kb_cat_reels())
        spawn_bg_task(run_video_studio_job(session, chat_id, vid_path, text, None))
        return

    # --- دریافت ورودی برای بسته کامل انتشار (One-Tap Pack) ---
    if mode == "one_tap_pack" and state["step"] == "wait_input":
        photo_path, vid_path = "", ""
        if msg.get("video"):
            vid = msg["video"]
            if vid.get("file_size", 0) > 19.5 * 1024 * 1024:
                await send_message(session, chat_id, "⚠️ حجم فیلم بالای ۲۰ مگابایت است.", kb_cancel())
                return
            vid_path = await download_tg_file(session, vid["file_id"], ".mp4")
        elif msg.get("photo"):
            photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg")
        if not photo_path and not vid_path and not text:
            await send_message(session, chat_id, "❌ عکس، فیلم یا متن خبر را بفرستید:", kb_cancel())
            return

        if CONFIG.get("use_burnt_hook", True):
            await send_message(session, chat_id, "⏳ در حال تحلیل خبر و طراحی قلاب کاغذ سوخته برای بسته کامل...")
            media_ai = vid_path or (photo_path or None)
            mime_ai = "video/mp4" if vid_path else ("image/jpeg" if photo_path else None)
            cap = await generate_editorial_caption(session, news_text=text, media_path=media_ai, mime_type=mime_ai)
            l1, l2 = await generate_burnt_hook_text(session, text if len(text) >= 12 else cap, media_path=media_ai, mime_type=mime_ai)
            state.update({
                "step": "hook_confirm", "photo_path": photo_path, "vid_path": vid_path,
                "caption": text, "cached_cap": cap, "media_ai": media_ai, "mime_ai": mime_ai,
                "hook_l1": l1, "hook_l2": l2, "target_title": "بسته کامل خبر",
            })
            await send_hook_preview(session, chat_id, l1, l2, "بسته کامل خبر")
            return

        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, "📦 در حال ساخت بسته کامل خبر...", kb_cat_quick())
        spawn_bg_task(run_one_tap_pack_job(session, chat_id, photo_path, vid_path, text, None))
        return

    # --- کارت پست و استوری رسمی پیج ---
    if mode == "card":
        fmt = state["fmt"]
        USER_STATE.pop(chat_id, None)
        photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg") if msg.get("photo") else ""
        if not photo_path and not text:
            await send_message(session, chat_id, "❌ لطفاً عکس یا متن خبر را بفرستید.", kb_cat_story())
            return
        await send_message(session, chat_id, "⏳ در حال طراحی کارت و نگارش کپشن ۶ بخشی...")
        cap = await generate_editorial_caption(session, news_text=text, media_path=photo_path or None, mime_type="image/jpeg" if photo_path else None)
        source_for_parts = text if len(text) >= 15 else cap
        badge, hl, sub = await extract_news_parts(session, source_for_parts)
        src_name = extract_source_name(text) or extract_source_name(cap)
        card_p = await asyncio.to_thread(render_news_card_sync, photo_path, badge, hl, sub, fmt, CONFIG["theme"], src_name)
        await send_photo_file(session, chat_id, card_p, caption="🖼️ کارت آماده انتشار")
        await send_caption_with_shield(session, chat_id, cap, back_kb=kb_cat_story())
        add_to_daily_items(hl, photo_path, tag=badge)
        return

    # --- دریافت دسته‌ای خبرهای صف جمع‌بندی ۶ سبکی ---
    if mode == "daily_collect":
        photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg") if msg.get("photo") else ""
        clean_lines = [strip_emojis_for_font(ln) for ln in text.splitlines() if strip_emojis_for_font(ln)]
        if not photo_path and not clean_lines:
            await send_message(session, chat_id, "❌ عکس یا متن خبر را بفرستید.", kb_daily_collect())
            return
        raw_hl = clean_lines[0][:95] if clean_lines else "خبر تصویری جدید"
        tag = "خبر فوری" if ("فوری" in text or "حادثه" in text) else ("ورزشی" if "ورزش" in text else "خبر شیراز")
        add_to_daily_items(raw_hl, photo_path, tag=tag)
        cnt = to_persian_digits(str(len(DAILY_ITEMS)))
        await send_message(
            session,
            chat_id,
            f"✅ خبر شماره {cnt} در صف جمع‌بندی ثبت شد:\n«{raw_hl}»\n\n"
            "خبر بعدی را بفرستید یا یکی از ۶ سبک زیر را برای ساخت ریلز انتخاب کنید.",
            kb_daily_collect(),
        )
        return

    # --- ریلز فوری و حادثه‌ای ---
    if mode == "incident":
        USER_STATE.pop(chat_id, None)
        photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg") if msg.get("photo") else ""
        if not photo_path and not text:
            await send_message(session, chat_id, "❌ عکس و متن خبر حادثه‌ای را بفرستید.", kb_cat_reels())
            return
        await send_message(session, chat_id, "🚨 در حال تدوین ریلز اضطراری حادثه‌ای...", kb_cat_reels())
        spawn_bg_task(run_incident_job(session, chat_id, photo_path, text))
        return

    # --- کپشن‌نویس فعال ---
    if mode == "caption_active":
        USER_STATE.pop(chat_id, None)
        media_path, mime = None, None
        if msg.get("video"):
            vid = msg["video"]
            if vid.get("file_size", 0) > 19.5 * 1024 * 1024:
                await send_message(session, chat_id, "⚠️ حجم فیلم بیشتر از ۲۰ مگابایت است.", kb_cat_story())
                return
            await send_message(session, chat_id, "🎥 در حال تحلیل تصویر و صدای فیلم و نگارش کپشن ۶ بخشی...")
            media_path = await download_tg_file(session, vid["file_id"], ".mp4")
            mime = vid.get("mime_type") or "video/mp4"
        elif msg.get("photo"):
            await send_message(session, chat_id, "🖼️ در حال تحلیل عکس و نگارش کپشن ۶ بخشی...")
            media_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg")
            mime = "image/jpeg"
        elif msg.get("voice") or msg.get("audio"):
            aud = msg.get("voice") or msg.get("audio")
            if aud.get("file_size", 0) > 19.5 * 1024 * 1024:
                await send_message(session, chat_id, "⚠️ حجم فایل صوتی بیشتر از ۲۰ مگابایت است.", kb_cat_story())
                return
            await send_message(session, chat_id, "🎙️ در حال شنیدن فایل صوتی و نگارش کپشن ۶ بخشی...")
            media_path = await download_tg_file(session, aud["file_id"], ".ogg")
            mime = aud.get("mime_type") or "audio/ogg"
        elif text:
            await send_message(session, chat_id, f"✍️ در حال نگارش کپشن ۶ بخشی {BRAND_HANDLE}...")
        else:
            await send_message(session, chat_id, "❌ لطفاً متن، عکس، ویس یا فیلم بفرستید.", kb_cat_story())
            return

        cap = await generate_editorial_caption(session, news_text=text, media_path=media_path, mime_type=mime)
        await send_caption_with_shield(session, chat_id, cap, back_kb=kb_cat_story())
        add_to_daily_items(cap.splitlines()[0] if cap else text[:70], media_path if mime == "image/jpeg" else None, tag="خبر")
        return

    # --- ریلز زوم نقشه ---
    if mode == "map_reel":
        if state["step"] == "wait_location":
            if not text:
                await send_message(session, chat_id, "❌ نام محله یا شهر را متنی بفرستید:", kb_cancel())
                return
            state["data"]["location"] = text
            state["step"] = "wait_photo"
            await send_message(session, chat_id, f"📍 موقعیت ثبت شد: {text}\nمرحله ۲ از ۲: عکس و متن خبر را بفرستید:", kb_cancel())
            return
        if state["step"] == "wait_photo":
            loc = state["data"]["location"]
            USER_STATE.pop(chat_id, None)
            photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg") if msg.get("photo") else ""
            await send_message(session, chat_id, f"🗺️ در حال دریافت نقشه واقعی «{loc}» و ساخت ریلز زوم دومرحله‌ای...", kb_cat_reels())
            spawn_bg_task(run_map_job(session, chat_id, loc, photo_path, text))
            return

    # --- ریلز موج صوتی ---
    if mode == "audiogram":
        if state["step"] == "wait_audio":
            aud = msg.get("voice") or msg.get("audio")
            if not aud or aud.get("file_size", 0) > 19.5 * 1024 * 1024:
                await send_message(session, chat_id, "❌ لطفاً ویس یا فایل صوتی (زیر ۲۰ مگابایت) بفرستید:", kb_cancel())
                return
            state["data"]["audio"] = await download_tg_file(session, aud["file_id"], ".ogg")
            state["step"] = "wait_speaker"
            await send_message(session, chat_id, "مرحله ۲ از ۲: عکس گوینده را با تیتر در کپشن بفرستید (یا «⏭️ بدون عکس گوینده»):", kb_cancel([{"text": BTN_SKIP_PHOTO}]))
            return
        if state["step"] == "wait_speaker":
            if is_pure_text and text == BTN_SKIP_PHOTO:
                state["step"] = "wait_title"
                await send_message(session, chat_id, "✏️ تیتر کوتاه خبر را بنویسید:", kb_cancel())
                return
            sp_photo = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg") if msg.get("photo") else ""
            if not text:
                state["data"]["photo"] = sp_photo
                state["step"] = "wait_title"
                await send_message(session, chat_id, "✏️ حالا تیتر کوتاه خبر را بنویسید:", kb_cancel())
                return
            aud_path = state["data"]["audio"]
            USER_STATE.pop(chat_id, None)
            await send_message(session, chat_id, "🎙️ در حال ساخت ریلز موج صوتی...", kb_cat_reels())
            spawn_bg_task(run_audiogram_job(session, chat_id, aud_path, sp_photo, text))
            return
        if state["step"] == "wait_title":
            aud_path, sp_photo = state["data"]["audio"], state["data"].get("photo", "")
            USER_STATE.pop(chat_id, None)
            await send_message(session, chat_id, "🎙️ در حال ساخت ریلز موج صوتی...", kb_cat_reels())
            spawn_bg_task(run_audiogram_job(session, chat_id, aud_path, sp_photo, text or BRAND_TITLE_FA))
            return

    # --- حذف واترمارک و لوگو ---
    if mode == "clean_logo":
        corner_map = {BTN_CORNER_TR: "tr", BTN_CORNER_TL: "tl", BTN_CORNER_BR: "br", BTN_CORNER_BL: "bl"}
        if state["step"] == "wait_corner":
            if is_pure_text and text in corner_map:
                state["corner"] = corner_map[text]
                state["step"] = "wait_media"
                await send_message(session, chat_id, f"✅ گوشه ثبت شد: {text}\nمرحله ۲ از ۲: عکس یا فیلم (زیر ۲۰ مگابایت) را بفرستید:", kb_cancel())
                return
            await send_message(session, chat_id, "❌ یکی از ۴ گوشه را انتخاب کنید:", kb_logo_corners())
            return
        if state["step"] == "wait_media":
            corner = state["corner"]
            if msg.get("video"):
                vid = msg["video"]
                if vid.get("file_size", 0) > 19.5 * 1024 * 1024:
                    await send_message(session, chat_id, "⚠️ حجم فیلم باید کمتر از ۲۰ مگابایت باشد.", kb_cancel())
                    return
                USER_STATE.pop(chat_id, None)
                await send_message(session, chat_id, "🧹 در حال حذف واترمارک از روی ویدئو...", kb_cat_quick())
                spawn_bg_task(run_clean_logo_job(session, chat_id, await download_tg_file(session, vid["file_id"], ".mp4"), True, corner))
                return
            if msg.get("photo"):
                USER_STATE.pop(chat_id, None)
                await send_message(session, chat_id, "🧹 در حال حذف واترمارک از روی عکس...", kb_cat_quick())
                spawn_bg_task(run_clean_logo_job(session, chat_id, await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg"), False, corner))
                return
            await send_message(session, chat_id, "❌ لطفاً عکس یا ویدئو بفرستید:", kb_cancel())
            return

    # --- بررسی دستی سپر ضدشدوبن ---
    if mode == "shadowban_check":
        USER_STATE.pop(chat_id, None)
        if not text:
            await send_message(session, chat_id, "❌ متن را بفرستید.", kb_cat_story())
            return
        LAST_CAPTION[chat_id] = text
        hits = check_shadowban_words(text)
        if not hits:
            await send_message(session, chat_id, "✅ عالی! هیچ کلمه پرریسک و محدودیت‌زایی در متن شما پیدا نشد.", kb_cat_story())
        else:
            lines = ["⚠️ کلمات حساس شناسایی‌شده در متن:"] + [f"• «{w}» ← معادل ایمن: {alt}" for w, alt in hits]
            lines.append("\nبرای دریافت نسخه اصلاح‌شده، دکمه «✨ بازنویسی ایمن آخرین کپشن» را بزنید.")
            await send_message(session, chat_id, "\n".join(lines), kb_shadowban_actions())
        return


# ==================== حلقه اصلی ربات ====================
async def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing!")
        return

    boot_time = time.time()
    async with aiohttp.ClientSession() as session:
        await load_config_from_pin(session)
        if not should_keep_running(boot_time):
            print(f"Outside scheduled hours ({get_tehran_now().strftime('%H:%M')} Tehran). Exiting.")
            return

        await tg_api(session, "deleteWebhook", {"drop_pending_updates": False})
        await tg_api(session, "setMyCommands", {
            "commands": [
                {"command": "start", "description": "باز کردن منوی ۴ دسته‌ای استودیو"},
                {"command": "menu", "description": "نمایش منوی اصلی"},
            ]
        })
        print(f"Studio Bot started at {get_tehran_now().strftime('%H:%M')} Tehran | RAQM={HAS_RAQM} | TTS={HAS_EDGE_TTS}")

        offset = 0
        while should_keep_running(boot_time):
            try:
                now = get_tehran_now()
                today_key = now.strftime("%Y-%m-%d")
                if CONFIG["auto_daily_card"] and ADMIN_ID and 7 <= now.hour <= 9 and CONFIG["last_occasion_date"] != today_key:
                    CONFIG["last_occasion_date"] = today_key
                    await save_config_to_pin(session)
                    c_path, c_cap = await build_daily_occasion_card(session)
                    await send_photo_file(session, ADMIN_ID, c_path, caption=c_cap, reply_markup=kb_main_menu())

                url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
                params = {"offset": offset, "timeout": 25, "allowed_updates": '["message"]'}
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=35)) as resp:
                    if resp.status == 409:
                        await asyncio.sleep(3)
                        continue
                    if resp.status == 200:
                        data = await resp.json()
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            if "message" in update:
                                await handle_message(session, update["message"])
            except Exception as e:
                print(f"Loop error: {e}")
                await asyncio.sleep(4)

        if BG_TASKS:
            await asyncio.gather(*BG_TASKS, return_exceptions=True)

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    print(f"Studio Bot shift ended cleanly at {get_tehran_now().strftime('%H:%M')} Tehran.")


if __name__ == "__main__":
    asyncio.run(main())
