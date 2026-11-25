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
import struct
import subprocess
import tempfile
import time
import wave
from datetime import datetime, timedelta, timezone

# نصب خودکار موتور فارسی‌نویس (libraqm0) قبل از بارگذاری Pillow بدون نیاز به تغییر bot.yml
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
    "شیراز": (29.5918, 52.5837, 12),
    "فارس": (29.5918, 52.5837, 8),
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
BTN_SHADOWBAN = "🛡️ سپر ضدشدوبن"
BTN_THEME = "🎨 تغییر تم گرافیکی"
BTN_OCCASION = "📅 کارت مناسبت امروز"
BTN_STATUS = "📊 وضعیت استودیو"
BTN_BACK = "🔙 بازگشت به منوی اصلی"
BTN_CANCEL = "❌ انصراف و بازگشت"
BTN_SKIP_PHOTO = "⏭️ بدون عکس گوینده"
BTN_SAFE_REWRITE = "✨ بازنویسی ایمن آخرین کپشن"

CONFIG = {
    "theme": "navy",
    "use_repo_frame": True,
    "video_antidup": True,
    "video_facetrack": True,
    "video_brand": True,
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
# ==================== ابزارهای کمکی، ساخت صدای خبری و اجرای امن FFmpeg ====================
def run_ffmpeg(cmd: list):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        err_lines = [ln.strip() for ln in res.stderr.splitlines() if ln.strip()]
        tail = "\n".join(err_lines[-4:]) if err_lines else f"exit code {res.returncode}"
        raise RuntimeError(tail)


def generate_news_audio_wav(out_path: str, duration_sec: float, mode: str = "news") -> str:
    """ساخت مستقیم فایل صوتی WAV با پایتون (حذف کامل aevalsrc و رفع قطعی ارور 234 در FFmpeg)."""
    sr = 44100
    n_samples = int(sr * duration_sec)
    frames = bytearray()
    two_pi = 2.0 * math.pi

    for i in range(n_samples):
        t = i / sr
        if mode == "incident":
            pulse = 0.5 + 0.5 * math.sin(two_pi * 2.2 * t)
            beat = 1.0 if (t % 0.75) > 0.60 else 0.0
            val = 0.16 * math.sin(two_pi * 75.0 * t) * pulse + 0.05 * math.sin(two_pi * 220.0 * t) * beat
        else:
            pulse = 0.5 + 0.5 * math.sin(two_pi * 1.5 * t)
            beat = 1.0 if (t % 1.2) > 1.05 else 0.0
            val = 0.11 * math.sin(two_pi * 110.0 * t) * pulse + 0.035 * math.sin(two_pi * 330.0 * t) * beat

        sample = max(-32767, min(32767, int(val * 32767)))
        frames += struct.pack("<h", sample)

    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(frames)
    return out_path


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
        "assets/frame.png",
    ):
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return path
    return ""


def find_repo_incident_frame() -> str:
    for path in ("incident_frame.png", "assets/incident_frame.png"):
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return path
    return ""


def prepare_rgba_frame_1080x1920(src_path: str, work_dir: str) -> str:
    img = Image.open(src_path).convert("RGBA")
    if img.size != (1080, 1920):
        img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
    out = os.path.join(work_dir, "prepared_repo_frame.png")
    img.save(out, format="PNG")
    return out


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
        return ImageFont.truetype(find_font_path(kind), size)
    except Exception:
        return ImageFont.load_default()


def prepare_text_and_kwargs(text: str, is_rtl: bool = True) -> tuple:
    """وقتی Raqm فعال باشد متن خام فارسی با direction='rtl' رسم می‌شود تا حروف پیوسته و بدون مربع باشند."""
    if HAS_RAQM:
        if is_rtl:
            return text, {"direction": "rtl", "language": "fa"}
        return text, {"direction": "ltr"}
    if is_rtl:
        return get_display(arabic_reshaper.reshape(text)), {}
    return text, {}


def wrap_persian_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 4) -> list:
    words = text.replace("\n", " ").split()
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
            if len(lines) >= max_lines - 1:
                break
    if cur and len(lines) < max_lines:
        lines.append(" ".join(cur))
    return lines


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
    if not text:
        return
    t_draw, kw = prepare_text_and_kwargs(text, is_rtl=is_rtl)
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


def fit_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    nw, nh = int(src_w * scale), int(src_h * scale)
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - target_w) // 2
    top = (nh - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def clean_caption_markdown(text: str) -> str:
    text = text.replace("**", "").replace("__", "").replace("```", "")
    lines = [ln.rstrip() for ln in text.strip().splitlines()]
    return "\n".join(lines).strip()


def check_shadowban_words(text: str) -> list:
    return [(w, alt) for w, alt in SENSITIVE_WORDS.items() if w in text]


def add_to_daily_items(headline: str, photo_path: str = None, tag: str = "خبر"):
    clean_hl = headline.replace("⭕", "").strip()
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
        "tag": tag,
        "time": get_tehran_now().strftime("%H:%M"),
    })
    if len(DAILY_ITEMS) > 10:
        old = DAILY_ITEMS.pop(0)
        if old.get("photo") and os.path.exists(old["photo"]):
            try:
                os.remove(old["photo"])
            except Exception:
                pass


# ==================== کیبوردهای ثابت منوی پایین صفحه (Reply Keyboard) ====================
def kb_main_menu() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_CARD_POST}, {"text": BTN_CARD_STORY}],
            [{"text": BTN_INCIDENT}],
            [{"text": BTN_CAPTION}],
            [{"text": BTN_MAP}, {"text": BTN_AUDIO}],
            [{"text": BTN_DAILY60}],
            [{"text": BTN_VIDEO}],
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
            [{"text": f"🖼️ قاب ریلز مخزن: {st(CONFIG['use_repo_frame'])}"}],
            [{"text": f"🧬 اصالت‌سازی و حذف متادیتا: {st(CONFIG['video_antidup'])}"}],
            [{"text": f"👤 ردیابی چهره ۹:۱۶: {st(CONFIG['video_facetrack'])}"}],
            [{"text": f"🏷️ اند-اسکرین دعوت به فالو: {st(CONFIG['video_brand'])}"}],
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
    raqm_status = "فعال ✅ (فونت فارسی سالم)" if HAS_RAQM else "حالت پشتیبان"

    repo_fr = find_repo_reel_frame()
    if repo_fr:
        fr_status = f"فعال ✅ ({os.path.basename(repo_fr)})" if CONFIG["use_repo_frame"] else f"موجود ولی خاموش ⏸ ({os.path.basename(repo_fr)})"
    else:
        fr_status = "آپلود نشده (نام فایل: reel_frame.png)"

    return (
        f"🎬 استودیوی تولید محتوای {BRAND_HANDLE}\n\n"
        f"🕒 ساعت تهران: {now_str}\n"
        f"🎨 تم فعال: {t_name}\n"
        f"🖼️ قاب ریلز مخزن: {fr_status}\n"
        f"🔤 موتور فارسی‌نویس: {raqm_status}\n"
        f"🧠 هوش مصنوعی سردبیری: {ai_status}\n"
        f"📦 خبرهای صف جمع‌بندی ۶۰ ثانیه‌ای امروز: {to_persian_digits(str(len(DAILY_ITEMS)))} مورد\n\n"
        "از دکمه‌های منوی پایین صفحه، ابزار موردنظر را انتخاب کنید:"
    )


# ==================== ارتباط با Telegram API ====================
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


# ==================== ذخیره و بازیابی تنظیمات در پیام پین‌شده ====================
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

    hl = (news_text.splitlines()[0] if news_text else "گزارش خبری جدید")[:70]
    prefix = "⭕ فوری |" if force_incident else "⭕ خبر شیراز |"
    return (
        f"{prefix} {hl}\n\n"
        f"{(news_text or 'جزئیات تکمیلی این خبر به‌زودی منتشر می‌شود.')[:220]}\n\n"
        "💬 نظر شما درباره این موضوع چیست؟ (۱: موافقم | ۲: مخالفم)\n\n"
        "🔔 پوشش لحظه‌ای اخبار شیراز و استان فارس در استوری‌ها و ریلزها\n"
        "📲 برای پیگیری ادامه خبر فالو کنید: @shirazlastnews\n\n"
        "#شیراز #استان_فارس #اخبار_شیراز #خبر_فوری #فارس"
    )


async def extract_short_headline(session: aiohttp.ClientSession, news_text: str, is_incident: bool = False) -> tuple:
    if GEMINI_API_KEY and news_text:
        p = (
            "از متن خبر زیر فقط یک تیتر بسیار کوتاه و کوبنده (حداکثر ۸ کلمه، رسمی و بدون کلیک‌بیت) "
            "و یک برچسب ۱ یا ۲ کلمه‌ای (مثل فوری، حادثه، خبر شیراز، اقتصادی، ورزشی) استخراج کن.\n"
            "خروجی را دقیقاً در دو خط بده:\n"
            "خط اول: فقط برچسب\n"
            "خط دوم: فقط تیتر\n\n"
            f"متن خبر:\n{news_text}"
        )
        out = await gemini_generate(session, p)
        lines = [ln.strip("•-*⭕ ") for ln in out.splitlines() if ln.strip()]
        if len(lines) >= 2:
            badge = "فوری | حادثه" if is_incident else lines[0][:22]
            return badge, lines[1][:85]

    first_line = (news_text.splitlines()[0] if news_text else BRAND_TITLE_FA).strip()
    words = first_line.split()[:9]
    badge = "فوری | حادثه" if is_incident else "خبر شیراز"
    return badge, " ".join(words)


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
    # ==================== ۱. کارت‌ساز پست (۴:۵) و استوری (۹:۱۶) ====================
def render_news_card_sync(photo_path: str, badge: str, headline: str, subtext: str, fmt: str = "post", theme_key: str = "navy") -> str:
    theme = THEMES.get(theme_key, THEMES["navy"])
    w, h = (1080, 1350) if fmt == "post" else (1080, 1920)

    if photo_path and os.path.exists(photo_path):
        base = Image.open(photo_path).convert("RGB")
        canvas = fit_cover(base, w, h).convert("RGBA")
    else:
        canvas = Image.new("RGBA", (w, h), theme["bg"] + (255,))

    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad)
    bg_r, bg_g, bg_b = theme["bg"]

    for y in range(260):
        alpha = int(190 * (1 - y / 260))
        gdraw.line([(0, y), (w, y)], fill=(bg_r, bg_g, bg_b, alpha))

    bottom_start = int(h * 0.42)
    for y in range(bottom_start, h):
        ratio = (y - bottom_start) / (h - bottom_start)
        alpha = int(248 * (ratio ** 1.35))
        gdraw.line([(0, y), (w, y)], fill=(bg_r, bg_g, bg_b, alpha))

    canvas = Image.alpha_composite(canvas, grad)
    draw = ImageDraw.Draw(canvas)

    draw.rectangle([(0, 0), (w, 16)], fill=theme["accent"] + (255,))

    f_brand = load_font("bold", 34)
    f_handle = load_font("regular", 28)
    jnow = jdatetime.datetime.fromgregorian(datetime=get_tehran_now())
    date_str = to_persian_digits(f"{jnow.day} {JALALI_MONTHS[jnow.month]} {jnow.year}")

    draw_rtl_text(draw, (w - 54, 46), BRAND_TITLE_FA, f_brand, theme["text"] + (255,), align="right")
    draw_rtl_text(draw, (54, 52), BRAND_HANDLE, f_handle, theme["accent"] + (255,), align="left", shadow=False, is_rtl=False)
    draw_rtl_text(draw, (w - 54, 96), date_str, load_font("regular", 24), theme["subtext"] + (230,), align="right", shadow=False)

    f_badge = load_font("bold", 34)
    b_txt, b_kw = prepare_text_and_kwargs(badge, is_rtl=True)
    bb = draw.textbbox((0, 0), b_txt, font=f_badge, **b_kw)
    bw = (bb[2] - bb[0]) + 56
    bh = 62

    f_title = load_font("display", 78 if fmt == "story" else 70)
    lines = wrap_persian_lines(draw, headline, f_title, w - 120, max_lines=3)
    line_h = 104 if fmt == "story" else 94
    block_h = len(lines) * line_h

    title_start_y = h - 245 - block_h if fmt == "post" else h - 380 - block_h
    badge_y = title_start_y - bh - 28

    draw.rounded_rectangle([(w - 56 - bw, badge_y), (w - 56, badge_y + bh)], radius=12, fill=theme["badge_bg"] + (255,))
    draw_rtl_text(draw, (w - 56 - bw // 2, badge_y + 10), badge, f_badge, theme["badge_text"] + (255,), align="center", shadow=False)
    draw.rectangle([(w - 42, title_start_y + 8), (w - 30, title_start_y + block_h - 10)], fill=theme["accent"] + (255,))

    cur_y = title_start_y
    for ln in lines:
        draw_rtl_text(draw, (w - 64, cur_y), ln, f_title, theme["text"] + (255,), align="right", shadow=True, shadow_offset=5)
        cur_y += line_h

    if subtext:
        f_sub = load_font("regular", 31)
        sub_lines = wrap_persian_lines(draw, subtext, f_sub, w - 120, max_lines=2)
        sy = cur_y + 16
        for sl in sub_lines:
            draw_rtl_text(draw, (w - 64, sy), sl, f_sub, theme["subtext"] + (240,), align="right", shadow=False)
            sy += 46

    footer_y = h - 88 if fmt == "post" else h - 140
    draw.line([(54, footer_y - 18), (w - 54, footer_y - 18)], fill=theme["accent"] + (130,), width=2)
    draw_rtl_text(draw, (w - 54, footer_y), "پوشش لحظه‌ای اخبار شیراز و فارس", load_font("regular", 26), theme["subtext"] + (220,), align="right", shadow=False)
    draw_rtl_text(draw, (54, footer_y), BRAND_HANDLE, load_font("bold", 28), theme["accent"] + (255,), align="left", shadow=False, is_rtl=False)

    out_path = os.path.join(TMP_ROOT, f"card_{fmt}_{int(time.time()*1000)}.jpg")
    canvas.convert("RGB").save(out_path, quality=94)
    return out_path


# ==================== ۲. ریلز فوری و حادثه‌ای (قالب اضطراری کاملاً متمایز) ====================
def build_incident_reel_sync(photo_path: str, headline: str, location_or_sub: str = "") -> str:
    w, h = 1080, 1920
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)

    bg_path = os.path.join(work_dir, "bg.jpg")
    if photo_path and os.path.exists(photo_path):
        im = fit_cover(Image.open(photo_path).convert("RGB"), 1200, 2134)
    else:
        im = Image.new("RGB", (1200, 2134), (20, 10, 12))
    im.save(bg_path, quality=92)

    def make_siren_glow(left_color, right_color, out_name):
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.ellipse([(-260, -180), (540, 620)], fill=left_color + (165,))
        d.ellipse([(w - 540, -180), (w + 260, 620)], fill=right_color + (165,))
        d.rectangle([(0, 0), (38, h)], fill=left_color + (100,))
        d.rectangle([(w - 38, 0), (w, h)], fill=right_color + (100,))
        layer = layer.filter(ImageFilter.GaussianBlur(radius=95))
        p = os.path.join(work_dir, out_name)
        layer.save(p)
        return p

    glow_a = make_siren_glow((239, 35, 60), (37, 99, 235), "glow_a.png")
    glow_b = make_siren_glow((37, 99, 235), (239, 35, 60), "glow_b.png")

    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)

    for y in range(420):
        od.line([(0, y), (w, y)], fill=(8, 8, 12, int(235 * (1 - y / 420))))
    for y in range(960, h):
        r = (y - 960) / (h - 960)
        od.line([(0, y), (w, y)], fill=(10, 6, 8, int(252 * (r ** 1.15))))

    def draw_hazard_stripe(y_top, height, color1, color2=(12, 12, 14, 255)):
        od.rectangle([(0, y_top), (w, y_top + height)], fill=color2)
        step = 54
        for x in range(-height, w + step, step):
            poly = [(x, y_top + height), (x + 26, y_top + height), (x + 26 + height, y_top), (x + height, y_top)]
            od.polygon(poly, fill=color1)

    draw_hazard_stripe(0, 28, (220, 38, 38, 255))
    draw_hazard_stripe(h - 28, 28, (250, 204, 21, 255))

    od.rounded_rectangle([(w - 445, 118), (w - 48, 206)], radius=12, fill=(220, 38, 38, 250), outline=(250, 204, 21, 255), width=4)
    draw_rtl_text(od, (w - 246, 134), "فوری | گزارش حادثه", load_font("display", 46), (255, 255, 255, 255), align="center", shadow=False)

    now_t = to_persian_digits(get_tehran_now().strftime("%H:%M"))
    od.rounded_rectangle([(48, 124), (295, 200)], radius=10, fill=(15, 15, 20, 225), outline=(220, 38, 38, 255), width=3)
    draw_rtl_text(od, (171, 140), f"ساعت {now_t}", load_font("bold", 32), (250, 204, 21, 255), align="center", shadow=False)

    f_title = load_font("display", 82)
    lines = wrap_persian_lines(od, headline, f_title, w - 150, max_lines=3)
    line_h = 104
    box_h = len(lines) * line_h + 75
    box_top = h - 390 - box_h

    od.rounded_rectangle([(46, box_top), (w - 46, box_top + box_h)], radius=18, fill=(14, 10, 12, 228), outline=(220, 38, 38, 255), width=5)
    od.rectangle([(w - 64, box_top + 22), (w - 50, box_top + box_h - 22)], fill=(250, 204, 21, 255))

    ty = box_top + 32
    for ln in lines:
        draw_rtl_text(od, (w - 86, ty), ln, f_title, (255, 255, 255, 255), align="right", shadow=True, shadow_offset=5)
        ty += line_h

    ticker_y = box_top + box_h + 30
    od.rectangle([(0, ticker_y), (w, ticker_y + 76)], fill=(185, 28, 28, 245))
    sub_line = location_or_sub.strip() if location_or_sub else "پوشش فوری حوادث شیراز، فارس و ایران"
    draw_rtl_text(od, (w // 2, ticker_y + 16), sub_line[:58], load_font("bold", 34), (255, 255, 255, 255), align="center", shadow=False)
    draw_rtl_text(od, (w - 60, ticker_y + 106), BRAND_TITLE_FA, load_font("bold", 32), (250, 204, 21, 255), align="right")
    draw_rtl_text(od, (60, ticker_y + 106), BRAND_HANDLE, load_font("bold", 32), (250, 204, 21, 255), align="left", is_rtl=False)

    inc_frame = find_repo_incident_frame()
    if inc_frame:
        fr_img = Image.open(inc_frame).convert("RGBA").resize((w, h), Image.Resampling.LANCZOS)
        ov = Image.alpha_composite(ov, fr_img)

    ov_path = os.path.join(work_dir, "overlay.png")
    ov.save(ov_path)

    wav_path = generate_news_audio_wav(os.path.join(work_dir, "sfx.wav"), 14.0, mode="incident")
    out_mp4 = os.path.join(TMP_ROOT, f"incident_reel_{int(time.time()*1000)}.mp4")

    cmd = [
        "ffmpeg", "-y",
        "-i", bg_path,
        "-loop", "1", "-t", "14", "-i", glow_a,
        "-loop", "1", "-t", "14", "-i", glow_b,
        "-loop", "1", "-t", "14", "-i", ov_path,
        "-i", wav_path,
        "-filter_complex",
        "[0:v]zoompan=z='1+0.00042*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=350:s=1080x1920:fps=25,format=rgba[bg];"
        "[bg][1:v]overlay=0:0:enable='floor(2*t)-2*floor(t)'[s1];"
        "[s1][2:v]overlay=0:0:enable='1-(floor(2*t)-2*floor(t))'[s2];"
        "[s2][3:v]overlay=0:0,format=yuv420p[vout]",
        "-map", "[vout]", "-map", "4:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", "-t", "14", out_mp4,
    ]
    run_ffmpeg(cmd)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۳. ریلز زوم سینمایی روی نقشه ====================
def latlon_to_tile(lat: float, lon: float, zoom: int):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


async def resolve_location_coords(session: aiohttp.ClientSession, loc_name: str):
    clean = loc_name.strip()
    for key, val in FARS_LOCATIONS.items():
        if key in clean:
            return val
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": f"{clean}, Iran", "format": "json", "limit": 1}
        headers = {"User-Agent": "ShirazLastNewsStudioBot/1.0"}
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"]), 13
    except Exception:
        pass
    return FARS_LOCATIONS["شیراز"]


async def fetch_dark_map_image(session: aiohttp.ClientSession, lat: float, lon: float, zoom: int) -> Image.Image:
    cx, cy = latlon_to_tile(lat, lon, zoom)
    grid = Image.new("RGB", (256 * 5, 256 * 5), (18, 24, 34))
    headers = {"User-Agent": "ShirazLastNewsStudioBot/1.0"}

    async def get_tile(dx, dy):
        tx, ty = cx + dx, cy + dy
        url = f"https://a.basemaps.cartocdn.com/dark_all/{zoom}/{tx}/{ty}.png"
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    raw = await r.read()
                    tile = Image.open(io.BytesIO(raw)).convert("RGB")
                    grid.paste(tile, ((dx + 2) * 256, (dy + 2) * 256))
        except Exception:
            pass

    await asyncio.gather(*(get_tile(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)))
    return fit_cover(grid, 1200, 2134)


def build_map_zoom_reel_sync(map_img: Image.Image, photo_path: str, loc_name: str, headline: str) -> str:
    w, h = 1080, 1920
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)

    map_bg_path = os.path.join(work_dir, "map_bg.jpg")
    map_img.save(map_bg_path, quality=92)

    hud = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hud)
    cx, cy = w // 2, h // 2

    hd.ellipse([(cx - 190, cy - 190), (cx + 190, cy + 190)], outline=(239, 68, 68, 95), width=4)
    hd.ellipse([(cx - 120, cy - 120), (cx + 120, cy + 120)], outline=(239, 68, 68, 175), width=5)
    hd.ellipse([(cx - 48, cy - 48), (cx + 48, cy + 48)], fill=(239, 68, 68, 90), outline=(255, 255, 255, 230), width=4)
    hd.ellipse([(cx - 16, cy - 16), (cx + 16, cy + 16)], fill=(239, 68, 68, 255))

    f_loc = load_font("display", 54)
    loc_txt = f"موقعیت: {loc_name}"
    l_draw, l_kw = prepare_text_and_kwargs(loc_txt, is_rtl=True)
    lb = hd.textbbox((0, 0), l_draw, font=f_loc, **l_kw)
    lw = min(w - 100, (lb[2] - lb[0]) + 84)
    hd.rounded_rectangle([(cx - lw // 2, cy + 90), (cx + lw // 2, cy + 178)], radius=14, fill=(220, 38, 38, 240), outline=(255, 255, 255, 220), width=3)
    draw_rtl_text(hd, (cx, cy + 104), loc_txt, f_loc, (255, 255, 255, 255), align="center", shadow=False)

    hd.rectangle([(0, 0), (w, 130)], fill=(10, 15, 25, 210))
    draw_rtl_text(hd, (w // 2, 36), f"گزارش مکانی | {BRAND_TITLE_FA}", load_font("bold", 38), (234, 179, 8, 255), align="center")
    hud_path = os.path.join(work_dir, "hud.png")
    hud.save(hud_path)

    card_path = render_news_card_sync(photo_path, f"گزارش از {loc_name}", headline, "", fmt="story", theme_key=CONFIG["theme"])
    news_bg_path = os.path.join(work_dir, "news_bg.jpg")
    Image.open(card_path).convert("RGB").resize((1200, 2134), Image.Resampling.LANCZOS).save(news_bg_path, quality=92)

    clip1 = os.path.join(work_dir, "c1.mp4")
    clip2 = os.path.join(work_dir, "c2.mp4")
    wav_path = generate_news_audio_wav(os.path.join(work_dir, "map_sfx.wav"), 12.0, mode="news")
    out_mp4 = os.path.join(TMP_ROOT, f"map_reel_{int(time.time()*1000)}.mp4")

    run_ffmpeg([
        "ffmpeg", "-y", "-i", map_bg_path, "-loop", "1", "-t", "4.5", "-i", hud_path,
        "-filter_complex",
        "[0:v]zoompan=z='1+0.0042*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=113:s=1080x1920:fps=25,format=rgba[m];"
        "[m][1:v]overlay=0:0,format=yuv420p,setsar=1[v]",
        "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-t", "4.5", clip1
    ])

    run_ffmpeg([
        "ffmpeg", "-y", "-i", news_bg_path,
        "-vf", "zoompan=z='1+0.0005*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=200:s=1080x1920:fps=25,format=yuv420p,setsar=1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-t", "8", clip2
    ])

    repo_frame = find_repo_reel_frame() if CONFIG["use_repo_frame"] else ""
    cmd = ["ffmpeg", "-y", "-i", clip1, "-i", clip2, "-i", wav_path]
    base_xf = "[0:v]fps=25,format=yuv420p,settb=AVTB[v0];[1:v]fps=25,format=yuv420p,settb=AVTB[v1];[v0][v1]xfade=transition=fade:duration=0.5:offset=4.0"
    if repo_frame:
        fr_p = prepare_rgba_frame_1080x1920(repo_frame, work_dir)
        cmd += ["-loop", "1", "-t", "12", "-i", fr_p]
        fcomp = f"{base_xf},format=rgba[xf];[xf][3:v]overlay=0:0,format=yuv420p[v]"
    else:
        fcomp = f"{base_xf},format=yuv420p[v]"

    cmd += [
        "-filter_complex", fcomp, "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-t", "12", out_mp4
    ]
    run_ffmpeg(cmd)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۴. ریلز جمع‌بندی «۶۰ ثانیه با اخبار شیراز» ====================
def build_daily_summary_reel_sync(items: list) -> str:
    w, h = 1080, 1920
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)
    theme = THEMES.get(CONFIG["theme"], THEMES["navy"])
    clips = []

    jnow = jdatetime.datetime.fromgregorian(datetime=get_tehran_now())
    date_str = to_persian_digits(f"{JALALI_WEEKDAYS[jnow.weekday()]} {jnow.day} {JALALI_MONTHS[jnow.month]} {jnow.year}")

    intro = Image.new("RGB", (w, h), theme["bg"])
    idraw = ImageDraw.Draw(intro)
    idraw.rectangle([(0, 0), (w, 24)], fill=theme["accent"])
    idraw.rectangle([(0, h - 24), (w, h)], fill=theme["accent"])
    draw_rtl_text(idraw, (w // 2, 620), "بسته خبری روزانه", load_font("bold", 48), theme["accent"], align="center")
    draw_rtl_text(idraw, (w // 2, 720), "۶۰ ثانیه با اخبار شیراز", load_font("display", 94), theme["text"], align="center")
    draw_rtl_text(idraw, (w // 2, 880), date_str, load_font("bold", 42), theme["subtext"], align="center")
    draw_rtl_text(idraw, (w // 2, 1080), f"{to_persian_digits(str(len(items)))} تیتر برگزیده امروز", load_font("bold", 40), theme["accent"], align="center")
    draw_rtl_text(idraw, (w // 2, 1680), BRAND_HANDLE, load_font("bold", 42), theme["text"], align="center", is_rtl=False)
    intro_img = os.path.join(work_dir, "intro.jpg")
    intro.save(intro_img, quality=92)
    intro_mp4 = os.path.join(work_dir, "s_00.mp4")
    run_ffmpeg([
        "ffmpeg", "-y", "-i", intro_img,
        "-vf", "zoompan=z='1+0.0009*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=63:s=1080x1920:fps=25,format=yuv420p,setsar=1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-t", "2.5", intro_mp4
    ])
    clips.append(intro_mp4)

    for idx, item in enumerate(items[:6], start=1):
        badge = f"خبر {to_persian_digits(str(idx))} از {to_persian_digits(str(len(items[:6])))}  |  {item.get('tag', 'شیراز')}"
        card_p = render_news_card_sync(item.get("photo"), badge, item["headline"], f"ثبت‌شده در ساعت {to_persian_digits(item.get('time', ''))}", fmt="story", theme_key=CONFIG["theme"])
        c_mp4 = os.path.join(work_dir, f"s_{idx:02d}.mp4")
        run_ffmpeg([
            "ffmpeg", "-y", "-i", card_p,
            "-vf", "zoompan=z='1+0.00055*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=138:s=1080x1920:fps=25,format=yuv420p,setsar=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-t", "5.5", c_mp4
        ])
        clips.append(c_mp4)

    clips.append(build_endscreen_clip_sync(work_dir, duration=2.5))

    list_file = os.path.join(work_dir, "concat.txt")
    with open(list_file, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")

    total_sec = 2.5 + len(items[:6]) * 5.5 + 2.5
    wav_path = generate_news_audio_wav(os.path.join(work_dir, "daily_sfx.wav"), total_sec, mode="news")
    out_mp4 = os.path.join(TMP_ROOT, f"daily60_{int(time.time()*1000)}.mp4")
    repo_frame = find_repo_reel_frame() if CONFIG["use_repo_frame"] else ""

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-i", wav_path]
    if repo_frame:
        fr_p = prepare_rgba_frame_1080x1920(repo_frame, work_dir)
        cmd += ["-loop", "1", "-t", str(total_sec), "-i", fr_p,
                "-filter_complex", "[0:v]format=rgba[base];[base][2:v]overlay=0:0:shortest=1,format=yuv420p[v]",
                "-map", "[v]", "-map", "1:a"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]

    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out_mp4
    ]
    run_ffmpeg(cmd)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۵. ریلز موج صوتی (Audiogram) ====================
def build_audiogram_reel_sync(audio_path: str, headline: str, speaker_photo: str = None) -> str:
    w, h = 1080, 1920
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)
    theme = THEMES.get(CONFIG["theme"], THEMES["navy"])

    bg = Image.new("RGBA", (w, h), theme["bg"] + (255,))
    draw = ImageDraw.Draw(bg)

    draw.rectangle([(0, 0), (w, 18)], fill=theme["accent"] + (255,))
    draw.rectangle([(0, h - 18), (w, h)], fill=theme["accent"] + (255,))
    draw_rtl_text(draw, (w // 2, 145), "گزارش صوتی اختصاصی", load_font("bold", 40), theme["accent"] + (255,), align="center")
    draw_rtl_text(draw, (w // 2, 210), BRAND_TITLE_FA, load_font("display", 54), theme["text"] + (255,), align="center")

    circle_r = 205
    cx, cy = w // 2, 560
    draw.ellipse([(cx - circle_r - 12, cy - circle_r - 12), (cx + circle_r + 12, cy + circle_r + 12)], fill=theme["accent"] + (255,))

    if speaker_photo and os.path.exists(speaker_photo):
        sp = fit_cover(Image.open(speaker_photo).convert("RGB"), circle_r * 2, circle_r * 2)
        mask = Image.new("L", (circle_r * 2, circle_r * 2), 0)
        ImageDraw.Draw(mask).ellipse([(0, 0), (circle_r * 2, circle_r * 2)], fill=255)
        bg.paste(sp, (cx - circle_r, cy - circle_r), mask)
    else:
        draw.ellipse([(cx - circle_r, cy - circle_r), (cx + circle_r, cy + circle_r)], fill=(25, 42, 72, 255))
        draw_rtl_text(draw, (cx, cy - 34), "گزارش صوتی", load_font("display", 56), theme["text"] + (255,), align="center")

    f_title = load_font("display", 70)
    lines = wrap_persian_lines(draw, headline, f_title, w - 140, max_lines=3)
    ty = 840
    for ln in lines:
        draw_rtl_text(draw, (w // 2, ty), ln, f_title, theme["text"] + (255,), align="center")
        ty += 94

    draw.rounded_rectangle([(60, 1210), (w - 60, 1490)], radius=24, fill=(0, 0, 0, 100), outline=theme["accent"] + (160,), width=3)
    draw_rtl_text(draw, (w // 2, 1630), BRAND_HANDLE, load_font("bold", 38), theme["accent"] + (255,), align="center", is_rtl=False)

    bg_path = os.path.join(work_dir, "audio_bg.png")
    bg.convert("RGB").save(bg_path)

    out_mp4 = os.path.join(TMP_ROOT, f"audiogram_{int(time.time()*1000)}.mp4")
    wave_color = theme["wave_hex"]
    repo_frame = find_repo_reel_frame() if CONFIG["use_repo_frame"] else ""

    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", bg_path, "-i", audio_path]
    if repo_frame:
        fr_p = prepare_rgba_frame_1080x1920(repo_frame, work_dir)
        cmd += ["-loop", "1", "-i", fr_p]
        fcomp = (
            f"[1:a]showwaves=s=920x230:mode=cline:rate=25:colors={wave_color}[w];"
            "[0:v][w]overlay=(W-w)/2:1235:shortest=1,format=rgba[bw];"
            "[bw][2:v]overlay=0:0:shortest=1,format=yuv420p[v]"
        )
    else:
        fcomp = (
            f"[1:a]showwaves=s=920x230:mode=cline:rate=25:colors={wave_color}[w];"
            "[0:v][w]overlay=(W-w)/2:1235:shortest=1,format=yuv420p[v]"
        )

    cmd += [
        "-filter_complex", fcomp, "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out_mp4
    ]
    run_ffmpeg(cmd)
    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4


# ==================== ۶. استودیو تدوین ویدئو (اصالت + چهره + قاب ریلز + اند-اسکرین) ====================
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


def build_lower_third_png(work_dir: str) -> str:
    theme = THEMES.get(CONFIG["theme"], THEMES["navy"])
    ov = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle([(560, 1560), (1035, 1665)], radius=16, fill=theme["bg"] + (225,), outline=theme["accent"] + (255,), width=3)
    d.rectangle([(1018, 1574), (1028, 1651)], fill=theme["accent"] + (255,))
    draw_rtl_text(d, (1000, 1574), BRAND_TITLE_FA, load_font("bold", 30), theme["text"] + (255,), align="right", shadow=False)
    draw_rtl_text(d, (585, 1618), BRAND_HANDLE, load_font("bold", 26), theme["accent"] + (255,), align="left", shadow=False, is_rtl=False)
    p = os.path.join(work_dir, "lower_third.png")
    ov.save(p)
    return p


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
    cmd += [
        "-vf", "scale=1080:1920,fps=25,format=yuv420p,setsar=1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
    ]
    if with_silent_audio:
        cmd += ["-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k"]
    cmd += ["-t", str(duration), mp4_p]
    run_ffmpeg(cmd)
    return mp4_p


def process_video_studio_sync(video_path: str) -> tuple:
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)
    info = probe_video_info(video_path)
    w, h = info["width"], info["height"]
    has_audio = info["has_audio"]

    applied = []
    use_antidup = CONFIG["video_antidup"]
    use_facetrack = CONFIG["video_facetrack"]
    use_brand = CONFIG["video_brand"]
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

    v_chain += ",fps=25,setsar=1"

    inputs = ["-i", video_path]
    if repo_frame:
        fr_p = prepare_rgba_frame_1080x1920(repo_frame, work_dir)
        inputs += ["-loop", "1", "-i", fr_p]
        v_chain += ",format=rgba[mainv];[mainv][1:v]overlay=0:0:shortest=1,format=yuv420p[vout]"
        applied.append(f"قاب ریلز اختصاصی مخزن ({os.path.basename(repo_frame)}) ✅")
    elif use_brand:
        lt_png = build_lower_third_png(work_dir)
        inputs += ["-loop", "1", "-i", lt_png]
        v_chain += ",format=rgba[mainv];[mainv][1:v]overlay=0:0:shortest=1:enable='floor(t)',format=yuv420p[vout]"
        applied.append("نوار برند Lower-Third ✅")
    else:
        v_chain += ",format=yuv420p[vout]"

    main_processed = os.path.join(work_dir, "main_proc.mp4")
    cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", v_chain, "-map", "[vout]"]
    if has_audio:
        if use_antidup:
            cmd += ["-filter:a", "atempo=1.015"]
        cmd += ["-map", "0:a", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k"]
    cmd += [
        "-map_metadata", "-1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-movflags", "+faststart", main_processed
    ]
    run_ffmpeg(cmd)

    out_mp4 = os.path.join(TMP_ROOT, f"studio_vid_{int(time.time()*1000)}.mp4")
    if use_brand:
        end_clip = build_endscreen_clip_sync(work_dir, duration=2.2, with_silent_audio=has_audio)
        applied.append("اند-اسکرین دعوت به فالو (۲.۲ ثانیه) ✅")
        if has_audio:
            run_ffmpeg([
                "ffmpeg", "-y", "-i", main_processed, "-i", end_clip,
                "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]",
                "-map_metadata", "-1",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
                "-movflags", "+faststart", out_mp4
            ])
        else:
            run_ffmpeg([
                "ffmpeg", "-y", "-i", main_processed, "-i", end_clip,
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map", "[v]",
                "-map_metadata", "-1",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-movflags", "+faststart", out_mp4
            ])
    else:
        shutil.copy(main_processed, out_mp4)

    shutil.rmtree(work_dir, ignore_errors=True)
    return out_mp4, applied


# ==================== ۷. کارت مناسبت‌نگار روزانه ====================
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
            "فقط در یک جمله بسیار کوتاه (حداکثر ۱۰ کلمه) مهم‌ترین مناسبت رسمی یا فرهنگی امروز در ایران یا شیراز را بنویس "
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
        f_occ = load_font("bold", 46)
        lines = wrap_persian_lines(d, occasion, f_occ, w - 220, max_lines=3)
        oy = 1220
        for ln in lines:
            draw_rtl_text(d, (w // 2, oy), ln, f_occ, theme["subtext"], align="center")
            oy += 72

        draw_rtl_text(d, (w // 2, 1620), BRAND_HANDLE, load_font("bold", 42), theme["accent"], align="center", is_rtl=False)
        out = os.path.join(TMP_ROOT, f"occasion_{int(time.time()*1000)}.jpg")
        im.save(out, quality=94)
        return out

    card_path = await asyncio.to_thread(draw_card)
    caption = f"📅 {full_date}\n\n{occasion}\n\n🔔 {BRAND_HANDLE}"
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


# ==================== اجرای کارهای ویدئویی در پس‌زمینه ====================
async def run_daily60_job(session: aiohttp.ClientSession, chat_id: str):
    try:
        items_copy = list(DAILY_ITEMS[-6:])
        mp4 = await asyncio.to_thread(build_daily_summary_reel_sync, items_copy)
        await send_video_file(session, chat_id, mp4, caption="🎬 ریلز جمع‌بندی ۶۰ ثانیه‌ای اخبار امروز آماده است!")
        headlines_text = "\n".join(f"- {it['headline']}" for it in items_copy)
        cap = await generate_editorial_caption(session, f"جمع‌بندی مهم‌ترین اخبار امروز شیراز و استان فارس:\n{headlines_text}")
        await send_caption_with_shield(session, chat_id, cap)
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در ساخت ریلز جمع‌بندی:\n{e}", kb_main_menu())


async def run_incident_job(session: aiohttp.ClientSession, chat_id: str, photo_path: str, news_text: str):
    try:
        _, hl = await extract_short_headline(session, news_text, is_incident=True)
        mp4 = await asyncio.to_thread(build_incident_reel_sync, photo_path, hl)
        await send_video_file(session, chat_id, mp4, caption="🚨 ریلز فوری و حادثه‌ای آماده انتشار است.")
        cap = await generate_editorial_caption(
            session,
            news_text=news_text,
            media_path=photo_path or None,
            mime_type="image/jpeg" if photo_path else None,
            force_incident=True,
        )
        await send_caption_with_shield(session, chat_id, cap)
        add_to_daily_items(hl, photo_path, tag="فوری")
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در تولید ریلز حادثه‌ای:\n{e}", kb_main_menu())


async def run_map_job(session: aiohttp.ClientSession, chat_id: str, loc_name: str, photo_path: str, news_text: str):
    try:
        lat, lon, zoom = await resolve_location_coords(session, loc_name)
        map_img = await fetch_dark_map_image(session, lat, lon, zoom)
        _, hl = await extract_short_headline(session, news_text)
        mp4 = await asyncio.to_thread(build_map_zoom_reel_sync, map_img, photo_path, loc_name, hl)
        await send_video_file(session, chat_id, mp4, caption=f"🗺️ ریلز زوم نقشه ({loc_name}) آماده است.")
        cap = await generate_editorial_caption(
            session,
            news_text=f"موقعیت خبر: {loc_name}\n{news_text}",
            media_path=photo_path or None,
            mime_type="image/jpeg" if photo_path else None,
        )
        await send_caption_with_shield(session, chat_id, cap)
        add_to_daily_items(hl, photo_path, tag=loc_name)
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در ساخت ریلز نقشه:\n{e}", kb_main_menu())


async def run_audiogram_job(session: aiohttp.ClientSession, chat_id: str, audio_path: str, speaker_photo: str, headline: str):
    try:
        mp4 = await asyncio.to_thread(build_audiogram_reel_sync, audio_path, headline, speaker_photo)
        await send_video_file(session, chat_id, mp4, caption="🎙️ ریلز موج صوتی آماده است.")
        cap = await generate_editorial_caption(
            session,
            news_text=f"تیتر گزارش صوتی: {headline}",
            media_path=audio_path,
            mime_type="audio/ogg",
        )
        await send_caption_with_shield(session, chat_id, cap)
        add_to_daily_items(headline, speaker_photo, tag="صوتی")
        if os.path.exists(mp4):
            os.remove(mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در ساخت ریلز صوتی:\n{e}", kb_main_menu())


async def run_video_studio_job(session: aiohttp.ClientSession, chat_id: str, vid_path: str, user_caption: str):
    try:
        out_mp4, applied = await asyncio.to_thread(process_video_studio_sync, vid_path)
        summary = "🎞️ ویدئو با موفقیت تدوین شد:\n" + "\n".join(f"• {a}" for a in applied)
        await send_video_file(session, chat_id, out_mp4, caption=summary)
        cap = await generate_editorial_caption(session, news_text=user_caption, media_path=vid_path, mime_type="video/mp4")
        await send_caption_with_shield(session, chat_id, cap)
        if os.path.exists(out_mp4):
            os.remove(out_mp4)
    except Exception as e:
        await send_message(session, chat_id, f"⚠️ خطا در پردازش ویدئو:\n{e}", kb_main_menu())


# ==================== مدیریت کامل دکمه‌های منوی پایین صفحه و پیام‌ها ====================
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

    # --- دکمه‌های منوی اصلی پایین صفحه ---
    if is_pure_text and text in (BTN_CARD_POST, BTN_CARD_STORY):
        fmt = "post" if text == BTN_CARD_POST else "story"
        fmt_fa = "پست (۴:۵)" if fmt == "post" else "استوری (۹:۱۶)"
        USER_STATE[chat_id] = {"mode": "card", "step": "wait_input", "fmt": fmt}
        await send_message(
            session,
            chat_id,
            f"🖼️ ساخت کارت {fmt_fa}\n\nعکس خبر را همراه با متن خبر بفرستید (یا فقط متن بفرستید):",
            kb_cancel(),
        )
        return

    if is_pure_text and text == BTN_INCIDENT:
        USER_STATE[chat_id] = {"mode": "incident", "step": "wait_input"}
        await send_message(
            session,
            chat_id,
            "🚨 ساخت ریلز فوری و حادثه‌ای (قالب اضطراری قرمز-مشکی + نور آژیر)\n\n"
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
            "🗺️ ریلز زوم سینمایی روی نقشه\n\n"
            "مرحله ۱ از ۲: نام محله در شیراز یا شهر استان فارس را بنویسید (مثلاً: معالی‌آباد، صدرا، مرودشت):",
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
        if not DAILY_ITEMS:
            await send_message(
                session,
                chat_id,
                "⚠️ هنوز خبری در صف امروز ثبت نشده! هر کارت، ریلز یا کپشنی بسازید خودکار به این صف اضافه می‌شود.",
                kb_main_menu(),
            )
            return
        await send_message(session, chat_id, f"🎬 در حال تدوین ریلز جمع‌بندی از {len(DAILY_ITEMS[:6])} خبر امروز...", kb_main_menu())
        spawn_bg_task(run_daily60_job(session, chat_id))
        return

    if is_pure_text and text == BTN_VIDEO:
        USER_STATE[chat_id] = {"mode": "video_studio", "step": "wait_video"}
        repo_fr = find_repo_reel_frame()
        fr_note = f"فایل شناسایی‌شده: {os.path.basename(repo_fr)}" if repo_fr else "فایل reel_frame.png هنوز آپلود نشده"
        await send_message(
            session,
            chat_id,
            "🎞️ استودیو تدوین هوشمند ویدئو\n\n"
            f"• قاب ریلز مخزن: {fr_note}\n"
            "• گزینه‌ها را از منوی پایین روشن/خاموش کنید و سپس ویدئوی خود را (زیر ۲۰ مگابایت) مستقیم بفرستید:",
            kb_video_studio(),
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
            f"🎨 تغییر آنی تم گرافیکی\n\nتم فعال فعلی: {cur}\nتم جدید را از منوی پایین صفحه انتخاب کنید:",
            kb_theme_menu(),
        )
        return

    if is_pure_text and text == BTN_OCCASION:
        await send_message(session, chat_id, "📅 در حال طراحی کارت مناسبت امروز...")
        card_p, cap = await build_daily_occasion_card(session)
        await send_photo_file(session, chat_id, card_p, caption=cap, reply_markup=kb_main_menu())
        return

    # --- زیرمنوی انتخاب تم گرافیکی ---
    if is_pure_text:
        for tkey, tval in THEMES.items():
            if text == tval["btn"]:
                CONFIG["theme"] = tkey
                await save_config_to_pin(session)
                USER_STATE.pop(chat_id, None)
                await send_message(session, chat_id, f"✅ تم گرافیکی به «{tval['name']}» تغییر کرد.", kb_main_menu())
                return

    # --- زیرمنوی تنظیمات استودیو ویدئو ---
    if is_pure_text and text.startswith(("🖼️ قاب ریلز مخزن:", "🧬 اصالت‌سازی", "👤 ردیابی چهره", "🏷️ اند-اسکرین")):
        if text.startswith("🖼️ قاب ریلز مخزن:"):
            CONFIG["use_repo_frame"] = not CONFIG["use_repo_frame"]
        elif text.startswith("🧬 اصالت‌سازی"):
            CONFIG["video_antidup"] = not CONFIG["video_antidup"]
        elif text.startswith("👤 ردیابی چهره"):
            CONFIG["video_facetrack"] = not CONFIG["video_facetrack"]
        elif text.startswith("🏷️ اند-اسکرین"):
            CONFIG["video_brand"] = not CONFIG["video_brand"]
        await save_config_to_pin(session)
        USER_STATE[chat_id] = {"mode": "video_studio", "step": "wait_video"}
        await send_message(session, chat_id, "✅ تنظیم ذخیره شد. حالا ویدئوی خود را بفرستید:", kb_video_studio())
        return

    # --- پردازش ورودی‌های کاربر در هر حالت ---
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
        badge, hl = await extract_short_headline(session, text)
        card_p = await asyncio.to_thread(render_news_card_sync, photo_path, badge, hl, "", fmt, CONFIG["theme"])
        await send_photo_file(session, chat_id, card_p, caption="🖼️ کارت آماده انتشار")
        cap = await generate_editorial_caption(
            session,
            news_text=text,
            media_path=photo_path or None,
            mime_type="image/jpeg" if photo_path else None,
        )
        await send_caption_with_shield(session, chat_id, cap)
        add_to_daily_items(hl, photo_path, tag=badge)
        return

    if mode == "incident":
        USER_STATE.pop(chat_id, None)
        photo_path = ""
        if msg.get("photo"):
            photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg")
        if not photo_path and not text:
            await send_message(session, chat_id, "❌ عکس و متن خبر حادثه‌ای را بفرستید.", kb_main_menu())
            return
        await send_message(session, chat_id, "🚨 در حال ساخت ریلز اضطراری حادثه‌ای (حدود ۲۰ ثانیه)...", kb_main_menu())
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
            await send_message(session, chat_id, f"🗺️ در حال دریافت نقشه «{loc}» و ساخت ریلز زوم سینمایی...", kb_main_menu())
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
        await send_message(session, chat_id, "🎞️ در حال تدوین هوشمند ویدئو و اعمال قاب ریلز (حدود ۳۰ تا ۶۰ ثانیه)...", kb_main_menu())
        vid_path = await download_tg_file(session, vid["file_id"], ".mp4")
        spawn_bg_task(run_video_studio_job(session, chat_id, vid_path, text))
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
