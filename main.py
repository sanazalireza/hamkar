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
import tempfile
import time
import wave
from datetime import datetime, timedelta, timezone

# نصب خودکار موتور فارسی‌نویس (libraqm0) قبل از بارگذاری Pillow
if not ctypes.util.find_library("raqm") and shutil.which("apt-get"):
    _r = subprocess.run(
        ["sudo", "apt-get", "install", "-y", "-qq", "libraqm0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if _r.returncode != 0:
        subprocess.run(["sudo", "apt-get", "update", "-qq"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "apt-get", "install", "-y", "-qq", "libraqm0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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

BRAND_HANDLE = "@shirazlastnews"
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

# ==================== تم‌های گرافیکی ====================
THEMES = {
    "navy": {
        "name": "تم رسمی سرمه‌ای 🔵",
        "btn": "🔵 تم رسمی سرمه‌ای",
        "bg": (11, 27, 52),
        "accent": (234, 179, 8),
        "badge_bg": (220, 38, 38),
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

# ==================== برچسب دکمه‌های منوی ثابت پایین صفحه ====================
BTN_CARD_POST = "🖼️ کارت پست (۴:۵)"
BTN_CARD_STORY = "📱 کارت استوری (۹:۱۶)"
BTN_INCIDENT = "🚨 ریلز فوری و حادثه‌ای"
BTN_CAPTION = "✍️ کپشن‌نویس فعال"
BTN_MAP = "🗺️ ریلز زوم نقشه"
BTN_AUDIO = "🎙️ ریلز موج صوتی"
BTN_DAILY60 = "🎬 ریلز جمع‌بندی ۶۰ ثانیه‌ای"
BTN_VIDEO = "🎞️ استودیو تدوین ویدئو"
BTN_CLEAN_LOGO = "🧹 حذف واترمارک و لوگو"
BTN_SHADOWBAN = "🛡️ سپر ضدشدوبن"
BTN_THEME = "🎨 تغییر تم گرافیکی"
BTN_OCCASION = "📅 کارت مناسبت امروز"
BTN_STATUS = "📊 وضعیت استودیو"
BTN_BACK = "🔙 بازگشت به منوی اصلی"
BTN_CANCEL = "❌ انصراف و بازگشت"
BTN_SKIP_PHOTO = "⏭️ بدون عکس گوینده"
BTN_SAFE_REWRITE = "✨ بازنویسی ایمن آخرین کپشن"
BTN_BUILD_POPART = "🚀 ساخت ریلز جمع‌بندی (برودکست)"
BTN_CLEAR_DAILY = "🧹 پاک کردن صف جمع‌بندی"

# دکمه‌های انتخاب گوشه حذف واترمارک (مورد ۹)
BTN_CORNER_TR = "↗️ گوشه بالا راست"
BTN_CORNER_TL = "↖️ گوشه بالا چپ"
BTN_CORNER_BR = "↘️ گوشه پایین راست"
BTN_CORNER_BL = "↙️ گوشه پایین چپ"

CONFIG = {
    "theme": "navy",
    "use_repo_frame": True,    # قاب ۳ باکسه ریلز (reel_frame.png)
    "use_story_frame": True,   # قاب اختصاصی استوری (story_frame.png)
    "video_antidup": True,     # اصالت‌سازی و حذف متادیتا
    "video_facetrack": True,   # ردیابی چهره ۹:۱۶
    "video_brand": True,       # اند-اسکرین دعوت به فالو
    "video_ticker": True,      # مورد ۷: نوار زیرنویس متحرک شبکه خبر
    "video_hook_intro": True,  # مورد ۵: قلاب ۱.۵ ثانیه‌ای شوک در ابتدا
    "auto_shadowban": True,
    "auto_daily_card": True,
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
        tail = "\n".join(err_lines[-4:]) if err_lines else f"exit code {res.returncode}"
        raise RuntimeError(tail)


def find_repo_audio(mode: str = "incident") -> str:
    if mode == "incident":
        cands = ("incident.mp3", "sounds/incident.mp3", "incident_music.mp3", "sounds/incident_music.mp3")
    else:
        cands = ("news.mp3", "sounds/news.mp3", "news_music.mp3", "sounds/news_music.mp3")
    for p in cands:
        if os.path.exists(p) and os.path.getsize(p) > 4000:
            return p
    return ""


def generate_emergency_audio_wav(out_path: str, duration_sec: float, mode: str = "incident") -> str:
    """ساخت صدای پرقدرت و اضطراری (آژیر واقعی + ضربه شوک ۱.۵ ثانیه اول + تیک‌تاک خبری) با NumPy."""
    sr = 44100
    n = int(sr * duration_sec)
    t = np.linspace(0.0, duration_sec, n, endpoint=False, dtype=np.float64)

    if mode == "incident":
        # ۱. ضربه شوک و بوق هشدار فوری در ۱.۵ ثانیه اول (قلاب شوک - مورد ۵)
        boom_env = np.exp(-t * 4.5) * (t < 1.2)
        boom = 0.55 * np.sin(2 * np.pi * (95.0 - 45.0 * np.minimum(t, 1.0)) * t) * boom_env
        alert_beep = 0.28 * np.sin(2 * np.pi * 1040.0 * t) * (
            ((t >= 0.05) & (t < 0.22)) | ((t >= 0.30) & (t < 0.47)) | ((t >= 0.55) & (t < 0.72))
        )

        # ۲. آژیر اورژانسی رفت‌وبرگشتی واقعی (نوسان فرکانس بین ۵۲۰ تا ۹۲۰ هرتز)
        siren_phase = 2 * np.pi * (720.0 * t - (200.0 / (2 * np.pi * 1.15)) * np.cos(2 * np.pi * 1.15 * t))
        siren = 0.19 * (0.75 * np.sin(siren_phase) + 0.25 * np.sin(2.0 * siren_phase))
        siren *= np.clip((t - 0.5) / 0.6, 0.0, 1.0)

        # ۳. ضربان قلب تند خبری (Breaking News Pulse) + تیک‌تاک تایپ زنده
        pulse_cycle = np.mod(t, 0.50)
        kick = 0.32 * np.sin(2 * np.pi * 62.0 * t) * np.exp(-pulse_cycle * 14.0)
        tick_cycle = np.mod(t, 0.14)
        type_ticks = 0.11 * np.sin(2 * np.pi * 2400.0 * t) * np.exp(-tick_cycle * 65.0) * ((t >= 1.2) & (t < 5.5))

        signal = boom + alert_beep + siren + kick + type_ticks
    else:
        # ریتم رسمی و پرانرژی شبکه خبر برای ریلز نقشه و جمع‌بندی ۶۰ ثانیه‌ای
        bar = np.mod(t, 0.60)
        bass = 0.18 * np.sin(2 * np.pi * 92.0 * t) * np.exp(-bar * 6.0)
        chime_cycle = np.mod(t, 1.20)
        chime = 0.09 * np.sin(2 * np.pi * 440.0 * t) * np.exp(-chime_cycle * 10.0)
        pad = 0.06 * np.sin(2 * np.pi * 184.0 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.8 * t))
        signal = bass + chime + pad

    # فید نرم انتهایی و محدودسازی امن صدا
    fade_n = min(int(sr * 0.4), n // 4)
    if fade_n > 0:
        signal[-fade_n:] *= np.linspace(1.0, 0.0, fade_n)
    signal = np.tanh(signal) * 0.92
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
    for path in (
        "reel_frame.png",
        "assets/reel_frame.png",
        "reel_overlay.png",
        "assets/reel_overlay.png",
        "frame.png",
    ):
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return path
    return ""


def find_repo_story_frame() -> str:
    for path in (
        "story_frame.png",
        "assets/story_frame.png",
        "story_overlay.png",
        "۰۳_استوری_خبر_فوری_خام.png",
        "assets/۰۳_استوری_خبر_فوری_خام.png",
    ):
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return path
    return ""


def find_repo_logo() -> str:
    for path in (
        "logo.png",
        "assets/logo.png",
        "quran_gate.png",
        "assets/quran_gate.png",
        "brand_logo.png",
    ):
        if os.path.exists(path) and os.path.getsize(path) > 500:
            return path
    for fname in os.listdir("."):
        low = fname.lower()
        if low.endswith(".png") and ("logo" in low or "لوگو" in fname or "دروازه" in fname) and os.path.getsize(fname) > 500:
            return fname
    return ""


def extract_source_name(news_text: str) -> str:
    """استخراج خودکار نام منبع یا خبرگزاری از متن خبر برای نوار فوتر استوری."""
    if not news_text:
        return ""
    m = re.search(r"منبع\s*[:：]\s*([^\n|،]+)", news_text)
    if m:
        return strip_emojis_for_font(m.group(1))[:36]
    agencies = [
        ("ایرنا", "خبرگزاری ایرنا"),
        ("فارس", "خبرگزاری فارس"),
        ("تسنیم", "خبرگزاری تسنیم"),
        ("ایسنا", "خبرگزاری ایسنا"),
        ("مهر", "خبرگزاری مهر"),
        ("ایلنا", "خبرگزاری ایلنا"),
        ("باشگاه خبرنگاران", "باشگاه خبرنگاران جوان"),
        ("صداوسیما", "خبرگزاری صداوسیما"),
        ("میزان", "خبرگزاری میزان"),
        ("دانشجو", "خبرگزاری دانشجو"),
        ("روابط عمومی", "روابط عمومی"),
    ]
    for key, title in agencies:
        if key in news_text:
            return title
    return ""


def kb_daily_collect() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_BUILD_POPART}],
            [{"text": BTN_CLEAR_DAILY}, {"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def spawn_bg_task(coro):
    task = asyncio.create_task(coro)
    BG_TASKS.add(task)
    task.add_done_callback(BG_TASKS.discard)
    return task


def to_persian_digits(text: str) -> str:
    en = "0123456789"
    fa = "۰۱۲۳۴۵۶۷۸۹"
    for i in range(10):
        text = text.replace(en[i], fa[i])
    return text


def strip_emojis_for_font(text: str) -> str:
    """حذف کامل ایموجی‌ها و کاراکترهای غیرقابل چاپ در فونت فارسی برای جلوگیری از مربع خالی []."""
    if not text:
        return ""
    allowed = re.sub(
        r"[^\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF\u200c\x20-\x7E«»—–،؛؟\n]",
        " ",
        text,
    )
    allowed = re.sub(r"[ \t]+", " ", allowed)
    return allowed.strip()


def find_font_path(kind: str = "bold") -> str:
    if not HAS_RAQM and kind == "display":
        kind = "bold"
    candidates = {
        "display": [
            "fonts/Lalezar-Regular.ttf",
            "fonts/Vazirmatn-Bold.ttf",
        ],
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
        if is_rtl:
            return clean, {"direction": "rtl", "language": "fa"}
        return clean, {"direction": "ltr"}
    if is_rtl:
        return get_display(arabic_reshaper.reshape(clean)), {}
    return clean, {}


def wrap_all_words(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """شکستن تمام کلمات بدون حذف حتی یک کلمه از انتهای جمله."""
    clean = strip_emojis_for_font(text).replace("\n", " ")
    words = clean.split()
    if not words:
        return []
    lines = []
    cur = []
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
    draw: ImageDraw.ImageDraw,
    text: str,
    font_kind: str,
    max_width: int,
    max_height: int,
    max_size: int = 72,
    min_size: int = 24,
    max_lines: int = 3,
    line_spacing: float = 1.32,
) -> tuple:
    """تنظیم خودکار سایز فونت تا کل متن بدون بریده شدن، دقیقاً داخل کادر جا بگیرد."""
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
    lines = wrap_all_words(draw, clean, font, max_width)[:max_lines]
    return font, lines, int(min_size * line_spacing)


def draw_rtl_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    align: str = "center",
    shadow: bool = True,
    shadow_offset: int = 4,
    is_rtl: bool = True,
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
    draw: ImageDraw.ImageDraw,
    box: tuple,
    text: str,
    font_kind: str,
    fill: tuple,
    max_size: int = 64,
    min_size: int = 22,
    max_lines: int = 3,
    align: str = "center",
    pad_x: int = 28,
    pad_y: int = 12,
    shadow: bool = False,
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
        if align == "right":
            ax = x2 - pad_x
        elif align == "left":
            ax = x1 + pad_x
        else:
            ax = (x1 + x2) // 2
        draw_rtl_text(draw, (ax, cur_y), ln, font, fill, align=align, shadow=shadow, shadow_offset=3)
        cur_y += lh


def fit_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    nw, nh = int(src_w * scale), int(src_h * scale)
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - target_w) // 2
    top = (nh - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


# ==================== اسکنر خودکار باکس‌های قاب ریلز و قاب استوری (مورد ۱) ====================
def detect_reel_frame_boxes(frame_rgba: Image.Image) -> dict:
    """تشخیص خودکار باکس قرمز بالا، باکس مشکی تیتر میانی و باکس مشکی پایینی از روی reel_frame.png."""
    arr = np.array(frame_rgba.resize((1080, 1920), Image.Resampling.LANCZOS))
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

    # مقادیر کالیبره‌شده پیش‌فرض مطابق reel_frame.png ارسالی
    boxes = {
        "red_badge": (80, 140, 382, 234),
        "title_box": (24, 1008, 1026, 1180),
        "sub_box": (60, 1430, 1020, 1622),
    }

    # ۱. تشخیص باکس قرمز بالا
    red_mask = ((a > 120) & (r > 155) & (g < 85) & (b < 85)).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    red_top = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if y < 750 and w >= 110 and h >= 40:
            red_top.append((x, y, x + w, y + h))
    if red_top:
        red_top.sort(key=lambda bx: bx[1])
        boxes["red_badge"] = red_top[0]

    # ۲. تشخیص باکس‌های مشکی میانی و پایینی (خط قرمز کنار باکس خودکار حذف می‌شود)
    dark_mask = ((a > 120) & (r < 68) & (g < 68) & (b < 68)).astype(np.uint8) * 255
    cnts_d, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    dark_boxes = []
    for c in cnts_d:
        x, y, w, h = cv2.boundingRect(c)
        if w >= 450 and h >= 70 and y >= 450:
            dark_boxes.append((x, y, x + w, y + h))
    dark_boxes.sort(key=lambda bx: bx[1])
    if len(dark_boxes) >= 2:
        boxes["title_box"] = dark_boxes[0]
        boxes["sub_box"] = dark_boxes[1]
    elif len(dark_boxes) == 1:
        boxes["title_box"] = dark_boxes[0]

    return boxes


def render_reel_frame_overlay(frame_path: str, badge: str, headline: str, subtitle: str, work_dir: str) -> str:
    """چاپ تمیز هر ۳ متن (برچسب قرمز، تیتر اصلی، زیرتیتر) دقیقاً داخل ۳ باکس reel_frame.png."""
    frame = Image.open(frame_path).convert("RGBA").resize((1080, 1920), Image.Resampling.LANCZOS)
    boxes = detect_reel_frame_boxes(frame)
    draw = ImageDraw.Draw(frame)

    # باکس ۱ (کادر قرمز بالا): برچسب مثل «خبر فوری»
    draw_centered_block_in_box(
        draw,
        boxes["red_badge"],
        badge or "خبر فوری",
        font_kind="display",
        fill=(255, 255, 255, 255),
        max_size=44,
        min_size=24,
        max_lines=1,
        align="center",
        pad_x=16,
        pad_y=8,
    )

    # باکس ۲ (کادر مشکی میانی): تیتر اصلی خبر
    draw_centered_block_in_box(
        draw,
        boxes["title_box"],
        headline or BRAND_TITLE_FA,
        font_kind="display",
        fill=(255, 255, 255, 255),
        max_size=56,
        min_size=26,
        max_lines=2,
        align="right",
        pad_x=30,
        pad_y=12,
        shadow=True,
    )

    # باکس ۳ (کادر مشکی پایینی): خلاصه / زیرتیتر تکمیلی
    sub_text = subtitle.strip() if subtitle and subtitle.strip() else f"پوشش لحظه‌ای اخبار شیراز و فارس | {BRAND_HANDLE}"
    draw_centered_block_in_box(
        draw,
        boxes["sub_box"],
        sub_text,
        font_kind="bold",
        fill=(235, 240, 248, 255),
        max_size=38,
        min_size=22,
        max_lines=3,
        align="center",
        pad_x=32,
        pad_y=14,
    )

    out_p = os.path.join(work_dir, f"filled_reel_frame_{int(time.time()*1000)}.png")
    frame.save(out_p, format="PNG")
    return out_p


def detect_story_frame_boxes(frame_rgb: Image.Image) -> dict:
    """تشخیص خودکار ۴ بخش قاب استوری پیج (نوار قرمز بالا، کادر عکس، کارت سفید پایین و برچسب قرمز پایین)."""
    arr = np.array(frame_rgb.resize((1080, 1920), Image.Resampling.LANCZOS))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # مقادیر دقیق کالیبره‌شده بر اساس ۰۳_استوری_خبر_فوری_خام.png
    boxes = {
        "top_red": (60, 120, 1020, 240),
        "photo_box": (60, 282, 1020, 1218),
        "white_box": (60, 1262, 1020, 1752),
        "bottom_red": (840, 1638, 972, 1702),
    }

    # ۱. تشخیص بخش‌های قرمز (بالا و برچسب کوچک پایین)
    red_mask = ((r > 155) & (g < 85) & (b < 85)).astype(np.uint8) * 255
    cnts_r, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts_r:
        x, y, w, h = cv2.boundingRect(c)
        if y < 500 and w > 400 and h > 40:
            boxes["top_red"] = (x, y, x + w, y + h)
        elif y > 1200 and w >= 70 and h >= 30:
            boxes["bottom_red"] = (x, y, x + w, y + h)

    # ۲. تشخیص کادر طوسی تیره محل قرارگیری عکس خبر
    gray_mask = ((r >= 15) & (r <= 80) & (g >= 15) & (g <= 85) & (b >= 15) & (b <= 95)).astype(np.uint8) * 255
    cnts_g, _ = cv2.findContours(gray_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_g = None
    best_area = 0
    for c in cnts_g:
        x, y, w, h = cv2.boundingRect(c)
        if w > 500 and h > 400 and (w * h) > best_area:
            best_area = w * h
            best_g = (x, y, x + w, y + h)
    if best_g:
        boxes["photo_box"] = best_g

    # ۳. تشخیص کارت سفید پایین برای تیتر و خلاصه
    white_mask = ((r > 210) & (g > 210) & (b > 210)).astype(np.uint8) * 255
    cnts_w, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_w = None
    best_w_area = 0
    for c in cnts_w:
        x, y, w, h = cv2.boundingRect(c)
        if w > 500 and h > 220 and y > 900 and (w * h) > best_w_area:
            best_w_area = w * h
            best_w = (x, y, x + w, y + h)
    if best_w:
        boxes["white_box"] = best_w

    return boxes


def clean_caption_markdown(text: str) -> str:
    text = text.replace("**", "").replace("__", "").replace("```", "")
    lines = [ln.rstrip() for ln in text.strip().splitlines()]
    return "\n".join(lines).strip()


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


# ==================== کیبوردهای ثابت منوی پایین صفحه ====================
def kb_main_menu() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_CARD_POST}, {"text": BTN_CARD_STORY}],
            [{"text": BTN_INCIDENT}],
            [{"text": BTN_CAPTION}],
            [{"text": BTN_MAP}, {"text": BTN_AUDIO}],
            [{"text": BTN_DAILY60}],
            [{"text": BTN_VIDEO}, {"text": BTN_CLEAN_LOGO}],
            [{"text": BTN_SHADOWBAN}, {"text": BTN_THEME}],
            [{"text": BTN_OCCASION}, {"text": BTN_STATUS}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_cancel(extra_row: list = None) -> dict:
    rows = []
    if extra_row:
        rows.append(extra_row)
    rows.append([{"text": BTN_CANCEL}])
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


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


def kb_video_studio() -> dict:
    def st(b):
        return "روشن ✅" if b else "خاموش ❌"

    return {
        "keyboard": [
            [{"text": f"🖼️ قاب ریلز (reel_frame): {st(CONFIG['use_repo_frame'])}"}, {"text": f"📱 قاب استوری: {st(CONFIG['use_story_frame'])}"}],
            [{"text": f"⚡ قلاب شوک اول ویدئو: {st(CONFIG['video_hook_intro'])}"}, {"text": f"📰 زیرنویس متحرک خبر: {st(CONFIG['video_ticker'])}"}],
            [{"text": f"🧬 اصالت‌سازی: {st(CONFIG['video_antidup'])}"}, {"text": f"👤 ردیابی چهره: {st(CONFIG['video_facetrack'])}"}],
            [{"text": f"🏷️ اند-اسکرین فالو: {st(CONFIG['video_brand'])}"}],
            [{"text": BTN_BACK}],
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
        "keyboard": [
            [{"text": BTN_SAFE_REWRITE}],
            [{"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def build_status_text() -> str:
    now_str = to_persian_digits(get_tehran_now().strftime("%H:%M"))
    t_name = THEMES[CONFIG["theme"]]["name"]
    ai_status = "متصل ✅" if GEMINI_API_KEY else "کلید GEMINI_API_KEY ثبت نشده ⚠️"
    raqm_status = "فعال ✅" if HAS_RAQM else "پشتیبان"

    r_fr = find_repo_reel_frame()
    s_fr = find_repo_story_frame()
    inc_mp3 = find_repo_audio("incident")

    r_st = f"فعال ✅ ({os.path.basename(r_fr)})" if r_fr else "آپلود نشده (reel_frame.png)"
    s_st = f"فعال ✅ ({os.path.basename(s_fr)})" if s_fr else "آپلود نشده (story_frame.png)"
    a_st = f"موزیک اختصاصی ({os.path.basename(inc_mp3)})" if inc_mp3 else "آژیر اورژانسی داخلی ✅"

    return (
        f"🎬 استودیوی تولید محتوای {BRAND_HANDLE}\n\n"
        f"🕒 ساعت تهران: {now_str} | 🎨 {t_name}\n"
        f"🖼️ قاب ریلز ۳ باکسه: {r_st}\n"
        f"📱 قاب استوری پیج: {s_st}\n"
        f"🚨 صدای ریلز حادثه‌ای: {a_st}\n"
        f"🔤 فارسی‌نویس: {raqm_status} | 🧠 هوش مصنوعی: {ai_status}\n"
        f"📦 صف جمع‌بندی ۶۰ ثانیه‌ای امروز: {to_persian_digits(str(len(DAILY_ITEMS)))} خبر\n\n"
        "از منوی پایین صفحه، ابزار موردنظر را انتخاب کنید:"
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
        res = await tg_api(session, "editMessageText", {
            "chat_id": ADMIN_ID,
            "message_id": CONFIG_MSG_ID,
            "text": payload_text,
        })
        if res and res.get("ok"):
            return
    sent = await send_message(session, ADMIN_ID, payload_text)
    if sent and sent.get("ok"):
        CONFIG_MSG_ID = sent["result"]["message_id"]
        await tg_api(session, "pinChatMessage", {
            "chat_id": ADMIN_ID,
            "message_id": CONFIG_MSG_ID,
            "disable_notification": True,
        })


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
    meta = {"file": {"display_name": os.path.basename(file_path)}}
    async with session.post(init_url, headers=headers, json=meta, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        upload_url = resp.headers.get("X-Goog-Upload-URL")
        if not upload_url:
            return ""

    with open(file_path, "rb") as f:
        raw = f.read()

    up_headers = {
        "Content-Length": str(file_size),
        "X-Goog-Upload-Offset": "0",
        "X-Goog-Upload-Command": "upload, finalize",
    }
    async with session.post(upload_url, headers=up_headers, data=raw, timeout=aiohttp.ClientTimeout(total=120)) as resp:
        if resp.status != 200:
            return ""
        info = await resp.json()

    file_obj = info.get("file", {})
    file_uri = file_obj.get("uri", "")
    file_name = file_obj.get("name", "")
    state = file_obj.get("state", "")

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
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.4},
    }

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
                        txt_parts = cands[0].get("content", {}).get("parts", [])
                        out = "".join(p.get("text", "") for p in txt_parts).strip()
                        if out:
                            return clean_caption_markdown(out)
        except Exception:
            continue
    return ""


async def generate_editorial_caption(
    session: aiohttp.ClientSession,
    news_text: str = "",
    media_path: str = None,
    mime_type: str = None,
    force_incident: bool = False,
) -> str:
    extra = ""
    if force_incident:
        extra = "\nتوجه ویژه: این خبر یک خبر فوری/حادثه‌ای است؛ تیتر خط اول حتماً با «⭕ فوری | ...» شروع شود.\n"
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


async def extract_news_parts(session: aiohttp.ClientSession, news_text: str, is_incident: bool = False) -> tuple:
    """استخراج دقیق ۳ بخش بدون ایموجی برای پر کردن هر ۳ باکس قاب ریلز و قاب استوری: (برچسب، تیتر کوتاه، زیرتیتر تکمیلی)."""
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
            badge = "خبر فوری" if is_incident else lines[0][:22]
            return badge, lines[1][:105], lines[2][:150]
        if len(lines) == 2:
            badge = "خبر فوری" if is_incident else lines[0][:22]
            return badge, lines[1][:105], f"پوشش لحظه‌ای اخبار شیراز و فارس | {BRAND_HANDLE}"

    raw_lines = [strip_emojis_for_font(ln) for ln in (news_text or "").splitlines() if strip_emojis_for_font(ln)]
    hl = raw_lines[0][:100] if raw_lines else BRAND_TITLE_FA
    sub = raw_lines[1][:145] if len(raw_lines) > 1 else f"پوشش لحظه‌ای اخبار شیراز و فارس | {BRAND_HANDLE}"
    badge = "خبر فوری" if is_incident else "خبر شیراز"
    return badge, hl, sub


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
    res = await gemini_generate(session, p)
    return res or caption_text
    # ==================== نوار زیرنویس متحرک شبکه خبر (مورد ۷) ====================
def build_scrolling_ticker_strip(text: str, duration_sec: float, bg_color=(185, 28, 28, 240), text_color=(255, 255, 255, 255), height: int = 74) -> Image.Image:
    """ساخت نوار زیرنویس پیوسته فارسی برای حرکت روان از چپ به راست (خوانش طبیعی فارسی)."""
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


def pipe_frames_to_mp4(frame_generator, out_mp4: str, audio_path: str, fps: int = 25):
    """ارسال مستقیم فریم‌های تصویر به FFmpeg با سرعت بالا و بدون خطای flush of closed file."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", "1080x1920", "-r", str(fps),
        "-i", "-",
        "-stream_loop", "-1",
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


# ==================== ۱. کارت‌ساز پست و استوری با هویت بصری اختصاصی @ShirazLastNews ====================
def draw_quran_gate_fallback(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 112):
    """رسم آیکون سفید دروازه قرآن در صورت نبود فایل logo.png در مخزن."""
    w_c = (255, 255, 255, 255)
    # بدنه اصلی و ۳ طاق
    draw.rectangle([(x + 12, y + 26), (x + size - 12, y + size - 12)], outline=w_c, width=4)
    draw.rectangle([(x + 30, y + 10), (x + size - 30, y + 26)], outline=w_c, width=4)
    # طاق بزرگ میانی
    draw.rounded_rectangle([(x + 38, y + 48), (x + size - 38, y + size - 10)], radius=18, outline=w_c, width=4)
    # دو طاق کناری
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
    draw_centered_block_in_box(
        draw, (530, 52, 1052, 202), top_label, "bold", (255, 255, 255, 255),
        max_size=62, min_size=34, max_lines=1, align="center", pad_x=16, pad_y=6
    )

    # ۲. لوگوی دروازه قرآن بالا سمت چپ (از logo.png مخزن یا آیکون خطی سفید)
    logo_path = find_repo_logo()
    if logo_path:
        try:
            lg = Image.open(logo_path).convert("RGBA")
            lg.thumbnail((138, 108), Image.Resampling.LANCZOS)
            lx = 78 + (138 - lg.width) // 2
            ly = 38 + (108 - lg.height) // 2
            canvas.alpha_composite(lg, (lx, ly))
        except Exception:
            draw_quran_gate_fallback(draw, 84, 38, 110)
    else:
        draw_quran_gate_fallback(draw, 84, 38, 110)

    # ۳. نشانگر LIVE با نقطه قرمز زیر لوگو
    draw.rounded_rectangle([(68, 158), (222, 212)], radius=27, fill=(28, 29, 34, 255), outline=(48, 50, 56, 255), width=2)
    draw.ellipse([(88, 173), (112, 197)], fill=(212, 28, 38, 255))
    draw_rtl_text(draw, (124, 169), "LIVE", load_font("bold", 28), (196, 44, 52, 255), align="left", shadow=False, is_rtl=False)

    # ۴. کادر اصلی عکس با گوشه‌های گرد و حاشیه باریک خاکستری
    px1, py1, px2, py2 = 46, 276, 1034, 1236
    pw, ph = px2 - px1, py2 - py1
    if photo_path and os.path.exists(photo_path):
        pic = fit_cover(Image.open(photo_path).convert("RGB"), pw, ph)
    else:
        theme = THEMES.get(CONFIG["theme"], THEMES["navy"])
        pic = Image.new("RGB", (pw, ph), theme["bg"])

    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (pw, ph)], radius=34, fill=255)
    canvas.paste(pic, (px1, py1), mask)
    draw.rounded_rectangle([(px1, py1), (px2, py2)], radius=34, outline=(105, 108, 118, 220), width=3)

    # ۵. کارت سفید هم‌پوشان روی لبه پایینی عکس (با سایه نرم)
    wx1, wy1, wx2, wy2 = 66, 1142, 1014, 1720
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([(wx1, wy1 + 10), (wx2, wy2 + 12)], radius=38, fill=(0, 0, 0, 125))
    sh = sh.filter(ImageFilter.GaussianBlur(radius=16))
    canvas = Image.alpha_composite(canvas, sh)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([(wx1, wy1), (wx2, wy2)], radius=38, fill=(255, 255, 255, 255))

    # ۶. تیتر اصلی مشکی و خلاصه ۲ تا ۳ خطی داخل کارت سفید
    text_max_w = (wx2 - wx1) - 96
    hl_font, hl_lines, hl_lh = fit_text_in_box(
        draw, headline or BRAND_TITLE_FA, "bold", text_max_w, 225,
        max_size=50, min_size=30, max_lines=3, line_spacing=1.38
    )
    cur_y = wy1 + 46
    for ln in hl_lines:
        draw_rtl_text(draw, (wx2 - 48, cur_y), ln, hl_font, (18, 20, 24, 255), align="right", shadow=False)
        cur_y += hl_lh

    if subtext:
        rem_h = max(65, (wy2 - 148) - (cur_y + 14))
        sub_font, sub_lines, sub_lh = fit_text_in_box(
            draw, subtext, "regular", text_max_w, rem_h,
            max_size=35, min_size=24, max_lines=3, line_spacing=1.42
        )
        sy = cur_y + 18
        for sl in sub_lines:
            draw_rtl_text(draw, (wx2 - 48, sy), sl, sub_font, (38, 42, 48, 255), align="right", shadow=False)
            sy += sub_lh

    # ۷. کپسول قرمز گوشه پایین راست کارت سفید
    bx1, by1, bx2, by2 = 768, 1594, 962, 1662
    draw.rounded_rectangle([(bx1, by1), (bx2, by2)], radius=22, fill=(204, 18, 28, 255))
    short_tag = "فوری" if "فوری" in top_label else (top_label.split("|")[0].strip().split()[-1] if top_label.split() else "فوری")
    draw_centered_block_in_box(
        draw, (bx1, by1, bx2, by2), short_tag[:12], "bold", (255, 255, 255, 255),
        max_size=30, min_size=20, max_lines=1, align="center", pad_x=10, pad_y=4
    )

    # ۸. تاریخ شمسی و آیدی پیج در گوشه پایین چپ کارت سفید
    jnow = jdatetime.datetime.fromgregorian(datetime=get_tehran_now())
    date_slash = to_persian_digits(f"{jnow.year:04d}/{jnow.month:02d}/{jnow.day:02d}")
    f_meta = load_font("bold", 29)
    d_txt, d_kw = prepare_text_and_kwargs(date_slash, is_rtl=False)
    dbb = draw.textbbox((0, 0), d_txt, font=f_meta, **d_kw)
    draw_rtl_text(draw, (wx1 + 48, 1612), date_slash, f_meta, (95, 100, 110, 255), align="left", shadow=False, is_rtl=False)
    draw_rtl_text(draw, (wx1 + 48 + (dbb[2] - dbb[0]) + 10, 1612), "| @ShirazLastNews", f_meta, (95, 100, 110, 255), align="left", shadow=False, is_rtl=False)

    # ۹. نوار فوتر پایین صفحه با برش قرمز اریب سمت چپ و نام منبع
    draw.rectangle([(0, 1794), (w, 1884)], fill=(36, 39, 44, 255))
    draw.polygon([(0, 1794), (275, 1794), (235, 1884), (0, 1884)], fill=(204, 18, 28, 255))
    src_clean = strip_emojis_for_font(source_name)
    footer_txt = f"منبع: {src_clean}  |  آخرین خبرهای شیراز و استان فارس" if src_clean else "آخرین خبرهای شیراز و استان فارس"
    draw_centered_block_in_box(
        draw, (285, 1802, 1032, 1876), footer_txt, "bold", (245, 247, 250, 255),
        max_size=30, min_size=20, max_lines=1, align="right", pad_x=6, pad_y=4
    )

    out_path = os.path.join(TMP_ROOT, f"story_brand_{int(time.time()*1000)}.jpg")
    canvas.convert("RGB").save(out_path, quality=94)
    return out_path


def render_news_card_sync(photo_path: str, badge: str, headline: str, subtext: str, fmt: str = "post", theme_key: str = "navy", source_name: str = "") -> str:
    # برای استوری همیشه از هویت بصری اختصاصی پیج استفاده می‌شود
    if fmt == "story":
        return render_brand_story_sync(photo_path, badge, headline, subtext, source_name=source_name)

    theme = THEMES.get(theme_key, THEMES["navy"])
    w, h = 1080, 1350

    if photo_path and os.path.exists(photo_path):
        canvas = fit_cover(Image.open(photo_path).convert("RGB"), w, h).convert("RGBA")
    else:
        canvas = Image.new("RGBA", (w, h), theme["bg"] + (255,))

    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad)
    bg_r, bg_g, bg_b = theme["bg"]

    for y in range(260):
        gdraw.line([(0, y), (w, y)], fill=(bg_r, bg_g, bg_b, int(195 * (1 - y / 260))))

    bottom_start = int(h * 0.40)
    for y in range(bottom_start, h):
        ratio = (y - bottom_start) / (h - bottom_start)
        gdraw.line([(0, y), (w, y)], fill=(bg_r, bg_g, bg_b, int(250 * (ratio ** 1.3))))

    canvas = Image.alpha_composite(canvas, grad)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([(0, 0), (w, 16)], fill=theme["accent"] + (255,))

    jnow = jdatetime.datetime.fromgregorian(datetime=get_tehran_now())
    date_str = to_persian_digits(f"{jnow.day} {JALALI_MONTHS[jnow.month]} {jnow.year}")

    draw_rtl_text(draw, (w - 54, 46), BRAND_TITLE_FA, load_font("bold", 34), theme["text"] + (255,), align="right")
    draw_rtl_text(draw, (54, 52), BRAND_HANDLE, load_font("regular", 28), theme["accent"] + (255,), align="left", shadow=False, is_rtl=False)
    draw_rtl_text(draw, (w - 54, 96), date_str, load_font("regular", 24), theme["subtext"] + (230,), align="right", shadow=False)

    f_title, lines, line_h = fit_text_in_box(
        draw, headline, "display", w - 130, 270, max_size=66, min_size=34, max_lines=4
    )
    block_h = max(line_h, len(lines) * line_h)
    sub_h = 110 if subtext else 0
    title_start_y = h - 210 - sub_h - block_h

    f_badge = load_font("bold", 34)
    clean_badge = strip_emojis_for_font(badge) or "خبر شیراز"
    b_txt, b_kw = prepare_text_and_kwargs(clean_badge, is_rtl=True)
    bb = draw.textbbox((0, 0), b_txt, font=f_badge, **b_kw)
    bw = (bb[2] - bb[0]) + 56
    bh = 62
    badge_y = title_start_y - bh - 26

    draw.rounded_rectangle([(w - 56 - bw, badge_y), (w - 56, badge_y + bh)], radius=12, fill=theme["badge_bg"] + (255,))
    draw_rtl_text(draw, (w - 56 - bw // 2, badge_y + 10), clean_badge, f_badge, theme["badge_text"] + (255,), align="center", shadow=False)
    draw.rectangle([(w - 42, title_start_y + 8), (w - 30, title_start_y + block_h - 10)], fill=theme["accent"] + (255,))

    cur_y = title_start_y
    for ln in lines:
        draw_rtl_text(draw, (w - 64, cur_y), ln, f_title, theme["text"] + (255,), align="right", shadow=True, shadow_offset=5)
        cur_y += line_h

    if subtext:
        sub_box = (60, cur_y + 12, w - 64, cur_y + 115)
        draw_centered_block_in_box(
            draw, sub_box, subtext, "regular", theme["subtext"] + (240,),
            max_size=30, min_size=22, max_lines=2, align="right", pad_x=0, pad_y=2
        )

    footer_y = h - 88
    draw.line([(54, footer_y - 18), (w - 54, footer_y - 18)], fill=theme["accent"] + (130,), width=2)
    draw_rtl_text(draw, (w - 54, footer_y), "پوشش لحظه‌ای اخبار شیراز و فارس", load_font("regular", 26), theme["subtext"] + (220,), align="right", shadow=False)
    draw_rtl_text(draw, (54, footer_y), BRAND_HANDLE, load_font("bold", 28), theme["accent"] + (255,), align="left", shadow=False, is_rtl=False)

    out_path = os.path.join(TMP_ROOT, f"card_{fmt}_{int(time.time()*1000)}.jpg")
    canvas.convert("RGB").save(out_path, quality=94)
    return out_path


# ==================== ۲. ریلز فوری و حادثه‌ای بازطراحی‌شده (شوک + آژیر + تایپ زنده + زیرنویس شبکه خبر) ====================
def build_incident_reel_sync(photo_path: str, headline: str, subtext: str = "") -> str:
    """ریلز اضطراری ۱۲ ثانیه‌ای: قلاب ۱.۵ ثانیه شوک، لرزش دوربین، چراغ گردان آژیر، تایپ زنده تیتر و نوار زیرنویس شبکه خبر."""
    w, h, fps, duration = 1080, 1920, 25, 12.0
    total_frames = int(fps * duration)
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)

    # پس‌زمینه حادثه‌ای با کنتراست سینمایی بالا
    if photo_path and os.path.exists(photo_path):
        bg_big = fit_cover(Image.open(photo_path).convert("RGB"), 1260, 2240)
    else:
        bg_big = Image.new("RGB", (1260, 2240), (24, 10, 14))
    bg_arr = np.array(bg_big, dtype=np.uint8)

    # دو فریم نور چراغ گردان قرمز و آبی بسیار پرقدرت
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

    # فریم شوک ۱.۵ ثانیه اول (Hook Flash Intro - مورد ۵)
    shock_red = Image.new("RGBA", (w, h), (210, 20, 32, 200))
    sd = ImageDraw.Draw(shock_red)
    sd.rounded_rectangle([(90, 740), (w - 90, 1140)], radius=28, fill=(10, 10, 14, 240), outline=(250, 204, 21, 255), width=8)
    draw_rtl_text(sd, (w // 2, 795), "خبر فوری", load_font("display", 120), (250, 204, 21, 255), align="center")
    draw_rtl_text(sd, (w // 2, 970), "گزارش اضطراری حادثه", load_font("bold", 54), (255, 255, 255, 255), align="center")

    shock_white = Image.new("RGBA", (w, h), (255, 255, 255, 215))

    # لایه ثابت گرافیک اضطراری (نوارهای خطر، ساعت وقوع، کادر تیتر، برند)
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

    # کادر بالای «فوری | حادثه» با فضای نقطه قرمز چشمک‌زن
    od.rounded_rectangle([(w - 490, 110), (w - 44, 206)], radius=14, fill=(220, 24, 34, 252), outline=(250, 204, 21, 255), width=5)
    draw_rtl_text(od, (w - 295, 128), "فوری | حادثه", load_font("display", 52), (255, 255, 255, 255), align="center", shadow=False)

    # ساعت زنده وقوع
    now_t = to_persian_digits(get_tehran_now().strftime("%H:%M"))
    od.rounded_rectangle([(44, 118), (315, 200)], radius=12, fill=(12, 12, 16, 235), outline=(220, 38, 38, 255), width=4)
    draw_rtl_text(od, (180, 136), f"ساعت {now_t}", load_font("bold", 34), (250, 204, 21, 255), align="center", shadow=False)

    # جعبه بزرگ تیتر حادثه با حاشیه هشدار قرمز و خط زرد
    box_top, box_bot = 1150, 1540
    od.rounded_rectangle([(42, box_top), (w - 42, box_bot)], radius=20, fill=(12, 8, 12, 235), outline=(235, 30, 40, 255), width=6)
    od.rectangle([(w - 62, box_top + 24), (w - 46, box_bot - 24)], fill=(250, 204, 21, 255))

    # برچسب برند بالای نوار زیرنویس
    draw_rtl_text(od, (w - 50, 1565), BRAND_TITLE_FA, load_font("bold", 32), (250, 204, 21, 255), align="right")
    draw_rtl_text(od, (50, 1565), BRAND_HANDLE, load_font("bold", 32), (255, 255, 255, 255), align="left", is_rtl=False)

    # آماده‌سازی مراحل تایپ زنده تیتر (کلمه‌به‌کلمه - مورد ۶)
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

    # نوار زیرنویس متحرک شبکه خبر (مورد ۷)
    ticker_msg = f"فوری: {clean_hl}" + (f"  —  {strip_emojis_for_font(subtext)}" if subtext else "")
    ticker_strip = build_scrolling_ticker_strip(ticker_msg, duration, bg_color=(195, 22, 32, 248), height=78)
    strip_w = ticker_strip.size[0]
    ticker_y = 1665

    audio_path = get_audio_track(work_dir, duration, mode="incident")
    out_mp4 = os.path.join(TMP_ROOT, f"incident_reel_{int(time.time()*1000)}.mp4")

    def frame_gen():
        bh_src, bw_src = bg_arr.shape[:2]
        for i in range(total_frames):
            t = i / fps
            # زوم پیش‌رونده + لرزش ضربه‌ای کوتاه در ۱.۵ ثانیه اول
            zoom = 1.0 + 0.14 * (t / duration)
            crop_w = int(bw_src / zoom)
            crop_h = int(bh_src / zoom)
            shake_x = int(math.sin(t * 58.0) * 18 * max(0.0, 1.0 - t / 1.5))
            shake_y = int(math.cos(t * 64.0) * 18 * max(0.0, 1.0 - t / 1.5))

            x0 = max(0, min(bw_src - crop_w, (bw_src - crop_w) // 2 + shake_x))
            y0 = max(0, min(bh_src - crop_h, (bh_src - crop_h) // 2 + shake_y))
            cropped = bg_arr[y0:y0 + crop_h, x0:x0 + crop_w]
            resized = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
            frame = Image.fromarray(resized).convert("RGBA")

            # نور چراغ گردان آژیر (تغییر سریع هر ۰.۳۸ ثانیه)
            siren_img = siren_a if (int(t / 0.38) % 2 == 0) else siren_b
            frame.alpha_composite(siren_img)
            frame.alpha_composite(static_ov)

            # نقطه قرمز چشمک‌زن LIVE در کادر فوری
            if int(t * 3.5) % 2 == 0:
                fd = ImageDraw.Draw(frame)
                fd.ellipse([(w - 102, 142), (w - 70, 174)], fill=(250, 204, 21, 255))

            # تایپ زنده تیتر کلمه‌به‌کلمه از ثانیه ۱.۲ تا ۵.۰
            if t >= 1.1 and type_overlays:
                prog = min(1.0, (t - 1.1) / max(1.8, min(3.8, len(type_overlays) * 0.35)))
                idx = min(len(type_overlays) - 1, int(prog * len(type_overlays)))
                frame.alpha_composite(type_overlays[idx])

            # نوار زیرنویس متحرک شبکه خبر (ورود از چپ به راست)
            src_x = max(0, min(strip_w - w, (strip_w - w) - int(t * 175)))
            tick_crop = ticker_strip.crop((src_x, 0, src_x + w, 78))
            frame.alpha_composite(tick_crop, (0, ticker_y))

            # قلاب ۱.۵ ثانیه اول شوک (فلش سفید لحظه‌ای + کارت هشدار فوری)
            if t < 0.16 or (0.48 <= t < 0.60):
                frame.alpha_composite(shock_white)
            elif t < 1.25:
                frame.alpha_composite(shock_red)

            yield np.array(frame.convert("RGB"), dtype=np.uint8)

    pipe_frames_to_mp4(frame_gen(), out_mp4, audio_path, fps=fps)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۳. ریلز زوم سینمایی روی نقشه (رفع قطعی با ۳ سرور پشتیبان + زوم دومرحله‌ای) ====================
def latlon_to_tile_float(lat: float, lon: float, zoom: int):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xf = (lon + 180.0) / 360.0 * n
    yf = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return xf, yf


async def resolve_location_coords(session: aiohttp.ClientSession, loc_name: str):
    clean = strip_emojis_for_font(loc_name)
    for key, val in FARS_LOCATIONS.items():
        if key in clean:
            return val
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": f"{clean}, Iran", "format": "json", "limit": 1}
        headers = {"User-Agent": "ShirazLastNewsMedia/2.0 (contact@shirazlastnews.local)"}
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"]), 14
    except Exception:
        pass
    return FARS_LOCATIONS["شیراز"]


async def fetch_reliable_map_image(session: aiohttp.ClientSession, lat: float, lon: float, zoom: int) -> Image.Image:
    """دریافت نقشه واقعی از ۳ سرور پشتیبان (Esri Street، Carto Voyager، OpenStreetMap و Esri Satellite)."""
    xf, yf = latlon_to_tile_float(lat, lon, zoom)
    cx, cy = int(xf), int(yf)
    max_t = (2 ** zoom) - 1

    providers = [
        ("esri_street", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"),
        ("carto_voyager", "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"),
        ("osm", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"),
        ("esri_sat", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"),
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/png,image/*,*/*;q=0.8",
    }

    for _, template in providers:
        grid = Image.new("RGB", (256 * 5, 256 * 5), (20, 30, 46))
        loaded = [0]

        async def get_tile(dx, dy):
            tx = max(0, min(max_t, cx + dx))
            ty = max(0, min(max_t, cy + dy))
            url = template.format(z=zoom, x=tx, y=ty)
            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        raw = await r.read()
                        tile = Image.open(io.BytesIO(raw)).convert("RGB")
                        grid.paste(tile, ((dx + 2) * 256, (dy + 2) * 256))
                        loaded[0] += 1
            except Exception:
                pass

        await asyncio.gather(*(get_tile(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)))
        if loaded[0] >= 9:
            # مرکز تصویر دقیقاً روی مختصات محله تنظیم می‌شود
            px = int((xf - (cx - 2)) * 256)
            py = int((yf - (cy - 2)) * 256)
            half_w, half_h = 360, 640
            left = max(0, min(grid.width - half_w * 2, px - half_w))
            top = max(0, min(grid.height - half_h * 2, py - half_h))
            cropped = grid.crop((left, top, left + half_w * 2, top + half_h * 2))
            return cropped.resize((1200, 2134), Image.Resampling.LANCZOS)

    # پشتیبان گرافیکی رادار فقط در صورت قطع سراسری تمام سرورهای نقشه
    fallback = Image.new("RGB", (1200, 2134), (15, 26, 42))
    fd = ImageDraw.Draw(fallback)
    for x in range(0, 1200, 80):
        fd.line([(x, 0), (x, 2134)], fill=(30, 48, 72), width=2)
    for y in range(0, 2134, 80):
        fd.line([(0, y), (1200, y)], fill=(30, 48, 72), width=2)
    return fallback


def build_map_zoom_reel_sync(wide_map: Image.Image, close_map: Image.Image, photo_path: str, loc_name: str, badge: str, headline: str, subtext: str) -> str:
    """ریلز ۱۲ ثانیه‌ای زوم دومرحله‌ای روی نقشه واقعی + پین رادار متحرک + ورود به خبر با قاب ۳ باکسه پیج."""
    w, h, fps, duration = 1080, 1920, 25, 12.0
    total_frames = int(fps * duration)
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)

    wide_arr = np.array(wide_map.convert("RGB"), dtype=np.uint8)
    close_arr = np.array(close_map.convert("RGB"), dtype=np.uint8)

    if photo_path and os.path.exists(photo_path):
        news_arr = np.array(fit_cover(Image.open(photo_path).convert("RGB"), 1200, 2134), dtype=np.uint8)
    else:
        news_arr = close_arr.copy()

    # لایه هدر و برچسب موقعیت روی نقشه
    map_hud = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(map_hud)
    for y in range(240):
        hd.line([(0, y), (w, y)], fill=(10, 18, 32, int(225 * (1 - y / 240))))
    for y in range(1580, h):
        r = (y - 1580) / (h - 1580)
        hd.line([(0, y), (w, y)], fill=(10, 18, 32, int(235 * r)))
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

    # لایه خبر (از قاب ۳ باکسه reel_frame.png با متن‌های پرشده استفاده می‌کند)
    repo_frame = find_repo_reel_frame() if CONFIG["use_repo_frame"] else ""
    if repo_frame:
        filled_path = render_reel_frame_overlay(repo_frame, badge or loc_clean, headline, subtext, work_dir)
        news_ov = Image.open(filled_path).convert("RGBA")
    else:
        card_p = render_news_card_sync(photo_path, badge or loc_clean, headline, subtext, fmt="story", theme_key=CONFIG["theme"])
        news_ov = Image.open(card_p).convert("RGBA")

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
                # مرحله ۱: زوم سریع از نقشه کلان استان به سمت شهر
                z = 1.0 + 0.55 * (t / 2.6)
                base_rgb = zoom_slice(wide_arr, z)
                frame = Image.fromarray(base_rgb).convert("RGBA")
                frame.alpha_composite(map_hud)
            elif t < 5.6:
                # مرحله ۲: نمای دقیق خیابان‌ها و محله + موج رادار متحرک
                lt = (t - 2.6) / 3.0
                z = 1.0 + 0.25 * lt
                close_rgb = zoom_slice(close_arr, z)
                if t < 3.1:
                    alpha = (t - 2.6) / 0.5
                    wide_rgb = zoom_slice(wide_arr, 1.55)
                    close_rgb = cv2.addWeighted(wide_rgb, 1.0 - alpha, close_rgb, alpha, 0)
                frame = Image.fromarray(close_rgb).convert("RGBA")
                frame.alpha_composite(map_hud)

                # پین رادار نبض‌دار قرمز در مرکز دقیق محله
                rd = ImageDraw.Draw(frame)
                pulse_r = int(35 + ((t * 160) % 180))
                pulse_a = max(30, int(230 * (1.0 - (pulse_r - 35) / 180.0)))
                rd.ellipse([(cx - pulse_r, cy - pulse_r), (cx + pulse_r, cy + pulse_r)], outline=(239, 68, 68, pulse_a), width=6)
                rd.ellipse([(cx - 42, cy - 42), (cx + 42, cy + 42)], fill=(239, 68, 68, 120), outline=(255, 255, 255, 240), width=4)
                rd.ellipse([(cx - 16, cy - 16), (cx + 16, cy + 16)], fill=(220, 38, 38, 255))
            else:
                # مرحله ۳: ورود به تصویر خبر با قاب ۳ باکسه پرشده
                nt = (t - 5.6) / 6.4
                z = 1.0 + 0.10 * nt
                n_rgb = zoom_slice(news_arr, z)
                if t < 6.1:
                    alpha = (t - 5.6) / 0.5
                    m_rgb = zoom_slice(close_arr, 1.25)
                    n_rgb = cv2.addWeighted(m_rgb, 1.0 - alpha, n_rgb, alpha, 0)
                frame = Image.fromarray(n_rgb).convert("RGBA")
                frame.alpha_composite(news_ov)

            if CONFIG.get("video_ticker", True):
                src_x = max(0, min(strip_w - w, (strip_w - w) - int(t * 165)))
                tick_crop = ticker_strip.crop((src_x, 0, src_x + w, 70))
                frame.alpha_composite(tick_crop, (0, 1795))

            yield np.array(frame.convert("RGB"), dtype=np.uint8)

    pipe_frames_to_mp4(frame_gen(), out_mp4, audio_path, fps=fps)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۴. ریلز جمع‌بندی ترکیبی (تمام‌صفحه + برودکست اریب + گرادیان شیشه‌ای) ====================
def build_daily_summary_reel_sync(items: list) -> str:
    w, h, fps = 1080, 1920, 25
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)
    selected = items[:8]
    n_news = len(selected)

    # شبکه کم‌حجم برای رندر فوق‌سریع گرادیان اتمسفریک متحرک (مدل ۳)
    gw, gh = 135, 240
    gy_grid, gx_grid = np.mgrid[0:gh, 0:gw].astype(np.float32)
    gx_norm = gx_grid / gw
    gy_norm = gy_grid / gh

    def make_dark_gradient_bg(t_sec: float, tint_rgb=(196, 22, 34)):
        """پس‌زمینه ذغالی-سرمه‌ای با ۲ هاله نور متحرک سینمایی."""
        c1x = 0.25 + 0.18 * math.sin(t_sec * 0.65)
        c1y = 0.28 + 0.14 * math.cos(t_sec * 0.50)
        c2x = 0.78 + 0.16 * math.cos(t_sec * 0.55)
        c2y = 0.76 + 0.12 * math.sin(t_sec * 0.70)

        d1 = np.exp(-((gx_norm - c1x) ** 2 + ((gy_norm - c1y) * 1.45) ** 2) / 0.18)
        d2 = np.exp(-((gx_norm - c2x) ** 2 + ((gy_norm - c2y) * 1.45) ** 2) / 0.22)

        r = np.clip(13.0 + d1 * (tint_rgb[0] * 0.42) + d2 * 22.0, 0, 255)
        g = np.clip(16.0 + d1 * (tint_rgb[1] * 0.42) + d2 * 38.0, 0, 255)
        b = np.clip(23.0 + d1 * (tint_rgb[2] * 0.42) + d2 * 68.0, 0, 255)
        small = np.stack([r, g, b], axis=-1).astype(np.uint8)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)

    def apply_glass_box(bg_rgb: np.ndarray, box: tuple, radius: int = 34, tint=(14, 17, 25), alpha: float = 0.62) -> Image.Image:
        """ساخت افکت شیشه مات واقعی (Glassmorphism) دقیقاً روی کادر مشخص‌شده از فریم زنده."""
        x1, y1, x2, y2 = box
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        bw, bh = x2 - x1, y2 - y1
        if bw < 20 or bh < 20:
            return Image.fromarray(bg_rgb).convert("RGBA")

        crop = bg_rgb[y1:y2, x1:x2]
        small = cv2.resize(crop, (max(8, bw // 4), max(8, bh // 4)), interpolation=cv2.INTER_LINEAR)
        blurred = cv2.GaussianBlur(small, (21, 21), 0)
        frosted = cv2.resize(blurred, (bw, bh), interpolation=cv2.INTER_LINEAR)

        tint_arr = np.full_like(frosted, tint, dtype=np.uint8)
        glass = cv2.addWeighted(frosted, 1.0 - alpha, tint_arr, alpha, 0)

        out = bg_rgb.copy()
        mask_pil = Image.new("L", (bw, bh), 0)
        ImageDraw.Draw(mask_pil).rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=radius, fill=255)
        mask_arr = (np.array(mask_pil, dtype=np.float32) / 255.0)[:, :, None]
        out[y1:y2, x1:x2] = (glass * mask_arr + out[y1:y2, x1:x2] * (1.0 - mask_arr)).astype(np.uint8)
        return Image.fromarray(out).convert("RGBA")

    def draw_broadcast_wipe(frame_rgba: Image.Image, mode: str, progress: float):
        """ترنزیشن پرده اریب قرمز و ذغالی سبک شبکه‌های خبری (مدل ۲)."""
        d = ImageDraw.Draw(frame_rgba)
        slant = 260
        stripe_w = 88
        charcoal = (18, 20, 25, 255)
        crimson = (204, 18, 28, 255)

        if mode == "in":
            # ورود پرده از راست به چپ در پایان اسلاید
            lead_x = int(1380 - 1500 * (progress ** 1.35))
            d.polygon([
                (lead_x, 0), (lead_x + stripe_w, 0),
                (lead_x + stripe_w - slant, h), (lead_x - slant, h)
            ], fill=crimson)
            d.polygon([
                (lead_x + stripe_w, 0), (w + 400, 0),
                (w + 400, h), (lead_x + stripe_w - slant, h)
            ], fill=charcoal)
        else:
            # خروج پرده به سمت چپ در ابتدای اسلاید جدید
            trail_x = int(1460 - 1540 * (progress ** 0.78))
            d.polygon([
                (-400, 0), (trail_x - stripe_w, 0),
                (trail_x - stripe_w - slant, h), (-400, h)
            ], fill=charcoal)
            d.polygon([
                (trail_x - stripe_w, 0), (trail_x, 0),
                (trail_x - slant, h), (trail_x - stripe_w - slant, h)
            ], fill=crimson)

    # لایه ثابت گرادیانت تیره بالا و پایین برای خوانایی روی عکس‌های تمام‌صفحه (مدل ۱)
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for y in range(340):
        vd.line([(0, y), (w, y)], fill=(10, 12, 18, int(215 * (1.0 - y / 340.0))))
    for y in range(980, h):
        r = (y - 980) / (h - 980)
        vd.line([(0, y), (w, y)], fill=(10, 12, 18, int(242 * (r ** 1.25))))

    # بارگذاری لوگوی دروازه قرآن (logo.png)
    logo_img = None
    logo_path = find_repo_logo()
    if logo_path:
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
        except Exception:
            logo_img = None

    jnow = jdatetime.datetime.fromgregorian(datetime=get_tehran_now())
    date_str = to_persian_digits(f"{JALALI_WEEKDAYS[jnow.weekday()]} {jnow.day} {JALALI_MONTHS[jnow.month]} {jnow.year}")

    # --- ۱. آماده‌سازی گرافیک مقدمه (گرادیان تاریک + کارت شیشه‌ای) ---
    intro_box = (66, 610, w - 66, 1270)
    intro_ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(intro_ov)
    idraw.rounded_rectangle(intro_box, radius=36, outline=(255, 255, 255, 68), width=3)
    idraw.rectangle([(w - 92, 665), (w - 80, 1215)], fill=(204, 18, 28, 255))
    if logo_img:
        lg = logo_img.copy()
        lg.thumbnail((170, 130), Image.Resampling.LANCZOS)
        intro_ov.alpha_composite(lg, ((w - lg.width) // 2, 360))
    else:
        draw_quran_gate_fallback(idraw, (w - 130) // 2, 360, 130)
    # برچسب اریب قرمز بالای کارت مقدمه
    idraw.polygon([(340, 566), (760, 566), (732, 636), (312, 636)], fill=(204, 18, 28, 255))
    draw_rtl_text(idraw, (536, 578), "بسته خبری روزانه", load_font("bold", 38), (255, 255, 255, 255), align="center", shadow=False)
    draw_rtl_text(idraw, (w // 2, 720), "۶۰ ثانیه با مهم ترین اخبار امروز", load_font("display", 90), (255, 255, 255, 255), align="center")
    draw_rtl_text(idraw, (w // 2, 875), date_str, load_font("bold", 40), (210, 218, 232, 255), align="center", shadow=False)
    idraw.line([(210, 965), (w - 210, 965)], fill=(255, 255, 255, 55), width=2)
    draw_rtl_text(
        idraw, (w // 2, 1015),
        f" {to_persian_digits(str(n_news))} مهم‌ترین خبرهای امروز",
        load_font("bold", 38), (242, 200, 68, 255), align="center", shadow=False
    )
    draw_rtl_text(idraw, (w // 2, 1140), "@ShirazLastNews", load_font("bold", 36), (205, 212, 224, 255), align="center", shadow=False, is_rtl=False)

    # --- ۲. آماده‌سازی اسلایدهای خبرها (عکس تمام‌صفحه + کارت شیشه‌ای تیتر + HUD برودکست) ---
    news_slides = []
    card_box_base = (52, 1235, w - 52, 1655)
    cb_w = card_box_base[2] - card_box_base[0]
    cb_h = card_box_base[3] - card_box_base[1]

    for idx, item in enumerate(selected, start=1):
        photo_p = item.get("photo")
        has_photo = bool(photo_p and os.path.exists(photo_p))
        photo_arr = None
        if has_photo:
            photo_arr = np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1220, 2168), dtype=np.uint8)

        tag_txt = strip_emojis_for_font(item.get("tag", "مهم‌ترین خبرها")) or "مهم‌ترین خبر"
        if "فوری" in tag_txt or "حادثه" in tag_txt:
            accent_c = (214, 22, 34)
        elif "ورزش" in tag_txt:
            accent_c = (22, 163, 74)
        elif "اقتصاد" in tag_txt:
            accent_c = (217, 152, 16)
        else:
            accent_c = (204, 18, 28)

        # رندر محتوای کارت شیشه‌ای در یک لایه مستقل تا به‌صورت نرم از پایین بالا بیاید
        card_content = Image.new("RGBA", (cb_w, cb_h), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card_content)
        cd.rounded_rectangle([(0, 0), (cb_w - 1, cb_h - 1)], radius=34, outline=(255, 255, 255, 78), width=3)
        # خط عمودی رنگی هویت برند سمت راست کارت
        cd.rounded_rectangle([(cb_w - 28, 34), (cb_w - 14, cb_h - 34)], radius=7, fill=accent_c + (255,))
        # برچسب اریب دسته خبر داخل بالای کارت
        cd.polygon([(cb_w - 310, 26), (cb_w - 46, 26), (cb_w - 46, 82), (cb_w - 332, 82)], fill=accent_c + (255,))
        draw_centered_block_in_box(
            cd, (cb_w - 312, 30, cb_w - 50, 78), tag_txt, "bold", (255, 255, 255, 255),
            max_size=30, min_size=20, max_lines=1, align="center", pad_x=10, pad_y=2
        )
        # ساعت ثبت خبر در سمت چپ بالای کارت
        t_lbl = to_persian_digits(item.get("time", ""))
        if t_lbl:
            draw_rtl_text(cd, (36, 40), f"ساعت {t_lbl}", load_font("regular", 26), (195, 205, 220, 220), align="left", shadow=False)

        # تیتر اصلی درشت و خوانا
        draw_centered_block_in_box(
            cd, (34, 98, cb_w - 50, cb_h - 32),
            item["headline"], "display", (255, 255, 255, 255),
            max_size=62, min_size=32, max_lines=3, align="right", pad_x=12, pad_y=6, shadow=True
        )

        # هدر برودکست بالا (لوگو + شمارنده ۰۱ / ۰۶)
        hud_top = Image.new("RGBA", (w, 260), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hud_top)
        if logo_img:
            lg = logo_img.copy()
            lg.thumbnail((110, 82), Image.Resampling.LANCZOS)
            hud_top.alpha_composite(lg, (52, 102))
        else:
            draw_quran_gate_fallback(hd, 52, 102, 78)
        draw_rtl_text(hd, (172, 128), "@ShirazLastNews", load_font("bold", 28), (235, 240, 248, 220), align="left", shadow=True, is_rtl=False)

        cnt_str = to_persian_digits(f"{idx:02d} / {n_news:02d}")
        hd.rounded_rectangle([(w - 260, 106), (w - 48, 174)], radius=34, fill=(16, 18, 24, 210), outline=(255, 255, 255, 75), width=2)
        hd.ellipse([(w - 92, 128), (w - 68, 152)], fill=accent_c + (255,))
        draw_rtl_text(hd, (w - 175, 120), cnt_str, load_font("bold", 34), (255, 255, 255, 255), align="center", shadow=False, is_rtl=False)

        news_slides.append({
            "photo_arr": photo_arr,
            "accent": accent_c,
            "card_content": card_content,
            "hud_top": hud_top,
            "dur": 4.8,
        })

    # --- ۳. آماده‌سازی گرافیک پایان (گرادیان تاریک + کارت شیشه‌ای فالو) ---
    outro_box = (72, 690, w - 72, 1210)
    outro_ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(outro_ov)
    od.rounded_rectangle(outro_box, radius=36, outline=(255, 255, 255, 72), width=3)
    draw_rtl_text(od, (w // 2, 755), BRAND_TITLE_FA, load_font("display", 82), (255, 255, 255, 255), align="center")
    draw_rtl_text(od, (w // 2, 895), "برای پیگیری لحظه‌ای اخبار ایران و شیراز فالو کنید", load_font("bold", 36), (210, 218, 232, 255), align="center", shadow=False)
    od.rounded_rectangle([(255, 1005), (825, 1115)], radius=24, fill=(204, 18, 28, 255))
    draw_rtl_text(od, (w // 2, 1034), "@ShirazLastNews", load_font("bold", 46), (255, 255, 255, 255), align="center", shadow=False, is_rtl=False)

    # انتخاب فایل صوتی اختصاصی از مخزن (daily.mp3 یا news.mp3)
    total_sec = 2.4 + sum(s["dur"] for s in news_slides) + 2.3
    audio_path = ""
    for cand in ("daily.mp3", "sounds/daily.mp3", "news.mp3", "sounds/news.mp3"):
        if os.path.exists(cand) and os.path.getsize(cand) > 4000:
            audio_path = cand
            break
    if not audio_path:
        audio_path = get_audio_track(work_dir, total_sec, mode="news")

    out_mp4 = os.path.join(TMP_ROOT, f"broadcast_daily_{int(time.time()*1000)}.mp4")

    def draw_progress_bars(frame_rgba: Image.Image, current_idx: int, frac: float):
        """نوارهای پیشرفت ۶ تایی بالای صفحه (مدل ۱)."""
        pd = ImageDraw.Draw(frame_rgba)
        margin_x, gap, bar_y, bar_h = 46, 12, 58, 9
        seg_w = (w - margin_x * 2 - gap * (n_news - 1)) / max(1, n_news)
        for s in range(n_news):
            sx1 = int(margin_x + s * (seg_w + gap))
            sx2 = int(sx1 + seg_w)
            pd.rounded_rectangle([(sx1, bar_y), (sx2, bar_y + bar_h)], radius=5, fill=(255, 255, 255, 72))
            if s < current_idx:
                pd.rounded_rectangle([(sx1, bar_y), (sx2, bar_y + bar_h)], radius=5, fill=(255, 255, 255, 238))
            elif s == current_idx:
                fw = max(10, int(seg_w * max(0.0, min(1.0, frac))))
                pd.rounded_rectangle([(sx1, bar_y), (sx1 + fw, bar_y + bar_h)], radius=5, fill=(220, 28, 38, 255))

    def frame_gen():
        global_t = 0.0
        wipe_dur = 0.26

        # ۱. فریم‌های مقدمه (2.4 ثانیه)
        n_intro = int(2.4 * fps)
        for i in range(n_intro):
            lt = i / fps
            global_t += 1.0 / fps
            bg = make_dark_gradient_bg(global_t, (204, 18, 28))
            dy = int(75 * ((1.0 - min(1.0, lt / 0.55)) ** 3))
            shifted_box = (intro_box[0], intro_box[1] + dy, intro_box[2], intro_box[3] + dy)
            frame = apply_glass_box(bg, shifted_box, radius=36, alpha=0.58)
            frame.alpha_composite(intro_ov, (0, dy))
            if lt > (2.4 - wipe_dur):
                draw_broadcast_wipe(frame, "in", (lt - (2.4 - wipe_dur)) / wipe_dur)
            yield np.array(frame.convert("RGB"), dtype=np.uint8)

        # ۲. فریم‌های خبرها
        for s_idx, sl in enumerate(news_slides):
            dur = sl["dur"]
            n_f = int(dur * fps)
            photo_arr = sl["photo_arr"]
            for i in range(n_f):
                lt = i / fps
                global_t += 1.0 / fps

                if photo_arr is not None:
                    ah, aw = photo_arr.shape[:2]
                    z = 1.0 + 0.09 * (lt / dur)
                    cw, ch = int(aw / z), int(ah / z)
                    x0, y0 = (aw - cw) // 2, (ah - ch) // 2
                    bg_rgb = cv2.resize(photo_arr[y0:y0 + ch, x0:x0 + cw], (w, h), interpolation=cv2.INTER_LINEAR)
                else:
                    bg_rgb = make_dark_gradient_bg(global_t, sl["accent"])

                # اعمال سایه سینمایی بالا و پایین روی عکس
                base_rgba = Image.fromarray(bg_rgb).convert("RGBA")
                base_rgba.alpha_composite(vignette)
                bg_darkened = np.array(base_rgba.convert("RGB"), dtype=np.uint8)

                # حرکت نرم بالا آمدن کارت شیشه‌ای تیتر در 0.55 ثانیه اول
                card_prog = min(1.0, max(0.0, (lt - 0.12) / 0.55))
                dy = int(115 * ((1.0 - card_prog) ** 3))
                cur_box = (
                    card_box_base[0], card_box_base[1] + dy,
                    card_box_base[2], card_box_base[3] + dy,
                )
                frame = apply_glass_box(bg_darkened, cur_box, radius=34, alpha=0.60)
                frame.alpha_composite(sl["card_content"], (cur_box[0], cur_box[1]))
                frame.alpha_composite(sl["hud_top"], (0, 0))
                draw_progress_bars(frame, s_idx, lt / dur)

                # فوتر باریک برند پایین صفحه
                draw_rtl_text(
                    ImageDraw.Draw(frame), (w // 2, 1790),
                    "بسته خبری روزانه  |  آخرین خبرهای ایران و شیراز",
                    load_font("regular", 26), (200, 208, 222, 200), align="center", shadow=False
                )

                # ترنزیشن اریب قرمز در ابتدا و انتهای اسلاید
                if lt < wipe_dur:
                    draw_broadcast_wipe(frame, "out", lt / wipe_dur)
                elif lt > (dur - wipe_dur):
                    draw_broadcast_wipe(frame, "in", (lt - (dur - wipe_dur)) / wipe_dur)

                yield np.array(frame.convert("RGB"), dtype=np.uint8)

        # ۳. فریم‌های پایان (2.3 ثانیه)
        n_out = int(2.3 * fps)
        for i in range(n_out):
            lt = i / fps
            global_t += 1.0 / fps
            bg = make_dark_gradient_bg(global_t, (204, 18, 28))
            frame = apply_glass_box(bg, outro_box, radius=36, alpha=0.58)
            frame.alpha_composite(outro_ov)
            if lt < wipe_dur:
                draw_broadcast_wipe(frame, "out", lt / wipe_dur)
            yield np.array(frame.convert("RGB"), dtype=np.uint8)

    pipe_frames_to_mp4(frame_gen(), out_mp4, audio_path, fps=fps)
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

    circle_r = 215
    cx, cy = w // 2, 540
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
        ov_p = render_reel_frame_overlay(repo_frame, badge or "گزارش صوتی", headline, subtext, work_dir)
        bg.alpha_composite(Image.open(ov_p).convert("RGBA"))
    else:
        draw_rtl_text(draw, (w // 2, 145), "گزارش صوتی اختصاصی", load_font("bold", 40), theme["accent"] + (255,), align="center")
        draw_rtl_text(draw, (w // 2, 210), BRAND_TITLE_FA, load_font("display", 54), theme["text"] + (255,), align="center")
        draw_centered_block_in_box(draw, (70, 820, w - 70, 1170), headline, "display", theme["text"] + (255,), max_size=68, min_size=30, max_lines=3)
        draw.rounded_rectangle([(60, 1210), (w - 60, 1490)], radius=24, fill=(0, 0, 0, 100), outline=theme["accent"] + (160,), width=3)
        draw_rtl_text(draw, (w // 2, 1630), BRAND_HANDLE, load_font("bold", 38), theme["accent"] + (255,), align="center", is_rtl=False)

    bg_path = os.path.join(work_dir, "audio_bg.png")
    bg.convert("RGB").save(bg_path)

    out_mp4 = os.path.join(TMP_ROOT, f"audiogram_{int(time.time()*1000)}.mp4")
    wave_color = theme["wave_hex"]
    run_ffmpeg([
        "ffmpeg", "-y", "-loop", "1", "-i", bg_path, "-i", audio_path,
        "-filter_complex",
        f"[1:a]showwaves=s=920x190:mode=cline:rate=25:colors={wave_color}[w];"
        f"[0:v][w]overlay=(W-w)/2:{wave_y}:shortest=1,format=yuv420p[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out_mp4
    ])
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۶. استودیو تدوین ویدئو (با پر کردن خودکار ۳ باکس قاب ریلز + قلاب شوک + زیرنویس متحرک) ====================
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
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(cascade_path)
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
        xs = []
        for i in range(1, 10):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i / 10.0)))
            ok, frame = cap.read()
            if not ok:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, 1.15, 5, minSize=(45, 45))
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


def build_hook_intro_clip_sync(work_dir: str, badge: str, headline: str, with_audio: bool = True) -> str:
    """قلاب ۱.۳ ثانیه‌ای شوک در ابتدای ریلز (مورد ۵)."""
    theme = THEMES.get(CONFIG["theme"], THEMES["navy"])
    im = Image.new("RGB", (1080, 1920), (14, 10, 16))
    d = ImageDraw.Draw(im)
    d.rectangle([(0, 0), (1080, 28)], fill=(220, 38, 38))
    d.rectangle([(0, 1892), (1080, 1920)], fill=(250, 204, 21))
    d.rounded_rectangle([(310, 620), (770, 715)], radius=16, fill=(220, 38, 38))
    draw_rtl_text(d, (540, 636), badge or "خبر فوری", load_font("display", 54), (255, 255, 255), align="center", shadow=False)
    draw_centered_block_in_box(d, (70, 760, 1010, 1180), headline, "display", (255, 255, 255), max_size=76, min_size=36, max_lines=3, shadow=True)
    draw_rtl_text(d, (540, 1340), BRAND_HANDLE, load_font("bold", 42), theme["accent"], align="center", is_rtl=False)

    img_p = os.path.join(work_dir, "hook.jpg")
    im.save(img_p, quality=92)
    mp4_p = os.path.join(work_dir, "hook.mp4")

    cmd = ["ffmpeg", "-y", "-loop", "1", "-t", "1.3", "-i", img_p]
    if with_audio:
        wav_p = generate_emergency_audio_wav(os.path.join(work_dir, "hook.wav"), 1.3, mode="incident")
        cmd += ["-i", wav_p]
    cmd += ["-vf", "scale=1080:1920,fps=25,format=yuv420p,setsar=1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]
    if with_audio:
        cmd += ["-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k"]
    cmd += ["-t", "1.3", mp4_p]
    run_ffmpeg(cmd)
    return mp4_p


def process_video_studio_sync(video_path: str, badge: str, headline: str, subtext: str) -> tuple:
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)
    info = probe_video_info(video_path)
    w, h = info["width"], info["height"]
    has_audio = info["has_audio"]
    dur = info["duration"]

    applied = []
    use_antidup = CONFIG["video_antidup"]
    use_facetrack = CONFIG["video_facetrack"]
    use_brand = CONFIG["video_brand"]
    use_ticker = CONFIG.get("video_ticker", True)
    use_hook = CONFIG.get("video_hook_intro", True)
    repo_frame = find_repo_reel_frame() if CONFIG["use_repo_frame"] else ""

    if use_facetrack and w > h:
        face_x = detect_face_center_x(video_path)
        if face_x >= 0:
            crop_w = min(w, max(16, int(h * 9 / 16)))
            crop_x = max(0, min(w - crop_w, face_x - crop_w // 2))
            v_chain = f"[0:v]crop={crop_w}:{h}:{crop_x}:0,scale=1080:1920:flags=lanczos"
            applied.append("ردیابی چهره ۹:۱۶ ✅")
        else:
            v_chain = (
                "[0:v]split[orig][bg];"
                "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[b];"
                "[orig]scale=1080:-2[f];"
                "[b][f]overlay=(W-w)/2:(H-h)/2"
            )
            applied.append("تبدیل ۹:۱۶ با پس‌زمینه تار ✅")
    else:
        v_chain = (
            "[0:v]split[orig][bg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[b];"
            "[orig]scale=1080:1920:force_original_aspect_ratio=decrease[f];"
            "[b][f]overlay=(W-w)/2:(H-h)/2"
        )

    if use_antidup:
        v_chain += ",scale=1112:1978,crop=1080:1920,eq=contrast=1.02:saturation=1.03:brightness=0.008,setpts=PTS/1.015"
        applied.append("اصالت‌سازی و حذف متادیتا ✅")

    v_chain += ",fps=25,setsar=1,format=rgba[cur0]"
    cur_label = "cur0"
    inputs = ["-i", video_path]
    inp_idx = 1

    # پر کردن خودکار هر ۳ باکس قاب reel_frame.png و قرار دادن روی ویدئو
    if repo_frame:
        filled_fr = render_reel_frame_overlay(repo_frame, badge, headline, subtext, work_dir)
        inputs += ["-loop", "1", "-i", filled_fr]
        v_chain += f";[{cur_label}][{inp_idx}:v]overlay=0:0:shortest=1[cur{inp_idx}]"
        cur_label = f"cur{inp_idx}"
        inp_idx += 1
        applied.append("قاب ۳ باکسه ریلز با متن خودکار ✅")

    # نوار زیرنویس متحرک شبکه خبر در پایین ویدئو (مورد ۷ - بدون کاما در فرمول)
    if use_ticker and headline:
        t_strip = build_scrolling_ticker_strip(f"{headline} — {subtext}", dur + 2.0, bg_color=(185, 28, 28, 240), height=68)
        t_path = os.path.join(work_dir, "ticker.png")
        t_strip.save(t_path, format="PNG")
        inputs += ["-loop", "1", "-i", t_path]
        v_chain += f";[{cur_label}][{inp_idx}:v]overlay=x='-w+1080+165*t':y=1795:shortest=1[cur{inp_idx}]"
        cur_label = f"cur{inp_idx}"
        inp_idx += 1
        applied.append("نوار زیرنویس متحرک شبکه خبر ✅")

    v_chain += f";[{cur_label}]format=yuv420p[vout]"

    main_processed = os.path.join(work_dir, "main_proc.mp4")
    cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", v_chain, "-map", "[vout]"]
    if has_audio:
        if use_antidup:
            cmd += ["-filter:a", "atempo=1.015"]
        cmd += ["-map", "0:a", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k"]
    cmd += ["-map_metadata", "-1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-movflags", "+faststart", main_processed]
    run_ffmpeg(cmd)

    # اتصال قلاب ۱.۳ ثانیه‌ای شوک در ابتدا و اند-اسکرین ۲.۲ ثانیه‌ای در انتها
    segments = []
    if use_hook:
        segments.append(build_hook_intro_clip_sync(work_dir, badge, headline, with_audio=has_audio))
        applied.append("قلاب شوک اول ویدئو (۱.۳ ثانیه) ✅")
    segments.append(main_processed)
    if use_brand:
        segments.append(build_endscreen_clip_sync(work_dir, duration=2.2, with_silent_audio=has_audio))
        applied.append("اند-اسکرین دعوت به فالو ✅")

    out_mp4 = os.path.join(TMP_ROOT, f"studio_vid_{int(time.time()*1000)}.mp4")
    if len(segments) > 1:
        c_cmd = ["ffmpeg", "-y"]
        for s in segments:
            c_cmd += ["-i", s]
        n = len(segments)
        if has_audio:
            streams = "".join(f"[{k}:v][{k}:a]" for k in range(n))
            c_cmd += ["-filter_complex", f"{streams}concat=n={n}:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k"]
        else:
            streams = "".join(f"[{k}:v]" for k in range(n))
            c_cmd += ["-filter_complex", f"{streams}concat=n={n}:v=1:a=0[v]", "-map", "[v]"]
        c_cmd += ["-map_metadata", "-1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-movflags", "+faststart", out_mp4]
        run_ffmpeg(c_cmd)
    else:
        shutil.copy(main_processed, out_mp4)

    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4, applied


# ==================== ۷. حذف واترمارک و لوگوی خبرگزاری‌ها از ۴ گوشه (مورد ۹) ====================
def calc_corner_rect(w: int, h: int, corner: str) -> tuple:
    rw = max(60, int(w * 0.24))
    rh = max(45, int(h * 0.12))
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
    x = max(2, min(w - rw - 2, x))
    y = max(2, min(h - rh - 2, y))
    out_mp4 = os.path.join(TMP_ROOT, f"clean_logo_{int(time.time()*1000)}.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"delogo=x={x}:y={y}:w={rw}:h={rh}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "copy", "-map_metadata", "-1", "-movflags", "+faststart",
        out_mp4,
    ]
    run_ffmpeg(cmd)
    return out_mp4


# ==================== ۸. کارت مناسبت‌نگار روزانه ====================
async def build_daily_occasion_card(session: aiohttp.ClientSession) -> tuple:
    jnow = jdatetime.datetime.fromgregorian(datetime=get_tehran_now())
    wd = JALALI_WEEKDAYS[jnow.weekday()]
    day_str = to_persian_digits(str(jnow.day))
    month_str = JALALI_MONTHS[jnow.month]
    year_str = to_persian_digits(str(jnow.year))
    full_date = f"{wd} {day_str} {month_str} {year_str}"

    occasion = SHAMSI_OCCASIONS.get((jnow.month, jnow.day), "")
    if not occasion and GEMINI_API_KEY:
        p = (
            f"امروز {full_date} هجری شمسی است. "
            "فقط در یک جمله بسیار کوتاه و بدون ایموجی (حداکثر ۱۰ کلمه) مهم‌ترین مناسبت رسمی یا فرهنگی امروز در ایران یا شیراز را بنویس "
            "(اگر مناسبت خاصی نیست، یک جمله کوتاه و باوقار صبح‌بخیر شیراز بنویس). بدون توضیح اضافه."
        )
        occasion = await gemini_generate(session, p)
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

        cx, cy = w // 2, 740
        d.ellipse([(cx - 210, cy - 210), (cx + 210, cy + 210)], fill=theme["accent"])
        draw_rtl_text(d, (cx, cy - 115), day_str, load_font("display", 210), theme["bg"], align="center", shadow=False)
        draw_rtl_text(d, (w // 2, 1020), f"{wd}  |  {month_str} {year_str}", load_font("display", 72), theme["text"], align="center")

        d.line([(200, 1150), (w - 200, 1150)], fill=theme["accent"], width=4)
        draw_centered_block_in_box(d, (110, 1190, w - 110, 1520), occasion, "bold", theme["subtext"], max_size=46, min_size=28, max_lines=3, align="center")
        draw_rtl_text(d, (w // 2, 1620), BRAND_HANDLE, load_font("bold", 42), theme["accent"], align="center", is_rtl=False)

        out = os.path.join(TMP_ROOT, f"occasion_{int(time.time()*1000)}.jpg")
        im.save(out, quality=94)
        return out

    card_path = await asyncio.to_thread(draw_card)
    caption = f"📅 {full_date}\n\n{strip_emojis_for_font(occasion)}\n\n🔔 {BRAND_HANDLE}"
    return card_path, caption
    # ==================== ارسال کپشن + سپر ضدشدوبن ====================
async def send_caption_with_shield(session: aiohttp.ClientSession, chat_id: str, caption: str):
    LAST_CAPTION[chat_id] = caption
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
    await send_message(session, chat_id, caption, kb_main_menu())


# ==================== اجرای کارهای ویدئویی و پردازشی در پس‌زمینه ====================
async def run_daily60_job(session: aiohttp.ClientSession, chat_id: str):
    try:
        items_copy = list(DAILY_ITEMS[-8:])
        mp4 = await asyncio.to_thread(build_daily_summary_reel_sync, items_copy)
        await send_video_file(session, chat_id, mp4, caption=f"🎨 ریلز جمع‌بندی موشن‌گرافیک پاپ‌آرت ({to_persian_digits(str(len(items_copy)))} خبر) آماده انتشار است!")
        headlines_text = "\n".join(f"- {it['headline']}" for it in items_copy)
        cap = await generate_editorial_caption(session, f"جمع‌بندی مهم‌ترین اخبار امروز شیراز و استان فارس:\n{headlines_text}")
        await send_caption_with_shield(session, chat_id, cap)
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در ساخت ریلز پاپ‌آرت:\n{e}", kb_main_menu())


async def run_incident_job(session: aiohttp.ClientSession, chat_id: str, photo_path: str, news_text: str):
    try:
        # ابتدا کپشن تولید می‌شود تا حتی اگر متن کوتاه یا خالی بود، تیتر و زیرتیتر کامل داشته باشیم
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
        await send_video_file(session, chat_id, mp4, caption="🚨 ریلز فوری و حادثه‌ای (شوک + آژیر + تایپ زنده + زیرنویس) آماده انتشار است.")
        await send_caption_with_shield(session, chat_id, cap)
        add_to_daily_items(hl, photo_path, tag="خبر فوری")
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در تولید ریلز حادثه‌ای:\n{e}", kb_main_menu())


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
        mp4 = await asyncio.to_thread(
            build_map_zoom_reel_sync, wide_map, close_map, photo_path, loc_name, badge, hl, sub
        )
        await send_video_file(session, chat_id, mp4, caption=f"🗺️ ریلز زوم دومرحله‌ای روی نقشه «{loc_name}» آماده است.")
        await send_caption_with_shield(session, chat_id, cap)
        add_to_daily_items(hl, photo_path, tag=loc_name)
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در ساخت ریلز نقشه:\n{e}", kb_main_menu())


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
        await send_caption_with_shield(session, chat_id, cap)
        add_to_daily_items(hl, speaker_photo, tag="صوتی")
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در ساخت ریلز صوتی:\n{e}", kb_main_menu())


async def run_video_studio_job(session: aiohttp.ClientSession, chat_id: str, vid_path: str, user_caption: str):
    try:
        # ابتدا کپشن از روی خود فیلم و متن کاربر تولید می‌شود تا هر ۳ باکس قاب ریلز دقیق پر شوند
        cap = await generate_editorial_caption(session, news_text=user_caption, media_path=vid_path, mime_type="video/mp4")
        source_for_parts = user_caption if len(user_caption) >= 15 else cap
        badge, hl, sub = await extract_news_parts(session, source_for_parts)
        out_mp4, applied = await asyncio.to_thread(process_video_studio_sync, vid_path, badge, hl, sub)
        summary = (
            "🎞️ ویدئو با موفقیت تدوین شد:\n"
            + "\n".join(f"• {a}" for a in applied)
            + f"\n\n🏷️ برچسب باکس قرمز: {badge}\n📝 تیتر باکس میانی: {hl}"
        )
        await send_video_file(session, chat_id, out_mp4, caption=summary)
        await send_caption_with_shield(session, chat_id, cap)
        add_to_daily_items(hl, None, tag=badge)
        if os.path.exists(out_mp4):
            os.remove(out_mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در پردازش ویدئو:\n{e}", kb_main_menu())


async def run_clean_logo_job(session: aiohttp.ClientSession, chat_id: str, media_path: str, is_video: bool, corner: str):
    corner_names = {
        "tr": "بالا راست",
        "tl": "بالا چپ",
        "br": "پایین راست",
        "bl": "پایین چپ",
    }
    cname = corner_names.get(corner, corner)
    try:
        if is_video:
            out_p = await asyncio.to_thread(clean_corner_logo_video_sync, media_path, corner)
            await send_video_file(session, chat_id, out_p, caption=f"🧹 لوگوی گوشه «{cname}» از روی ویدئو پاک‌سازی شد.", reply_markup=kb_main_menu())
        else:
            out_p = await asyncio.to_thread(clean_corner_logo_photo_sync, media_path, corner)
            await send_photo_file(session, chat_id, out_p, caption=f"🧹 لوگوی گوشه «{cname}» از روی عکس پاک‌سازی شد.", reply_markup=kb_main_menu())
        if os.path.exists(out_p):
            os.remove(out_p)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در حذف واترمارک:\n{e}", kb_main_menu())


# ==================== مدیریت کامل دکمه‌های منوی ثابت پایین صفحه ====================
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

    # --- دکمه‌های عمومی شروع و بازگشت ---
    if is_pure_text and text in ("/start", "/menu", BTN_BACK, BTN_CANCEL, BTN_STATUS):
        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, build_status_text(), kb_main_menu())
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

    # --- دکمه‌های منوی اصلی ---
    if is_pure_text and text in (BTN_CARD_POST, BTN_CARD_STORY):
        fmt = "post" if text == BTN_CARD_POST else "story"
        fmt_fa = "پست (۴:۵)" if fmt == "post" else "استوری (۹:۱۶)"
        extra_note = ""
        if fmt == "story":
            sf = find_repo_story_frame()
            extra_note = f"\n📱 قالب فعال: {os.path.basename(sf)} ✅" if sf else "\n📱 قالب پیش‌فرض (برای قالب پیج فایل story_frame.png را آپلود کنید)"
        USER_STATE[chat_id] = {"mode": "card", "step": "wait_input", "fmt": fmt}
        await send_message(
            session,
            chat_id,
            f"🖼️ ساخت کارت {fmt_fa}{extra_note}\n\nعکس خبر را همراه با متن خبر بفرستید (یا فقط متن بفرستید):",
            kb_cancel(),
        )
        return

    if is_pure_text and text == BTN_INCIDENT:
        USER_STATE[chat_id] = {"mode": "incident", "step": "wait_input"}
        await send_message(
            session,
            chat_id,
            "🚨 ریلز فوری و حادثه‌ای (نسخه اضطراری)\n"
            "• قلاب ۱.۵ ثانیه‌ای شوک + لرزش دوربین\n"
            "• آژیر اورژانسی واقعی + چراغ گردان قرمز/آبی\n"
            "• تایپ زنده کلمه‌به‌کلمه تیتر + زیرنویس متحرک شبکه خبر\n\n"
            "عکس حادثه را همراه با متن خبر بفرستید:",
            kb_cancel(),
        )
        return

    if is_pure_text and text == BTN_CAPTION:
        USER_STATE[chat_id] = {"mode": "caption_active", "step": "wait_input"}
        await send_message(
            session,
            chat_id,
            f"✍️ کپشن‌نویس فعال ({BRAND_HANDLE})\n\n"
            "برای چه چیزی کپشن می‌خواهید؟ یکی از موارد زیر را مستقیم بفرستید:\n"
            "• 🎥 فیلم / ویدئو (تا ۲۰ مگابایت)\n"
            "• 🖼️ عکس (با یا بدون توضیح)\n"
            "• 🎙️ ویس یا فایل صوتی\n"
            "• 📝 متن خبر و نام منبع",
            kb_cancel(),
        )
        return

    if is_pure_text and text == BTN_MAP:
        USER_STATE[chat_id] = {"mode": "map_reel", "step": "wait_location", "data": {}}
        await send_message(
            session,
            chat_id,
            "🗺️ ریلز زوم دومرحله‌ای روی نقشه واقعی\n\n"
            "مرحله ۱ از ۲: نام محله در شیراز یا شهر استان فارس را بنویسید (مثلاً: معالی‌آباد، صدرا، بلوار چمران، مرودشت):",
            kb_cancel(),
        )
        return

    if is_pure_text and text == BTN_AUDIO:
        USER_STATE[chat_id] = {"mode": "audiogram", "step": "wait_audio", "data": {}}
        await send_message(
            session,
            chat_id,
            "🎙️ ریلز موج صوتی (Audiogram)\n\nمرحله ۱ از ۲: ویس یا فایل صوتی را بفرستید:",
            kb_cancel(),
        )
        return

    if is_pure_text and text == BTN_DAILY60:
        USER_STATE[chat_id] = {"mode": "daily_collect"}
        cnt = to_persian_digits(str(len(DAILY_ITEMS)))
        await send_message(
            session,
            chat_id,
            f"🎨 حالت ساخت ریلز جمع‌بندی پاپ‌آرت فعال شد!\n"
            f"📦 تعداد خبرهای فعلی در صف: {cnt} خبر\n\n"
            "حالا خبرها را (عکس+متن یا فقط متن) یکی‌یکی پشت‌سرهم بفرستید یا فوروارد کنید.\n"
            f"هر زمان همه خبرها را فرستادید، دکمه «{BTN_BUILD_POPART}» را از منوی پایین بزنید:",
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
        await send_message(
            session,
            chat_id,
            "🧹 صف جمع‌بندی کاملاً پاک شد (۰ خبر).\nخبر اول را بفرستید:",
            kb_daily_collect(),
        )
        return

    if is_pure_text and text == BTN_BUILD_POPART:
        if not DAILY_ITEMS:
            await send_message(session, chat_id, "⚠️ صف خالی است! ابتدا حداقل یک خبر بفرستید.", kb_daily_collect())
            return
        USER_STATE.pop(chat_id, None)
        await send_message(
            session,
            chat_id,
            f"🎨 در حال رندر ریلز موشن‌گرافیک پاپ‌آرت از {to_persian_digits(str(len(DAILY_ITEMS[-8:])))} خبر (حدود ۳۰ ثانیه)...",
            kb_main_menu(),
        )
        spawn_bg_task(run_daily60_job(session, chat_id))
        return

    if is_pure_text and text == BTN_VIDEO:
        USER_STATE[chat_id] = {"mode": "video_studio", "step": "wait_video"}
        r_fr = find_repo_reel_frame()
        fr_note = f"فعال ✅ ({os.path.basename(r_fr)}) — پر کردن خودکار ۳ باکس" if r_fr else "آپلود نشده (reel_frame.png)"
        await send_message(
            session,
            chat_id,
            "🎞️ استودیو تدوین هوشمند ویدئو\n\n"
            f"• قاب ریلز ۳ باکسه: {fr_note}\n"
            "• گزینه‌ها را از منوی پایین تنظیم کنید و سپس **ویدئوی خود را (ترجیحاً با متن خبر در کپشن)** بفرستید:",
            kb_video_studio(),
        )
        return

    if is_pure_text and text == BTN_CLEAN_LOGO:
        USER_STATE[chat_id] = {"mode": "clean_logo", "step": "wait_corner"}
        await send_message(
            session,
            chat_id,
            "🧹 حذف واترمارک و لوگوی خبرگزاری‌ها\n\n"
            "مرحله ۱ از ۲: لوگوی مزاحم در کدام گوشه عکس یا فیلم قرار دارد؟ از منوی پایین انتخاب کنید:",
            kb_logo_corners(),
        )
        return

    if is_pure_text and text == BTN_SHADOWBAN:
        USER_STATE[chat_id] = {"mode": "shadowban_check", "step": "wait_text"}
        await send_message(
            session,
            chat_id,
            "🛡️ سپر ضدشدوبن اینستاگرام\n\nمتن کپشن یا تیتر خود را بفرستید تا کلمات حساس بررسی شوند:",
            kb_cancel(),
        )
        return

    if is_pure_text and text == BTN_THEME:
        USER_STATE[chat_id] = {"mode": "theme_select"}
        cur = THEMES[CONFIG["theme"]]["name"]
        await send_message(
            session,
            chat_id,
            f"🎨 تغییر آنی تم گرافیکی\n\nتم فعال فعلی: {cur}\nتم جدید را از منوی پایین انتخاب کنید:",
            kb_theme_menu(),
        )
        return

    if is_pure_text and text == BTN_OCCASION:
        await send_message(session, chat_id, "📅 در حال طراحی کارت مناسبت امروز...")
        card_p, cap = await build_daily_occasion_card(session)
        await send_photo_file(session, chat_id, card_p, caption=cap, reply_markup=kb_main_menu())
        return

    # --- زیرمنوی انتخاب تم ---
    if is_pure_text:
        for tkey, tval in THEMES.items():
            if text == tval["btn"]:
                CONFIG["theme"] = tkey
                await save_config_to_pin(session)
                USER_STATE.pop(chat_id, None)
                await send_message(session, chat_id, f"✅ تم گرافیکی به «{tval['name']}» تغییر کرد.", kb_main_menu())
                return

    # --- زیرمنوی تنظیمات استودیو ویدئو ---
    if is_pure_text and text.startswith((
        "🖼️ قاب ریلز", "📱 قاب استوری", "⚡ قلاب شوک", "📰 زیرنویس متحرک",
        "🧬 اصالت‌سازی", "👤 ردیابی چهره", "🏷️ اند-اسکرین"
    )):
        if text.startswith("🖼️ قاب ریلز"):
            CONFIG["use_repo_frame"] = not CONFIG["use_repo_frame"]
        elif text.startswith("📱 قاب استوری"):
            CONFIG["use_story_frame"] = not CONFIG["use_story_frame"]
        elif text.startswith("⚡ قلاب شوک"):
            CONFIG["video_hook_intro"] = not CONFIG["video_hook_intro"]
        elif text.startswith("📰 زیرنویس متحرک"):
            CONFIG["video_ticker"] = not CONFIG["video_ticker"]
        elif text.startswith("🧬 اصالت‌سازی"):
            CONFIG["video_antidup"] = not CONFIG["video_antidup"]
        elif text.startswith("👤 ردیابی چهره"):
            CONFIG["video_facetrack"] = not CONFIG["video_facetrack"]
        elif text.startswith("🏷️ اند-اسکرین"):
            CONFIG["video_brand"] = not CONFIG["video_brand"]
        await save_config_to_pin(session)
        USER_STATE[chat_id] = {"mode": "video_studio", "step": "wait_video"}
        await send_message(session, chat_id, "✅ تنظیم ذخیره شد. حالا ویدئوی خود را (با متن خبر در کپشن) بفرستید:", kb_video_studio())
        return

    # --- پردازش ورودی‌های هر حالت ---
    state = USER_STATE.get(chat_id)
    if not state:
        await send_message(session, chat_id, build_status_text(), kb_main_menu())
        return

    mode = state.get("mode")

    if mode == "card":
        fmt = state["fmt"]
        USER_STATE.pop(chat_id, None)
        photo_path = ""
        if msg.get("photo"):
            photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg")
        if not photo_path and not text:
            await send_message(session, chat_id, "❌ لطفاً عکس یا متن خبر را بفرستید.", kb_main_menu())
            return

        await send_message(session, chat_id, "⏳ در حال طراحی کارت گرافیکی و نگارش کپشن ۶ بخشی...")
        cap = await generate_editorial_caption(
            session,
            news_text=text,
            media_path=photo_path or None,
            mime_type="image/jpeg" if photo_path else None,
        )
        source_for_parts = text if len(text) >= 15 else cap
        badge, hl, sub = await extract_news_parts(session, source_for_parts)
        src_name = extract_source_name(text) or extract_source_name(cap)
        card_p = await asyncio.to_thread(
            render_news_card_sync, photo_path, badge, hl, sub, fmt, CONFIG["theme"], src_name
        )
        await send_photo_file(session, chat_id, card_p, caption="🖼️ کارت آماده انتشار")
        await send_caption_with_shield(session, chat_id, cap)
        add_to_daily_items(hl, photo_path, tag=badge)
        return

    if mode == "daily_collect":
        photo_path = ""
        if msg.get("photo"):
            photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg")
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
            f"✅ خبر شماره {cnt} در صف جمع‌بندی پاپ‌آرت ثبت شد:\n«{raw_hl}»\n\n"
            f"خبر بعدی را بفرستید یا روی «{BTN_BUILD_POPART}» بزنید.",
            kb_daily_collect(),
        )
        return

    if mode == "incident":
        USER_STATE.pop(chat_id, None)
        photo_path = ""
        if msg.get("photo"):
            photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg")
        if not photo_path and not text:
            await send_message(session, chat_id, "❌ عکس و متن خبر حادثه‌ای را بفرستید.", kb_main_menu())
            return
        await send_message(session, chat_id, "🚨 در حال تدوین ریلز اضطراری حادثه‌ای (حدود ۲۵ تا ۴۰ ثانیه)...", kb_main_menu())
        spawn_bg_task(run_incident_job(session, chat_id, photo_path, text))
        return

    if mode == "caption_active":
        USER_STATE.pop(chat_id, None)
        media_path = None
        mime = None

        if msg.get("video"):
            vid = msg["video"]
            if vid.get("file_size", 0) > 19.5 * 1024 * 1024:
                await send_message(session, chat_id, "⚠️ حجم فیلم بیشتر از ۲۰ مگابایت است. نسخه کم‌حجم‌تر بفرستید.", kb_main_menu())
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
                await send_message(session, chat_id, "⚠️ حجم فایل صوتی بیشتر از ۲۰ مگابایت است.", kb_main_menu())
                return
            await send_message(session, chat_id, "🎙️ در حال شنیدن فایل صوتی و نگارش کپشن ۶ بخشی...")
            media_path = await download_tg_file(session, aud["file_id"], ".ogg")
            mime = aud.get("mime_type") or "audio/ogg"

        elif text:
            await send_message(session, chat_id, f"✍️ در حال نگارش کپشن ۶ بخشی دقیق {BRAND_HANDLE}...")
        else:
            await send_message(session, chat_id, "❌ لطفاً متن، عکس، ویس یا فیلم بفرستید.", kb_main_menu())
            return

        cap = await generate_editorial_caption(session, news_text=text, media_path=media_path, mime_type=mime)
        await send_caption_with_shield(session, chat_id, cap)
        first_hl = cap.splitlines()[0] if cap else text[:70]
        add_to_daily_items(first_hl, media_path if mime == "image/jpeg" else None, tag="خبر")
        return

    if mode == "map_reel":
        if state["step"] == "wait_location":
            if not text:
                await send_message(session, chat_id, "❌ نام محله یا شهر را به صورت متنی بفرستید:", kb_cancel())
                return
            state["data"]["location"] = text
            state["step"] = "wait_photo"
            await send_message(
                session,
                chat_id,
                f"📍 موقعیت ثبت شد: {text}\n\nمرحله ۲ از ۲: حالا عکس خبر را همراه با متن خبر بفرستید:",
                kb_cancel(),
            )
            return

        if state["step"] == "wait_photo":
            loc = state["data"]["location"]
            USER_STATE.pop(chat_id, None)
            photo_path = ""
            if msg.get("photo"):
                photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg")
            await send_message(session, chat_id, f"🗺️ در حال دریافت نقشه واقعی «{loc}» و ساخت ریلز زوم دومرحله‌ای...", kb_main_menu())
            spawn_bg_task(run_map_job(session, chat_id, loc, photo_path, text))
            return

    if mode == "audiogram":
        if state["step"] == "wait_audio":
            aud = msg.get("voice") or msg.get("audio")
            if not aud:
                await send_message(session, chat_id, "❌ لطفاً ویس یا فایل صوتی بفرستید:", kb_cancel())
                return
            if aud.get("file_size", 0) > 19.5 * 1024 * 1024:
                await send_message(session, chat_id, "⚠️ حجم فایل صوتی باید کمتر از ۲۰ مگابایت باشد.", kb_cancel())
                return
            state["data"]["audio"] = await download_tg_file(session, aud["file_id"], ".ogg")
            state["step"] = "wait_speaker"
            await send_message(
                session,
                chat_id,
                "مرحله ۲ از ۲: عکس گوینده را همراه با تیتر خبر در کپشن بفرستید (یا از منوی پایین «⏭️ بدون عکس گوینده» را بزنید):",
                kb_cancel([{"text": BTN_SKIP_PHOTO}]),
            )
            return

        if state["step"] == "wait_speaker":
            if is_pure_text and text == BTN_SKIP_PHOTO:
                state["step"] = "wait_title"
                await send_message(session, chat_id, "✏️ تیتر کوتاه خبر را بنویسید:", kb_cancel())
                return
            aud_path = state["data"]["audio"]
            sp_photo = ""
            if msg.get("photo"):
                sp_photo = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg")
            if not text:
                state["data"]["photo"] = sp_photo
                state["step"] = "wait_title"
                await send_message(session, chat_id, "✏️ حالا تیتر کوتاه خبر را بنویسید:", kb_cancel())
                return
            USER_STATE.pop(chat_id, None)
            await send_message(session, chat_id, "🎙️ در حال ساخت ریلز موج صوتی...", kb_main_menu())
            spawn_bg_task(run_audiogram_job(session, chat_id, aud_path, sp_photo, text))
            return

        if state["step"] == "wait_title":
            aud_path = state["data"]["audio"]
            sp_photo = state["data"].get("photo", "")
            USER_STATE.pop(chat_id, None)
            await send_message(session, chat_id, "🎙️ در حال ساخت ریلز موج صوتی...", kb_main_menu())
            spawn_bg_task(run_audiogram_job(session, chat_id, aud_path, sp_photo, text or BRAND_TITLE_FA))
            return

    if mode == "video_studio":
        vid = msg.get("video")
        if not vid:
            await send_message(session, chat_id, "❌ لطفاً یک فایل ویدئو (زیر ۲۰ مگابایت) بفرستید:", kb_video_studio())
            return
        if vid.get("file_size", 0) > 19.5 * 1024 * 1024:
            await send_message(session, chat_id, "⚠️ حجم ویدئو بالای ۲۰ مگابایت است. نسخه کم‌حجم‌تر بفرستید.", kb_video_studio())
            return
        USER_STATE.pop(chat_id, None)
        await send_message(session, chat_id, "🎞️ در حال تحلیل فیلم، پر کردن ۳ باکس قاب ریلز و تدوین هوشمند (۳۰ تا ۶۰ ثانیه)...", kb_main_menu())
        vid_path = await download_tg_file(session, vid["file_id"], ".mp4")
        spawn_bg_task(run_video_studio_job(session, chat_id, vid_path, text))
        return

    if mode == "clean_logo":
        corner_map = {
            BTN_CORNER_TR: "tr",
            BTN_CORNER_TL: "tl",
            BTN_CORNER_BR: "br",
            BTN_CORNER_BL: "bl",
        }
        if state["step"] == "wait_corner":
            if is_pure_text and text in corner_map:
                state["corner"] = corner_map[text]
                state["step"] = "wait_media"
                await send_message(
                    session,
                    chat_id,
                    f"✅ موقعیت لوگو ثبت شد: {text}\n\nمرحله ۲ از ۲: حالا عکس یا فیلم (زیر ۲۰ مگابایت) را بفرستید:",
                    kb_cancel(),
                )
                return
            await send_message(session, chat_id, "❌ یکی از ۴ گوشه را از منوی پایین انتخاب کنید:", kb_logo_corners())
            return

        if state["step"] == "wait_media":
            corner = state["corner"]
            if msg.get("video"):
                vid = msg["video"]
                if vid.get("file_size", 0) > 19.5 * 1024 * 1024:
                    await send_message(session, chat_id, "⚠️ حجم فیلم باید کمتر از ۲۰ مگابایت باشد.", kb_cancel())
                    return
                USER_STATE.pop(chat_id, None)
                await send_message(session, chat_id, "🧹 در حال حذف واترمارک از روی ویدئو...", kb_main_menu())
                m_path = await download_tg_file(session, vid["file_id"], ".mp4")
                spawn_bg_task(run_clean_logo_job(session, chat_id, m_path, True, corner))
                return
            if msg.get("photo"):
                USER_STATE.pop(chat_id, None)
                await send_message(session, chat_id, "🧹 در حال حذف واترمارک از روی عکس...", kb_main_menu())
                m_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg")
                spawn_bg_task(run_clean_logo_job(session, chat_id, m_path, False, corner))
                return
            await send_message(session, chat_id, "❌ لطفاً عکس یا ویدئو بفرستید:", kb_cancel())
            return

    if mode == "shadowban_check":
        USER_STATE.pop(chat_id, None)
        if not text:
            await send_message(session, chat_id, "❌ متن را بفرستید.", kb_main_menu())
            return
        LAST_CAPTION[chat_id] = text
        hits = check_shadowban_words(text)
        if not hits:
            await send_message(session, chat_id, "✅ عالی! هیچ کلمه پرریسک و محدودیت‌زایی در متن شما پیدا نشد.", kb_main_menu())
        else:
            lines = ["⚠️ کلمات حساس شناسایی‌شده در متن:"]
            for w, alt in hits:
                lines.append(f"• «{w}» ← معادل ایمن: {alt}")
            lines.append("\nبرای دریافت نسخه اصلاح‌شده، دکمه «✨ بازنویسی ایمن آخرین کپشن» را از منوی پایین بزنید.")
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
                {"command": "start", "description": "باز کردن منوی اصلی استودیو"},
                {"command": "menu", "description": "نمایش دکمه‌های منوی پایین"},
            ]
        })
        print(f"Studio Bot started at {get_tehran_now().strftime('%H:%M')} Tehran | RAQM={HAS_RAQM}")

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
                params = {
                    "offset": offset,
                    "timeout": 25,
                    "allowed_updates": '["message"]',
                }
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
