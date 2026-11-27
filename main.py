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
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB").strip()
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
VIRAL_DAILY_BATCH_PROMPT = """تو سردبیر ارشد و کارگردان ریلزهای وایرال خبری در اینستاگرام برای پیج @ShirazLastNews هستی.
لیست خبرهای زیر را بررسی کن و خروجی را فقط و فقط به صورت یک JSON معتبر (بدون مارک‌داون و بدون توضیح اضافه) با این ساختار دقیق تحویل بده:
{
  "items": [
    {
      "display_headline": "تیتر کوتاه، تمیز و کوبنده برای چاپ روی تصویر (حداکثر ۱۰ کلمه، کاملاً بدون علامت‌های ؛/ یا / یا | یا ایموجی)",
      "highlight_words": ["کلمه_کلیدی_۱", "کلمه_کلیدی_۲"],
      "spoken_text": "متن گفتاری کوتاه، طبیعی، روان و مخصوص گویندگی تلویزیون (حداکثر ۱۳ کلمه، بدون علائم خبرگزاری، با ویرگول برای مکث و اعراب دقیق فقط روی کلمات حساس و اسامی خاص مثل بَیضا، مُهِم‌ترین، خَبَرِ فوری، مَعالی‌آباد)"
    }
  ],
  "outro_question": "یک سؤال کوتاه، جذاب و کامنت‌گیر درباره داغ‌ترین خبر این بسته برای پایان ریلز (حداکثر ۱۰ کلمه، با ایموجی ننویس)"
}

قواعد اجباری:
- تعداد اعضای آرایه items باید دقیقاً برابر تعداد خبرهای ورودی و به همان ترتیب باشد.
- در display_headline هرگز علامت «/» یا «؛/» یا «|» نگذار و جمله را کامل و شفاف بنویس.
- در highlight_words دقیقاً ۲ تا ۳ کلمه مهم از داخل خودِ display_headline انتخاب کن که دقیقاً با همان املا در display_headline وجود داشته باشند.
- در spoken_text شماره خبر ننویس (شماره خبر به‌صورت خودکار اضافه می‌شود)، اما جمله را طوری بنویس که گوینده بسیار طبیعی، روان و پرانرژی آن را بخواند."""

DEFAULT_PRONUNCIATION_DICT = {
    "خبر فوری": "خَبَرِ فوری",
    "آخرین خبرهای": "آخَرین خَبَرهایِ",
    "خبرهای": "خَبَرهای",
    "خبر": "خَبَر",
    "مهم‌ترین": "مُهِم‌ترین",
    "مهمترین": "مُهِم‌ترین",
    "بیضا": "بَیضا",
    "بیضای": "بَیضایِ",
    "شهرستان بیضا": "شَهرِستانِ بَیضا",
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
    "شهرستان ممسنی": "شَهرِستانِ مَمَسَنی",
    "نورآباد ممسنی": "نورآبادِ مَمَسَنی",
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
    "صعود": "صُعود",
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
        cands = ("incident.wav", "incident.mp3", "sounds/incident.wav", "sounds/incident.mp3")
    elif mode == "hologram":
        cands = ("hologram.wav", "hologram.mp3", "sounds/hologram.wav", "sounds/hologram.mp3", "daily.wav", "news.wav")
    elif mode == "kinetic":
        cands = ("daily.wav", "daily.mp3", "sounds/daily.wav", "sounds/daily.mp3", "news.wav", "news.mp3")
    else:
        cands = ("news.wav", "news.mp3", "sounds/news.wav", "sounds/news.mp3", "daily.wav", "daily.mp3")
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


def smart_truncate_words(text: str, max_chars: int = 96) -> str:
    """کوتاه‌سازی ایمن روی مرز جمله یا کلمه بدون رها شدن حروف اضافه معلق (مثل با، در، از، و) در انتهای تیتر."""
    t = re.sub(r"\s+", " ", (text or "")).strip()
    if len(t) <= max_chars:
        return t

    # اولویت ۱: برش در پایان بخش کامل جمله (؛ یا . یا —) تا معنا کاملاً تمام‌شده بماند
    head = t[:max_chars]
    for sep in ("؛", ".", "—", "،"):
        pos = head.rfind(sep)
        if pos >= int(max_chars * 0.48):
            cut = head[:pos].strip(" ،؛:-—/|")
            words = cut.split()
            while len(words) > 2 and words[-1].strip("،.؛:!؟«»") in HOOK_FORBIDDEN_END_WORDS:
                words.pop()
            if words:
                return " ".join(words)

    # اولویت ۲: برش روی مرز کلمه + حذف خودکار حروف اضافه معلق از انتهای جمله
    cut = head.rsplit(" ", 1)[0].strip(" ،؛:-—/|")
    words = cut.split()
    while len(words) > 2 and words[-1].strip("،.؛:!؟«»") in HOOK_FORBIDDEN_END_WORDS:
        words.pop()
    return " ".join(words) if words else head.strip()


def add_to_daily_items(headline: str, photo_path: str = None, tag: str = "خبر", exact_lock: bool = False) -> dict:
    clean_hl = sanitize_display_headline(headline) if "sanitize_display_headline" in globals() else strip_emojis_for_font(headline)
    if "|" in clean_hl:
        clean_hl = clean_hl.split("|", 1)[1].strip()
    saved_img = None
    if photo_path and os.path.exists(photo_path):
        saved_img = os.path.join(TMP_ROOT, f"daily_{int(time.time())}_{len(DAILY_ITEMS)}.jpg")
        try:
            shutil.copy(photo_path, saved_img)
        except Exception:
            saved_img = None
    item = {
        "id": f"{int(time.time() * 1000) % 1000000}{random.randint(10, 99)}",
        "headline": smart_truncate_words(clean_hl, 320),
        "photo": saved_img,
        "tag": strip_emojis_for_font(tag) or "شیراز",
        "time": get_tehran_now().strftime("%H:%M"),
        "exact_lock": exact_lock,
    }
    DAILY_ITEMS.append(item)
    if len(DAILY_ITEMS) > 10:
        old = DAILY_ITEMS.pop(0)
        if old.get("photo") and os.path.exists(old["photo"]):
            try:
                os.remove(old["photo"])
            except Exception:
                pass
    return item


def kb_daily_item_inline(item_id: str, approved: bool = False) -> dict:
    if approved:
        return {
            "inline_keyboard": [
                [{"text": "✏️ ویرایش مجدد متن", "callback_data": f"di_edit:{item_id}"}, {"text": "🗑️ حذف از صف", "callback_data": f"di_del:{item_id}"}],
            ]
        }
    return {
        "inline_keyboard": [
            [{"text": "✅ تایید همین متن", "callback_data": f"di_ok:{item_id}"}, {"text": "✏️ اصلاح متن خبر", "callback_data": f"di_edit:{item_id}"}],
            [{"text": "🗑️ حذف این خبر از صف", "callback_data": f"di_del:{item_id}"}],
        ]
    }


def format_daily_item_card(item: dict) -> str:
    idx_num = next((i + 1 for i, it in enumerate(DAILY_ITEMS) if it.get("id") == item.get("id")), len(DAILY_ITEMS))
    hl = item.get("headline", "")
    char_cnt = len(hl)
    word_cnt = len(hl.split())
    status_line = "✅ وضعیت: تایید و قفل‌شده (عیناً نمایش و خوانده می‌شود)" if item.get("exact_lock") else "⏳ وضعیت: در انتظار تایید یا اصلاح شما"
    len_hint = "✅ طول متن عالی برای کادر" if char_cnt <= 95 else "⚠️ متن کمی طولانی است؛ پیشنهاد می‌شود کوتاه‌ترش کنید"
    return (
        f"📌 خبر شماره {to_persian_digits(str(idx_num))} در صف جمع‌بندی\n"
        f"{status_line}\n\n"
        f"📝 متن فعلی:\n«{hl}»\n\n"
        f"🔢 {to_persian_digits(str(char_cnt))} کاراکتر ({to_persian_digits(str(word_cnt))} کلمه) — {len_hint}"
    )


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
    """تطبیق هوشمند بانک تلفظ حتی در صورت وجود اعراب ناقص روی کلمات."""
    merged = dict(DEFAULT_PRONUNCIATION_DICT)
    merged.update(CONFIG.get("custom_pronunciations") or {})
    if not merged or not text:
        return text
    diac_re = re.compile(r"[\u064b-\u0652\u0670]+")
    diac_pat = r"[\u064b-\u0652\u0670]*"
    norm_map = {}
    for k, v in merged.items():
        nk = diac_re.sub("", k).strip()
        if nk:
            norm_map[nk] = v
    keys_sorted = sorted(norm_map.keys(), key=len, reverse=True)
    patterns = [r"(?<![\u0600-\u06FF])" + diac_pat.join(re.escape(ch) for ch in k) for k in keys_sorted]
    combined = re.compile("|".join(patterns))

    def _repl(m):
        raw_hit = diac_re.sub("", m.group(0))
        return norm_map.get(raw_hit, m.group(0))

    return combined.sub(_repl, text)


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


def sanitize_display_headline(text: str) -> str:
    """حذف کامل علائم خام خبرگزاری‌ها (؛/ و / و |) و تمیزسازی تیتر برای چاپ و خوانش."""
    if not text:
        return ""
    t = strip_emojis_for_font(text)
    t = re.sub(r"\s*[؛;]\s*/\s*", "؛ ", t)
    t = re.sub(r"\s*/\s*[؛;]\s*", "؛ ", t)
    t = re.sub(r"\s*/\s*", " — ", t)
    t = re.sub(r"\s*\|\s*", "؛ ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ؛،-—/|:")
    return t


async def prepare_viral_daily_editorial(session: aiohttp.ClientSession, items: list) -> dict:
    """آماده‌سازی تیترها و کلمات کلیدی؛ برای خبرهای تایید/اصلاح‌شده دقیقاً همان متن کاربر بدون تغییر حفظ می‌شود."""
    selected = items[:8]

    def finalize_complete_sentence(s: str, limit: int = 120) -> str:
        t = smart_truncate_words(sanitize_display_headline(s), limit)
        words = t.split()
        while len(words) > 2 and words[-1].strip("،.؛:!؟«»") in HOOK_FORBIDDEN_END_WORDS:
            words.pop()
        return " ".join(words) if words else t

    fallback_items = []
    for it in selected:
        raw_hl = sanitize_display_headline(it.get("headline", "")) or BRAND_TITLE_FA
        hl = raw_hl if it.get("exact_lock") else (finalize_complete_sentence(raw_hl, 95) or BRAND_TITLE_FA)
        words = [w.strip("،.؛:!؟«»") for w in hl.split() if len(w.strip("،.؛:!؟«»")) >= 3]
        fallback_items.append({
            "display_headline": hl,
            "highlight_words": words[:2],
            "spoken_text": apply_pronunciation_dict(hl),
        })
    fallback = {
        "items": fallback_items,
        "outro_question": "کدوم خبر امروز مهم‌تر بود؟ شماره‌شو کامنت کن!",
    }
    if not GEMINI_API_KEY or not selected:
        return fallback

    numbered_lines = []
    for i, it in enumerate(selected):
        txt = sanitize_display_headline(it.get("headline", ""))
        lock_tag = " [متن تاییدشده و قفل کاربر - بدون تغییر کلمات]" if it.get("exact_lock") else ""
        numbered_lines.append(f"{i + 1}. {txt}{lock_tag}")
    numbered = "\n".join(numbered_lines)

    extra_rules = (
        "\nقواعد تکمیلی اجباری:\n"
        "- برای هر خبری که برچسب [متن تاییدشده و قفل کاربر] دارد، display_headline باید ۱۰۰٪ عیناً همان متن باشد و در spoken_text فقط روی همان کلمات اعراب‌گذاری دقیق انجام بده و هیچ کلمه‌ای کم یا زیاد نکن.\n"
        "- برای سایر خبرها اگر متن طولانی است، آن را به یک جمله کاملاً تمام‌شده (۷ تا ۱۲ کلمه) خلاصه کن و هرگز با حرف اضافه معلق (با، در، از، به، و، را، که) تمام نکن."
    )
    raw = await gemini_generate(session, f"{VIRAL_DAILY_BATCH_PROMPT}{extra_rules}\n\nخبرهای امروز:\n{numbered}")
    if not raw:
        return fallback

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return fallback
    try:
        parsed = json.loads(m.group(0))
        p_items = parsed.get("items") or []
        out_items = []
        for idx, fb in enumerate(fallback_items):
            is_locked = bool(selected[idx].get("exact_lock"))
            if idx < len(p_items) and isinstance(p_items[idx], dict):
                kws = [strip_emojis_for_font(str(k)).strip("،.؛:!؟«»") for k in (p_items[idx].get("highlight_words") or []) if str(k).strip()]
                if is_locked:
                    # قفل قطعی روی متن تاییدشده کاربر (هم در تصویر و هم در گفتار)
                    d_hl = fb["display_headline"]
                    sp_cand = sanitize_display_headline(str(p_items[idx].get("spoken_text", "")))
                    # فقط در صورتی spoken_text هوش مصنوعی پذیرفته می‌شود که طولش هم‌اندازه متن کاربر باشد (صرفاً اعراب‌گذاری کرده باشد)
                    sp = apply_pronunciation_dict(sp_cand) if (sp_cand and abs(len(sp_cand.split()) - len(d_hl.split())) <= 1) else fb["spoken_text"]
                else:
                    d_hl = finalize_complete_sentence(str(p_items[idx].get("display_headline", "")), 115) or fb["display_headline"]
                    sp = apply_pronunciation_dict(finalize_complete_sentence(str(p_items[idx].get("spoken_text", "")), 150) or d_hl)
                out_items.append({
                    "display_headline": d_hl,
                    "highlight_words": kws[:3] if kws else fb["highlight_words"],
                    "spoken_text": sp,
                })
            else:
                out_items.append(fb)
        outro_q = finalize_complete_sentence(str(parsed.get("outro_question", "")), 78) or fallback["outro_question"]
        return {"items": out_items, "outro_question": outro_q}
    except Exception:
        return fallback


async def _tts_via_elevenlabs(session: aiohttp.ClientSession, text: str, raw_out: str) -> bool:
    if not ELEVENLABS_API_KEY:
        return False
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.78, "style": 0.35},
    }
    try:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=35)) as resp:
            if resp.status == 200:
                data = await resp.read()
                if len(data) > 1000:
                    with open(raw_out, "wb") as f:
                        f.write(data)
                    return True
    except Exception:
        pass
    return False


async def _tts_via_gemini_native(session: aiohttp.ClientSession, text: str, raw_wav_out: str, is_female: bool = False) -> bool:
    """تولید کل گویندگی در یک درخواست واحد Gemini Native TTS (سریع و بدون گیر کردن در صف 429)."""
    if not GEMINI_API_KEY:
        return False
    voice_name = "Kore" if is_female else "Charon"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={GEMINI_API_KEY}"
    styled_prompt = (
        "Read the following Persian TV news bulletin in a crisp, natural, energetic Iranian news anchor voice. "
        "Pronounce every Persian word and Fars place name accurately according to diacritics (e.g. مَمَسَنی, بَیضا, خَبَر). "
        "Leave a clear 1-second silent pause wherever there is a blank line between paragraphs:\n\n"
        f"{text}"
    )
    body = {
        "contents": [{"parts": [{"text": styled_prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}},
        },
    }
    backoffs = [5.0, 10.0]
    for attempt in range(len(backoffs) + 1):
        try:
            async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=75)) as resp:
                if resp.status in (429, 503):
                    if attempt < len(backoffs):
                        await asyncio.sleep(backoffs[attempt])
                        continue
                    return False
                if resp.status != 200:
                    return False
                data = await resp.json()
                cands = data.get("candidates") or []
                if not cands:
                    return False
                for p in (cands[0].get("content", {}).get("parts") or []):
                    inline = p.get("inlineData") or p.get("inline_data")
                    if inline and inline.get("data"):
                        raw_bytes = base64.b64decode(inline["data"])
                        if len(raw_bytes) < 400:
                            return False
                        mime = (inline.get("mimeType") or inline.get("mime_type") or "").lower()
                        if "wav" in mime or "mp3" in mime or "mpeg" in mime or "ogg" in mime:
                            with open(raw_wav_out, "wb") as f:
                                f.write(raw_bytes)
                            return True
                        sr_m = re.search(r"rate=(\d+)", mime)
                        sr = int(sr_m.group(1)) if sr_m else 24000
                        with wave.open(raw_wav_out, "wb") as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(sr)
                            wf.writeframes(raw_bytes)
                        return True
        except Exception:
            if attempt < 1:
                await asyncio.sleep(2.0)
    return False


async def synthesize_broadcast_tts(
    session: aiohttp.ClientSession,
    raw_text: str,
    out_wav: str,
    work_dir: str,
    already_diacritized: bool = False,
    lock_engine: str = "",
) -> tuple:
    """تولید صدای یکدست گوینده خبری با قفل موتور صوتی (هرگز وسط ویدیو صدای گوینده عوض نمی‌شود)."""
    diac_text = apply_pronunciation_dict(raw_text) if already_diacritized else await diacritize_persian_for_tts(session, raw_text)
    is_female = CONFIG.get("tts_profile") == "studio_anchor_f"
    raw_in = os.path.join(work_dir, f"tts_src_{int(time.time()*1000)}_{random.randint(10,99)}.wav")
    engine_used = ""

    # اگر موتور قفل شده، فقط از همان موتور برای تمام اسلایدها استفاده می‌کنیم تا صدا دوگانه نشود
    if (not lock_engine or lock_engine == "ElevenLabs") and ELEVENLABS_API_KEY:
        if await _tts_via_elevenlabs(session, diac_text, raw_in):
            engine_used = "ElevenLabs"

    if not engine_used and (not lock_engine or lock_engine == "Gemini TTS") and GEMINI_API_KEY:
        if await _tts_via_gemini_native(session, diac_text, raw_in, is_female=is_female):
            engine_used = "Gemini TTS"

    if not engine_used and (not lock_engine or lock_engine == "پشتیبان صوتی") and HAS_EDGE_TTS and edge_tts is not None:
        raw_mp3 = os.path.join(work_dir, f"tts_fb_{int(time.time()*1000)}_{random.randint(10,99)}.mp3")
        v_name = "fa-IR-DilaraNeural" if is_female else "fa-IR-FaridNeural"
        try:
            await edge_tts.Communicate(diac_text, voice=v_name, rate="+2%", pitch="+0Hz").save(raw_mp3)
            if os.path.exists(raw_mp3) and os.path.getsize(raw_mp3) > 500:
                raw_in = raw_mp3
                engine_used = "پشتیبان صوتی"
        except Exception:
            pass

    if not engine_used or not os.path.exists(raw_in):
        return 0.0, ""

    dsp_chain = (
        "aresample=44100,"
        "silenceremove=start_periods=1:start_duration=0.04:start_threshold=-42dB,"
        "highpass=f=90,"
        "equalizer=f=240:t=q:w=1.2:g=-1.8,"
        "equalizer=f=3200:t=q:w=1.3:g=2.0,"
        "acompressor=threshold=-17dB:ratio=2.4:attack=12:release=130,"
        "loudnorm=I=-15:TP=-1.5:LRA=8"
    )
    try:
        run_ffmpeg([
            "ffmpeg", "-y", "-i", raw_in,
            "-af", dsp_chain,
            "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", out_wav,
        ])
        return probe_audio_duration(out_wav), engine_used
    except Exception:
        return 0.0, ""
        

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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        for attempt in range(2):
            try:
                async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                    if resp.status in (429, 503) and attempt == 0:
                        await asyncio.sleep(5.5)
                        continue
                    if resp.status == 200:
                        data = await resp.json()
                        cands = data.get("candidates", [])
                        if cands:
                            out = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", [])).strip()
                            if out:
                                return clean_caption_markdown(out)
                    break
            except Exception:
                break
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


# ==================== ۴. موتور وایرال ۶ سبکی ریلز جمع‌بندی (گویندگی یکدست Gemini TTS فقط در سبک ۶) ====================
def build_mastered_reel_audio_sync(
    work_dir: str,
    total_sec: float,
    cut_times: list,
    mode: str = "news",
    voice_wav: str = "",
) -> tuple:
    """مسترینگ صدای ریلز: موزیک پس‌زمینه + افکت هوای سینمایی Whoosh (بدون صدای قطره آب) + داکینگ خودکار زیر صدای گوینده."""
    sr = 44100
    n_samples = max(sr, int(round(total_sec * sr)))
    bg_src = get_audio_track(work_dir, total_sec + 2.0, mode=mode)
    bg_wav = os.path.join(work_dir, "bg_decoded.wav")
    run_ffmpeg([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", bg_src,
        "-t", f"{total_sec:.3f}", "-ar", str(sr), "-ac", "2", "-c:a", "pcm_s16le", bg_wav,
    ])

    def read_stereo_float(path: str, target_n: int) -> np.ndarray:
        with wave.open(path, "rb") as wf:
            raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
            ch = wf.getnchannels()
        arr = np.stack([raw, raw], axis=-1) if ch == 1 else raw.reshape(-1, ch)[:, :2]
        if len(arr) < target_n:
            arr = np.vstack([arr, np.zeros((target_n - len(arr), 2), dtype=np.float32)])
        return arr[:target_n]

    bg_arr = read_stereo_float(bg_wav, n_samples)

    # افکت صوتی حرفه‌ای Whoosh برودکست (فقط هوای گذرا + بیس بسیار نرم 68Hz به 40Hz؛ بدون هیچ صدای قطره آب)
    w_len = int(0.28 * sr)
    wt = np.linspace(0.0, 0.28, w_len, endpoint=False, dtype=np.float32)
    rng = np.random.default_rng(19)
    raw_n = rng.normal(0.0, 1.0, w_len).astype(np.float32)
    lp_wide = np.convolve(raw_n, np.ones(26, dtype=np.float32) / 26.0, mode="same")
    lp_narrow = np.convolve(raw_n, np.ones(110, dtype=np.float32) / 110.0, mode="same")
    air_whoosh = (lp_wide - lp_narrow) * (np.sin(np.pi * (wt / 0.28)) ** 1.8) * 1.45
    freq_sweep = 68.0 - 28.0 * (wt / 0.28)
    sub_thump = 0.22 * np.sin(2.0 * np.pi * np.cumsum(freq_sweep) / sr) * np.exp(-wt * 14.0)
    sfx_mono = (air_whoosh + sub_thump) * 0.34
    sfx_stereo = np.stack([sfx_mono, sfx_mono], axis=-1)

    if voice_wav and os.path.exists(voice_wav):
        v_arr = read_stereo_float(voice_wav, n_samples)
        v_abs = np.max(np.abs(v_arr), axis=1)
        win = int(0.18 * sr)
        v_env = np.convolve(v_abs, np.ones(win, dtype=np.float32) / win, mode="same")
        duck_gain = np.where(v_env > 0.015, 0.16, 0.36).astype(np.float32)
        s_win = int(0.12 * sr)
        duck_gain = np.convolve(duck_gain, np.ones(s_win, dtype=np.float32) / s_win, mode="same")[:, None]
        mix = v_arr * 1.15 + bg_arr * duck_gain
        eq_source = v_abs
    else:
        mix = bg_arr * 0.68
        eq_source = np.max(np.abs(bg_arr), axis=1)

    for ct in cut_times:
        idx0 = int(max(0, (ct - 0.14) * sr))
        idx1 = min(n_samples, idx0 + w_len)
        if idx1 > idx0:
            mix[idx0:idx1] += sfx_stereo[:idx1 - idx0]

    fade_n = min(int(0.35 * sr), n_samples // 4)
    if fade_n > 0:
        mix[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)[:, None]

    mix = np.tanh(mix * 0.96) * 0.94
    out_wav = os.path.join(work_dir, "master_reel_audio.wav")
    pcm = (np.clip(mix, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

    fps = 25
    n_frames = max(1, int(math.ceil(total_sec * fps)))
    hop = max(1, sr // fps)
    energies = []
    for fi in range(n_frames):
        s0 = fi * hop
        s1 = min(n_samples, s0 + hop)
        val = float(np.sqrt(np.mean(eq_source[s0:s1] ** 2))) if s1 > s0 else 0.0
        energies.append(min(1.0, val * 4.5))
    return out_wav, energies


def detect_narration_segment_durs(wav_path: str, scripts: list) -> list:
    """تشخیص خودکار مکث‌های طبیعی بین خبرها در یک فایل صوتی پیوسته برای سینک دقیق هر اسلاید."""
    n_segs = len(scripts)
    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    mono = raw if ch == 1 else np.mean(raw.reshape(-1, ch), axis=1)
    total_dur = len(mono) / float(sr)
    if n_segs <= 1 or total_dur <= 1.0:
        return [max(1.0, total_dur)]

    hop = max(1, int(0.02 * sr))
    n_win = len(mono) // hop
    if n_win < 10:
        return [total_dur / n_segs] * n_segs

    rms = np.sqrt(np.mean(mono[:n_win * hop].reshape(n_win, hop) ** 2, axis=1))
    rms = np.convolve(rms, np.ones(4, dtype=np.float32) / 4.0, mode="same")
    thresh = max(0.012, float(np.percentile(rms, 20)) * 2.2)
    is_quiet = rms < thresh

    pauses = []
    in_q, q_start = False, 0
    for idx, q in enumerate(is_quiet):
        if q and not in_q:
            in_q, q_start = True, idx
        elif not q and in_q:
            in_q = False
            dur_q = (idx - q_start) * 0.02
            if dur_q >= 0.16:
                pauses.append(((q_start + idx) * 0.01, dur_q))
    if in_q:
        dur_q = (len(is_quiet) - q_start) * 0.02
        if dur_q >= 0.16:
            pauses.append(((q_start + len(is_quiet)) * 0.01, dur_q))

    weights = [max(12, len(s)) + 10 for s in scripts]
    tot_w = float(sum(weights))
    min_seg = min(1.4, total_dur / (n_segs * 1.6))

    cuts = [0.0]
    cum_w = 0.0
    for k in range(1, n_segs):
        cum_w += weights[k - 1]
        exp_t = total_dur * (cum_w / tot_w)
        rem_min = min_seg * (n_segs - k)
        w_lo = max(cuts[-1] + min_seg, exp_t - max(2.4, total_dur * 0.11))
        w_hi = min(total_dur - rem_min, exp_t + max(2.4, total_dur * 0.11))
        if w_hi <= w_lo:
            best_t = max(cuts[-1] + 0.5, min(total_dur - 0.5 * (n_segs - k), exp_t))
        else:
            cands = [(mid, dur_q) for (mid, dur_q) in pauses if w_lo <= mid <= w_hi]
            if cands:
                best_t = max(cands, key=lambda x: x[1] * 3.5 - abs(x[0] - exp_t) * 0.45)[0]
            else:
                i0 = max(0, min(len(rms) - 1, int(w_lo / 0.02)))
                i1 = max(i0 + 1, min(len(rms), int(w_hi / 0.02)))
                best_t = (i0 + int(np.argmin(rms[i0:i1]))) * 0.02
        cuts.append(best_t)
    cuts.append(total_dur)
    return [max(0.8, cuts[i + 1] - cuts[i]) for i in range(n_segs)]


async def prepare_hologram_narration_audio(session: aiohttp.ClientSession, items: list, editorial: dict, work_dir: str) -> dict:
    """تولید کل گویندگی سبک ۶ در یک درخواست واحد (حدود ۱۵ ثانیه) بدون محدودیت 429 و با صدای کاملاً یکدست."""
    ed_items = editorial.get("items") or []
    ordinals = ["خَبَرِ اوّل؛", "خَبَرِ دُوُم؛", "خَبَرِ سِوُم؛", "خَبَرِ چَهارُم؛", "خَبَرِ پَنجُم؛", "خَبَرِ شِشُم؛", "خَبَرِ هَفتُم؛", "خَبَرِ هَشتُم؛"]

    scripts = ["شَصت ثانیِه با مُهِم‌ترین اَخبار!"]
    for idx, ed in enumerate(ed_items):
        ord_p = ordinals[idx] if idx < len(ordinals) else f"خَبَرِ {idx + 1}؛"
        sp = apply_pronunciation_dict(ed.get("spoken_text") or ed.get("display_headline") or "")
        scripts.append(f"{ord_p} {sp}.")
    scripts.append("بَرایِ مُهِم‌ترین خَبَرهایِ ایران و شیراز فالو کُنید.")

    # ترکیب کل متن در یک درخواست واحد با فاصله پاراگراف برای مکث طبیعی بین خبرها
    combined_script = "\n\n".join(scripts)
    voice_full = os.path.join(work_dir, "voice_full.wav")
    dur_total, eng = await synthesize_broadcast_tts(
        session, combined_script, voice_full, work_dir, already_diacritized=True
    )

    if dur_total > 1.5 and os.path.exists(voice_full):
        seg_durs = await asyncio.to_thread(detect_narration_segment_durs, voice_full, scripts)
        return {"voice_wav": voice_full, "durs": seg_durs, "narrated": True, "engine": eng}

    def_durs = [2.1] + [3.8 for _ in ed_items] + [2.6]
    return {"voice_wav": "", "durs": def_durs, "narrated": False, "engine": ""}


def _tokenize_line_metrics(draw: ImageDraw.ImageDraw, words: list, font: ImageFont.FreeTypeFont, hw_norm: set, has_pill: bool):
    """محاسبه دقیق پیکسل‌به‌پیکسل عرض کلمات + حاشیه باکس هایلایت (صفر درصد بیرون‌زدگی از کادر)."""
    td_sp1, kw_sp = prepare_text_and_kwargs("ب ب", is_rtl=True)
    td_sp0, _ = prepare_text_and_kwargs("بب", is_rtl=True)
    bb1 = draw.textbbox((0, 0), td_sp1, font=font, **kw_sp)
    bb0 = draw.textbbox((0, 0), td_sp0, font=font, **kw_sp)
    sp_w = max(8, (bb1[2] - bb1[0]) - (bb0[2] - bb0[0]) + 4)

    infos = []
    for w_tok in words:
        td, kw = prepare_text_and_kwargs(w_tok, is_rtl=True)
        bb = draw.textbbox((0, 0), td, font=font, **kw)
        w_w = max(4, bb[2] - bb[0])
        clean_tok = re.sub(r"[،.؛:!؟«»\-—]", "", w_tok).strip()
        is_hl = bool(clean_tok and (clean_tok in hw_norm or any(len(k) >= 3 and k in clean_tok for k in hw_norm)))
        pad = 9 if (is_hl and has_pill) else 0
        infos.append((td, kw, bb, w_w, is_hl, pad))
    total_w = sum(x[3] + 2 * x[5] for x in infos) + sp_w * max(0, len(infos) - 1)
    return infos, sp_w, total_w


def fit_highlighted_text_in_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_kind: str,
    max_width: int,
    max_height: int,
    highlight_words: list,
    has_pill: bool,
    max_size: int = 58,
    min_size: int = 24,
    max_lines: int = 4,
    line_spacing: float = 1.38,
) -> tuple:
    """خط‌شکنی و تنظیم خودکار سایز فونت با محاسبه واقعی عرض کادرهای هایلایت تا هیچ حرفی بریده نشود."""
    clean = strip_emojis_for_font(text).replace("\n", " ")
    all_words = [w for w in clean.split() if w]
    hw_norm = {re.sub(r"[،.؛:!؟«»\-—]", "", str(k)).strip() for k in (highlight_words or []) if str(k).strip()}
    if not all_words:
        return load_font(font_kind, min_size), [], int(min_size * line_spacing)

    for sz in range(max_size, min_size - 1, -2):
        font = load_font(font_kind, sz)
        lines, cur = [], []
        for w_tok in all_words:
            trial = cur + [w_tok]
            _, _, tw = _tokenize_line_metrics(draw, trial, font, hw_norm, has_pill)
            if tw <= max_width or not cur:
                cur = trial
            else:
                lines.append(" ".join(cur))
                cur = [w_tok]
        if cur:
            lines.append(" ".join(cur))
        lh = int(sz * line_spacing)
        if len(lines) <= max_lines and (len(lines) * lh) <= max_height:
            # اطمینان از اینکه هیچ خط منفردی هم از max_width بیشتر نشده باشد
            if all(_tokenize_line_metrics(draw, ln.split(), font, hw_norm, has_pill)[2] <= max_width for ln in lines):
                return font, lines, lh

    font = load_font(font_kind, min_size)
    lines, cur = [], []
    for w_tok in all_words:
        trial = cur + [w_tok]
        _, _, tw = _tokenize_line_metrics(draw, trial, font, hw_norm, has_pill)
        if tw <= max_width or not cur:
            cur = trial
        else:
            lines.append(" ".join(cur))
            cur = [w_tok]
    if cur:
        lines.append(" ".join(cur))
    return font, lines[:max_lines], int(min_size * line_spacing)


def draw_highlighted_rtl_line(
    draw: ImageDraw.ImageDraw,
    anchor_x: int,
    y: int,
    line: str,
    font: ImageFont.FreeTypeFont,
    normal_fill: tuple,
    highlight_fill: tuple,
    highlight_words: list,
    align: str = "right",
    pill_bg: tuple = None,
    shadow: bool = True,
):
    """چاپ خط فارسی با کادرهای هایلایت تمیز و محاسبه دقیق عرض بدون بیرون‌زدگی."""
    words = [w for w in line.split() if w]
    if not words:
        return
    hw_norm = {re.sub(r"[،.؛:!؟«»\-—]", "", str(k)).strip() for k in (highlight_words or []) if str(k).strip()}
    w_infos, sp_w, total_w = _tokenize_line_metrics(draw, words, font, hw_norm, pill_bg is not None)

    if align == "center":
        cursor_x = anchor_x + total_w // 2
    elif align == "left":
        cursor_x = anchor_x + total_w
    else:
        cursor_x = anchor_x

    for td, kw, bb, w_w, is_hl, pad in w_infos:
        draw_x = (cursor_x - pad) - bb[2]
        if is_hl and pill_bg is not None:
            draw.rounded_rectangle(
                [(draw_x + bb[0] - pad, y + bb[1] - 5), (draw_x + bb[2] + pad, y + bb[3] + 7)],
                radius=11,
                fill=pill_bg,
            )
        if shadow:
            draw.text((draw_x + 3, y + 3), td, font=font, fill=(0, 0, 0, 190), **kw)
        draw.text((draw_x, y), td, font=font, fill=(highlight_fill if is_hl else normal_fill), **kw)
        cursor_x -= (w_w + 2 * pad + sp_w)


def build_daily_summary_reel_sync(
    items: list,
    style: str = "broadcast",
    narration_plan: dict = None,
    editorial: dict = None,
) -> str:
    """موتور وایرال ۶ سبکی: صفر درصد بریدگی متن، کنتراست بالا، Whoosh حرفه‌ای، دکمه فالو بدون خطای @ و پس‌زمینه زنده."""
    w, h, fps = 1080, 1920, 25
    work_dir = tempfile.mkdtemp(dir=TMP_ROOT)
    selected = items[:8]
    n_news = max(1, len(selected))

    ed_items = (editorial or {}).get("items") or []
    outro_q = sanitize_display_headline((editorial or {}).get("outro_question", "")) or "کدوم خبر امروز مهم‌تر بود؟ شماره‌شو کامنت کن!"

    TEXT_SAFE_RIGHT = 900

    gw, gh = 135, 240
    gy_grid, gx_grid = np.mgrid[0:gh, 0:gw].astype(np.float32)
    gx_norm, gy_norm = gx_grid / gw, gy_grid / gh

    def make_dark_gradient_bg(t_sec: float, tint_rgb=(196, 22, 34)):
        c1x = 0.25 + 0.18 * math.sin(t_sec * 0.65)
        c1y = 0.28 + 0.14 * math.cos(t_sec * 0.50)
        c2x = 0.78 + 0.16 * math.cos(t_sec * 0.55)
        c2y = 0.76 + 0.12 * math.sin(t_sec * 0.70)
        d1 = np.exp(-((gx_norm - c1x) ** 2 + ((gy_norm - c1y) * 1.45) ** 2) / 0.19)
        d2 = np.exp(-((gx_norm - c2x) ** 2 + ((gy_norm - c2y) * 1.45) ** 2) / 0.24)
        r = np.clip(18.0 + d1 * (tint_rgb[0] * 0.46) + d2 * 28.0, 0, 255)
        g = np.clip(22.0 + d1 * (tint_rgb[1] * 0.46) + d2 * 46.0, 0, 255)
        b = np.clip(32.0 + d1 * (tint_rgb[2] * 0.46) + d2 * 78.0, 0, 255)
        return cv2.resize(np.stack([r, g, b], axis=-1).astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR)

    def make_blurred_ambient_bg(photo_path: str, tint_rgb=(18, 24, 38)) -> np.ndarray:
        """پس‌زمینه زنده و پرنورتر از خود عکس خبر تا نیمه پایین ویدیو هیچ حس تاریکی و خلوتی نداشته باشد."""
        if photo_path and os.path.exists(photo_path):
            sm = fit_cover(Image.open(photo_path).convert("RGB"), 270, 480)
            arr = cv2.GaussianBlur(np.array(sm, dtype=np.uint8), (27, 27), 0)
            tinted = cv2.addWeighted(arr, 0.56, np.full_like(arr, tint_rgb, dtype=np.uint8), 0.44, 0)
            return cv2.resize(tinted, (1188, 2112), interpolation=cv2.INTER_LINEAR)
        return None

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
        arr = np.array(card_pil, dtype=np.uint8)
        ch, cw = arr.shape[:2]
        pad_x, pad_y = 44, 44
        src = np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]])
        dx = math.sin(math.radians(yaw_deg)) * 32.0
        dy = math.sin(math.radians(pitch_deg)) * 20.0
        shrink = abs(math.sin(math.radians(yaw_deg))) * 24.0
        dst = np.float32([
            [pad_x + (shrink if dx > 0 else 0), pad_y + max(0.0, dy)],
            [pad_x + cw - (shrink if dx < 0 else 0), pad_y + max(0.0, -dy)],
            [pad_x + cw - (shrink if dx < 0 else 0), pad_y + ch - max(0.0, -dy)],
            [pad_x + (shrink if dx > 0 else 0), pad_y + ch - max(0.0, dy)],
        ])
        M = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(arr, M, (cw + pad_x * 2, ch + pad_y * 2), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        return Image.fromarray(warped, mode="RGBA")

    def draw_broadcast_wipe(frame_rgba: Image.Image, mode: str, progress: float, accent_rgba=(204, 18, 28, 255)):
        d = ImageDraw.Draw(frame_rgba)
        slant, stripe_w = 240, 82
        charcoal = (16, 18, 24, 255)
        if mode == "in":
            lead_x = int(1360 - 1480 * (progress ** 1.35))
            d.polygon([(lead_x, 0), (lead_x + stripe_w, 0), (lead_x + stripe_w - slant, h), (lead_x - slant, h)], fill=accent_rgba)
            d.polygon([(lead_x + stripe_w, 0), (w + 400, 0), (w + 400, h), (lead_x + stripe_w - slant, h)], fill=charcoal)
        else:
            trail_x = int(1440 - 1520 * (progress ** 0.78))
            d.polygon([(-400, 0), (trail_x - stripe_w, 0), (trail_x - stripe_w - slant, h), (-400, h)], fill=charcoal)
            d.polygon([(trail_x - stripe_w, 0), (trail_x, 0), (trail_x - slant, h), (trail_x - stripe_w - slant, h)], fill=accent_rgba)

    def draw_equalizer(frame_rgba: Image.Image, x: int, y: int, energy: float, t_sec: float, bar_color=(242, 200, 68, 240)):
        ed = ImageDraw.Draw(frame_rgba)
        for bi in range(7):
            phase = abs(math.sin(t_sec * (7.5 + bi * 1.4) + bi * 0.9))
            bh = int(8 + 30 * min(1.0, (0.25 + 0.75 * energy) * (0.45 + 0.55 * phase)))
            bx = x + bi * 11
            ed.rounded_rectangle([(bx, y + 38 - bh), (bx + 6, y + 38)], radius=3, fill=bar_color)

    def draw_progress_bars(frame_rgba: Image.Image, current_idx: int, frac: float, bar_y: int = 202, active_c=(220, 28, 38, 255)):
        pd = ImageDraw.Draw(frame_rgba)
        margin_x, gap, bar_h = 56, 12, 9
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

    def paste_logo(target_rgba, draw_obj, x, y, mw=104, mh=78):
        if logo_img:
            lg = logo_img.copy()
            lg.thumbnail((mw, mh), Image.Resampling.LANCZOS)
            target_rgba.alpha_composite(lg, (x, y))
        else:
            draw_quran_gate_fallback(draw_obj, x, y, min(mw, mh))

    def zoom_pan_slice(arr: np.ndarray, target_w: int, target_h: int, prog: float, zoom_amt: float = 0.09, pan_dir: int = 1):
        ah, aw = arr.shape[:2]
        z = 1.0 + zoom_amt * prog
        cw, ch = int(aw / z), int(ah / z)
        max_shift_x = max(0, (aw - cw) // 2)
        shift_x = int(max_shift_x * 0.45 * (prog - 0.5) * pan_dir)
        x0 = max(0, min(aw - cw, (aw - cw) // 2 + shift_x))
        y0 = max(0, (ah - ch) // 2)
        return cv2.resize(arr[y0:y0 + ch, x0:x0 + cw], (target_w, target_h), interpolation=cv2.INTER_LINEAR)

    # سایه نرم‌تر تا نیمه پایینی ویدیو زنده و خوش‌رنگ باقی بماند
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for y in range(380):
        vd.line([(0, y), (w, y)], fill=(10, 14, 22, int(205 * (1.0 - y / 380.0))))
    for y in range(1040, h):
        vd.line([(0, y), (w, y)], fill=(10, 14, 22, int(200 * (((y - 1040) / (h - 1040)) ** 1.15))))

    now_tehran = get_tehran_now()
    jnow = jdatetime.datetime.fromgregorian(datetime=now_tehran)
    date_str = to_persian_digits(f"{JALALI_WEEKDAYS[jnow.weekday()]} {jnow.day} {JALALI_MONTHS[jnow.month]} {jnow.year}")
    clock_str = to_persian_digits(now_tehran.strftime("%H:%M"))

    cold_photos = []
    for it in selected:
        p = it.get("photo")
        if p and os.path.exists(p):
            cold_photos.append(np.array(fit_cover(Image.open(p).convert("RGB"), 1188, 2112), dtype=np.uint8))
        if len(cold_photos) >= 3:
            break

    # --- مقدمه سریع و کوبنده ---
    intro_box = (64, 445, w - 64, 1055)
    intro_ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(intro_ov)
    accent_intro = (0, 212, 255) if style == "hologram" else (204, 18, 28)
    idraw.rounded_rectangle(intro_box, radius=36, outline=accent_intro + (165,) if style == "hologram" else (255, 255, 255, 76), width=3)
    idraw.rectangle([(w - 90, 495), (w - 78, 1005)], fill=accent_intro + (255,))
    paste_logo(intro_ov, idraw, (w - 135) // 2, 240, 160, 120)
    intro_tag_map = {
        "broadcast": "بسته خبری روزانه", "split": "گزارش تحریریه", "editorial": "پرونده خبری امروز",
        "kinetic": "مرور سریع اخبار", "live": "بولتین زنده خبری", "hologram": "گزارش صوتی و تصویری",
    }
    idraw.polygon([(310, 404), (790, 404), (762, 474), (282, 474)], fill=(204, 18, 28, 255))
    draw_rtl_text(idraw, (536, 416), intro_tag_map.get(style, "بسته خبری روزانه"), load_font("bold", 38), (255, 255, 255, 255), align="center", shadow=False)
    draw_centered_block_in_box(idraw, (96, 505, w - 108, 650), "۶۰ ثانیه با مهم‌ترین اخبار", "display", (255, 255, 255, 255), max_size=84, min_size=50, max_lines=1, align="center", shadow=True)
    draw_rtl_text(idraw, (w // 2, 668), date_str, load_font("bold", 40), (210, 218, 232, 255), align="center", shadow=False)
    idraw.line([(200, 750), (w - 200, 750)], fill=(255, 255, 255, 55), width=2)
    draw_centered_block_in_box(idraw, (96, 775, w - 108, 885), "مرور سریع مهم‌ترین اخبار ایران و شیراز", "bold", (242, 200, 68, 255), max_size=38, min_size=26, max_lines=1, align="center", shadow=False)
    draw_rtl_text(idraw, (w // 2, 926), BRAND_HANDLE, load_font("bold", 36), (205, 212, 224, 255), align="center", shadow=False, is_rtl=False)

    # --- پایان فالوئرگیر با اصلاح ۱۰۰٪ دکمه فالو (جدا کردن LTR و RTL تا @ هرگز جابه‌جا نشود) ---
    outro_box = (64, 410, w - 64, 1175)
    outro_base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(outro_base)
    od.rounded_rectangle(outro_box, radius=36, outline=accent_intro + (155,) if style == "hologram" else (255, 255, 255, 76), width=3)
    paste_logo(outro_base, od, (w - 135) // 2, 225, 155, 118)
    od.rounded_rectangle([(104, 462), (w - 104, 628)], radius=24, fill=(242, 200, 68, 32), outline=(242, 200, 68, 190), width=3)
    draw_rtl_text(od, (w // 2, 476), "نظر شما در کامنت‌ها:", load_font("bold", 28), (242, 200, 68, 255), align="center", shadow=False)
    draw_centered_block_in_box(od, (124, 514, w - 124, 620), outro_q, "bold", (255, 255, 255, 255), max_size=36, min_size=24, max_lines=2, align="center")
    draw_rtl_text(od, (w // 2, 668), BRAND_TITLE_FA, load_font("display", 78), (255, 255, 255, 255), align="center")
    draw_centered_block_in_box(od, (96, 785, w - 96, 912), "برای پیگیری مهم‌ترین خبرهای ایران و شیراز فالو کنید", "bold", (215, 224, 238, 255), max_size=38, min_size=26, max_lines=2, align="center")

    def build_follow_btn(fill_rgba: tuple, border_rgba: tuple, fa_label: str) -> Image.Image:
        lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        bd = ImageDraw.Draw(lay)
        bd.rounded_rectangle([(148, 955), (w - 148, 1085)], radius=28, fill=fill_rgba, outline=border_rgba, width=4)
        # آیدی انگلیسی سمت چپ با جهت LTR دقیق (بدون پریدن علامت @)
        draw_rtl_text(bd, (365, 994), BRAND_HANDLE, load_font("bold", 38), (255, 255, 255, 255), align="center", shadow=False, is_rtl=False)
        bd.line([(578, 982), (578, 1058)], fill=(255, 255, 255, 160), width=3)
        # عبارت فارسی سمت راست با جهت RTL دقیق
        draw_rtl_text(bd, (748, 992), fa_label, load_font("bold", 40), (255, 255, 255, 255), align="center", shadow=False, is_rtl=True)
        return lay

    btn_pre = build_follow_btn((204, 18, 28, 255), (255, 255, 255, 170), "فالو کنید +")
    btn_post = build_follow_btn((22, 163, 74, 255), (255, 255, 255, 225), "دنبال شد ✓")

    if style == "hologram" and narration_plan and len(narration_plan.get("durs", [])) == (len(selected) + 2):
        durs_list = narration_plan["durs"]
        intro_dur, outro_dur = durs_list[0], durs_list[-1]
        item_durs = durs_list[1:-1]
        voice_wav = narration_plan.get("voice_wav", "")
    else:
        intro_dur = 1.6 if style == "kinetic" else 1.9
        outro_dur = 2.4 if style == "kinetic" else 2.7
        item_durs = [3.4 if style == "kinetic" else 4.3 for _ in selected]
        voice_wav = ""

    total_sec = intro_dur + sum(item_durs) + outro_dur
    cut_times = []
    acc = intro_dur
    cut_times.append(acc)
    for d in item_durs:
        acc += d
        cut_times.append(acc)

    audio_path, eq_energies = build_mastered_reel_audio_sync(
        work_dir, total_sec, cut_times,
        mode="hologram" if style == "hologram" else ("kinetic" if style == "kinetic" else "news"),
        voice_wav=voice_wav if style == "hologram" else "",
    )
    out_mp4 = os.path.join(TMP_ROOT, f"viral_daily_{style}_{int(time.time()*1000)}.mp4")

    clean_headlines = []
    for idx, it in enumerate(selected):
        if idx < len(ed_items):
            clean_headlines.append((ed_items[idx]["display_headline"], ed_items[idx].get("highlight_words") or []))
        else:
            hl = sanitize_display_headline(it.get("headline", "")) or BRAND_TITLE_FA
            clean_headlines.append((hl, hl.split()[:2]))

    ticker_strip = None
    if style in ("split", "live"):
        all_hls = "   ●   ".join(h_pair[0] for h_pair in clean_headlines if h_pair[0])
        ticker_strip = build_scrolling_ticker_strip(all_hls, total_sec + 4.0, bg_color=(192, 20, 30, 245) if style == "live" else (24, 28, 38, 245), height=68)

    paper_bg_arr = None
    if style == "editorial":
        rng = np.random.default_rng(42)
        base_p = np.full((h, w, 3), (22, 24, 30), dtype=np.int16)
        noise = rng.integers(-8, 9, size=(h // 2, w // 2, 1), dtype=np.int16)
        paper_bg_arr = np.clip(base_p + cv2.resize(noise.astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)[:, :, None].astype(np.int16), 0, 255).astype(np.uint8)

    particles = []
    if style == "hologram":
        prng = random.Random(77)
        for _ in range(36):
            particles.append((prng.uniform(0, w), prng.uniform(0, h), prng.uniform(24, 70), prng.uniform(3, 7), prng.choice([(0, 232, 255), (255, 206, 54), (240, 56, 72)])))

    def make_line_layers(
        hl_txt: str, hl_words: list, box_w: int, box_h: int, anchor_x: int, top_y: int,
        font_kind: str, max_sz: int, min_sz: int, max_lines: int, align: str,
        normal_c=(255, 255, 255, 255), hl_c=(255, 255, 255, 255), pill_bg=None, canvas_size=(w, h)
    ):
        probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        f_ch, lines, lh = fit_highlighted_text_in_box(
            probe, hl_txt, font_kind, box_w, box_h, hl_words,
            has_pill=(pill_bg is not None), max_size=max_sz, min_size=min_sz, max_lines=max_lines, line_spacing=1.38
        )
        tot_h = len(lines) * lh
        sy = top_y + max(0, (box_h - tot_h) // 2)
        lays = []
        for li, ln in enumerate(lines):
            lay = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
            draw_highlighted_rtl_line(ImageDraw.Draw(lay), anchor_x, sy + li * lh, ln, f_ch, normal_c, hl_c, hl_words, align=align, pill_bg=pill_bg, shadow=True)
            lays.append(lay)
        return lays

    prepared = []
    for idx, item in enumerate(selected, start=1):
        photo_p = item.get("photo")
        has_photo = bool(photo_p and os.path.exists(photo_p))
        tag_txt = strip_emojis_for_font(item.get("tag", "خبر")) or "خبر"
        hl_txt, hl_words = clean_headlines[idx - 1]
        accent_c = get_accent_for_tag(tag_txt)
        t_lbl = to_persian_digits(item.get("time", ""))
        cnt_str = to_persian_digits(f"{idx:02d} / {n_news:02d}")
        amb_bg = make_blurred_ambient_bg(photo_p, (18, 24, 38)) if has_photo else None

        entry = {
            "idx": idx, "tag": tag_txt, "headline": hl_txt, "hl_words": hl_words,
            "accent": accent_c, "time": t_lbl, "cnt": cnt_str, "dur": item_durs[idx - 1],
            "photo_arr": None, "amb_bg": amb_bg,
        }

        if style == "broadcast":
            if has_photo:
                entry["photo_arr"] = np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1240, 2204), dtype=np.uint8)
            cb_w, cb_h = w - 128, 405
            card_chrome = Image.new("RGBA", (cb_w, cb_h), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card_chrome)
            cd.rounded_rectangle([(0, 0), (cb_w - 1, cb_h - 1)], radius=32, outline=(255, 255, 255, 86), width=3)
            safe_r_in = TEXT_SAFE_RIGHT - 64
            cd.rounded_rectangle([(safe_r_in + 10, 30), (safe_r_in + 24, cb_h - 30)], radius=7, fill=accent_c + (255,))
            cd.polygon([(safe_r_in - 270, 24), (safe_r_in - 4, 24), (safe_r_in - 4, 78), (safe_r_in - 294, 78)], fill=accent_c + (255,))
            draw_centered_block_in_box(cd, (safe_r_in - 274, 28, safe_r_in - 8, 74), tag_txt, "bold", (255, 255, 255, 255), max_size=28, min_size=20, max_lines=1)
            if t_lbl:
                draw_rtl_text(cd, (36, 36), f"ساعت {t_lbl}", load_font("regular", 25), (195, 205, 220, 220), align="left", shadow=False)

            # کنتراست بالا: متن سفید شفاف داخل باکس قرمز برند + حاشیه امن چپ و راست (صفر بریدگی)
            line_lays = make_line_layers(
                hl_txt, hl_words, safe_r_in - 74, cb_h - 118, safe_r_in - 22, 92,
                "display", 54, 26, 4, "right", (255, 255, 255, 255), (255, 255, 255, 255),
                pill_bg=accent_c + (235,), canvas_size=(cb_w, cb_h)
            )
            hud_top = Image.new("RGBA", (w, 340), (0, 0, 0, 0))
            hd = ImageDraw.Draw(hud_top)
            paste_logo(hud_top, hd, 56, 228, 102, 76)
            draw_rtl_text(hd, (172, 250), BRAND_HANDLE, load_font("bold", 28), (235, 240, 248, 225), align="left", shadow=True, is_rtl=False)
            hd.rounded_rectangle([(w - 258, 234), (w - 56, 300)], radius=32, fill=(16, 18, 24, 215), outline=(255, 255, 255, 78), width=2)
            hd.ellipse([(w - 98, 255), (w - 74, 279)], fill=accent_c + (255,))
            draw_rtl_text(hd, (w - 178, 248), cnt_str, load_font("bold", 32), (255, 255, 255, 255), align="center", shadow=False, is_rtl=False)
            entry["card_chrome"], entry["line_lays"], entry["hud_top"] = card_chrome, line_lays, hud_top

        elif style == "split":
            if has_photo:
                entry["photo_arr"] = np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1240, 960), dtype=np.uint8)
            static_split = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(static_split)
            for y in range(340):
                sd.line([(0, y), (w, y)], fill=(12, 14, 20, int(208 * (1.0 - y / 340.0))))
            sd.rectangle([(0, 845), (w, 857)], fill=accent_c + (255,))
            paste_logo(static_split, sd, 56, 228, 100, 74)
            sd.rounded_rectangle([(w - 258, 234), (w - 56, 298)], radius=30, fill=(14, 16, 22, 220), outline=(255, 255, 255, 80), width=2)
            draw_rtl_text(sd, (w - 157, 246), cnt_str, load_font("bold", 32), (255, 255, 255, 255), align="center", shadow=False, is_rtl=False)
            sd.polygon([(TEXT_SAFE_RIGHT - 295, 814), (TEXT_SAFE_RIGHT + 14, 814), (TEXT_SAFE_RIGHT + 14, 886), (TEXT_SAFE_RIGHT - 325, 886)], fill=accent_c + (255,))
            draw_centered_block_in_box(sd, (TEXT_SAFE_RIGHT - 295, 818, TEXT_SAFE_RIGHT + 6, 882), tag_txt, "bold", (255, 255, 255, 255), max_size=30, min_size=22, max_lines=1)
            draw_rtl_text(sd, (56, 902), f"{BRAND_HANDLE}  |  {date_str}", load_font("regular", 25), (185, 196, 214, 230), align="left", shadow=False, is_rtl=False)
            sd.line([(56, 948), (TEXT_SAFE_RIGHT + 14, 948)], fill=(255, 255, 255, 48), width=2)
            sd.rectangle([(TEXT_SAFE_RIGHT + 2, 976), (TEXT_SAFE_RIGHT + 14, 1300)], fill=accent_c + (255,))

            line_lays = make_line_layers(
                hl_txt, hl_words, TEXT_SAFE_RIGHT - 100, 330, TEXT_SAFE_RIGHT - 22, 970,
                "display", 58, 26, 4, "right", (255, 255, 255, 255), (255, 255, 255, 255),
                pill_bg=accent_c + (235,), canvas_size=(w, h)
            )
            entry["static_split"], entry["line_lays"] = static_split, line_lays

        elif style == "editorial":
            if has_photo:
                entry["photo_arr"] = np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1060, 650), dtype=np.uint8)
            ed_frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ed = ImageDraw.Draw(ed_frame)
            paste_logo(ed_frame, ed, 64, 226, 96, 72)
            draw_rtl_text(ed, (w - 64, 242), f"پرونده خبری  |  {date_str}", load_font("bold", 28), (225, 216, 196, 240), align="right", shadow=False)
            ed.line([(64, 314), (w - 64, 314)], fill=(225, 216, 196, 115), width=2)
            ed.rounded_rectangle([(TEXT_SAFE_RIGHT - 255, 922), (TEXT_SAFE_RIGHT, 982)], radius=10, fill=accent_c + (255,))
            draw_centered_block_in_box(ed, (TEXT_SAFE_RIGHT - 249, 926, TEXT_SAFE_RIGHT - 6, 978), tag_txt, "bold", (255, 255, 255, 255), max_size=28, min_size=20, max_lines=1)
            draw_rtl_text(ed, (68, 932), cnt_str, load_font("bold", 32), (225, 216, 196, 220), align="left", shadow=False, is_rtl=False)
            ed.line([(64, 1384), (TEXT_SAFE_RIGHT, 1384)], fill=(225, 216, 196, 90), width=2)
            draw_rtl_text(ed, (TEXT_SAFE_RIGHT, 1404), BRAND_TITLE_FA, load_font("bold", 28), (225, 216, 196, 225), align="right", shadow=False)
            draw_rtl_text(ed, (64, 1406), BRAND_HANDLE, load_font("bold", 28), (242, 200, 68, 245), align="left", shadow=False, is_rtl=False)

            hl_lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            hd = ImageDraw.Draw(hl_lay)
            f_ed, ed_lines, ed_lh = fit_highlighted_text_in_box(
                hd, hl_txt, "display", TEXT_SAFE_RIGHT - 96, 355, hl_words,
                has_pill=False, max_size=58, min_size=26, max_lines=4, line_spacing=1.38
            )
            line_rects, cur_y = [], 1005
            for ln in ed_lines:
                t_draw, kw = prepare_text_and_kwargs(ln, is_rtl=True)
                bb = hd.textbbox((0, 0), t_draw, font=f_ed, **kw)
                line_rects.append((max(68, TEXT_SAFE_RIGHT - (bb[2] - bb[0]) - 24), cur_y + int(ed_lh * 0.54), TEXT_SAFE_RIGHT + 4, cur_y + int(ed_lh * 0.86)))
                draw_highlighted_rtl_line(hd, TEXT_SAFE_RIGHT - 8, cur_y, ln, f_ed, (250, 248, 242, 255), (255, 224, 92, 255), hl_words, align="right", pill_bg=None, shadow=True)
                cur_y += ed_lh
            entry["ed_frame"], entry["hl_lay"], entry["line_rects"] = ed_frame, hl_lay, line_rects

        elif style == "kinetic":
            if has_photo:
                entry["photo_arr"] = cv2.convertScaleAbs(np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1280, 2276), dtype=np.uint8), alpha=1.14, beta=-8)
            k_hud = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            kd = ImageDraw.Draw(k_hud)
            kd.rounded_rectangle([(56, 236), (345, 304)], radius=14, fill=accent_c + (248,))
            draw_centered_block_in_box(kd, (64, 240, 337, 300), tag_txt, "bold", (255, 255, 255, 255), max_size=32, min_size=22, max_lines=1)
            draw_rtl_text(kd, (w - 58, 218), to_persian_digits(f"{idx:02d}"), load_font("display", 108), (255, 255, 255, 238), align="right", shadow=True, shadow_offset=6)
            draw_rtl_text(kd, (w // 2, 1408), BRAND_HANDLE, load_font("bold", 32), (255, 255, 255, 235), align="center", shadow=True, is_rtl=False)

            probe = ImageDraw.Draw(Image.new("RGBA", (w, h)))
            fk, k_lines, k_lh = fit_highlighted_text_in_box(probe, hl_txt, "display", 740, 410, hl_words, has_pill=False, max_size=64, min_size=28, max_lines=4, line_spacing=1.40)
            start_y = 950 + (410 - len(k_lines) * k_lh) // 2
            line_layers = []
            for li, ln in enumerate(k_lines):
                lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                ld = ImageDraw.Draw(lay)
                t_draw, kw = prepare_text_and_kwargs(ln, is_rtl=True)
                bb = ld.textbbox((0, 0), t_draw, font=fk, **kw)
                lw, lh_b, ly = bb[2] - bb[0], bb[3] - bb[1], start_y + li * k_lh
                cx_k = w // 2 - 24
                ld.rounded_rectangle([(cx_k - lw // 2 - 30, ly - 10), (cx_k + lw // 2 + 30, ly + lh_b + 24)], radius=14, fill=(accent_c + (245,)) if li == 0 else (12, 14, 18, 240))
                draw_highlighted_rtl_line(ld, cx_k, ly, ln, fk, (255, 255, 255, 255), (255, 224, 52, 255), hl_words, align="center", pill_bg=None, shadow=False)
                line_layers.append(lay)
            entry["k_hud"], entry["line_layers"] = k_hud, line_layers

        elif style == "live":
            if has_photo:
                entry["photo_arr"] = np.array(fit_cover(Image.open(photo_p).convert("RGB"), 1120, 680), dtype=np.uint8)
            live_ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ld = ImageDraw.Draw(live_ov)
            ld.rectangle([(0, 198), (w, 336)], fill=(15, 19, 28, 236))
            ld.rectangle([(0, 330), (w, 338)], fill=(204, 18, 28, 255))
            paste_logo(live_ov, ld, 54, 210, 94, 70)
            ld.rounded_rectangle([(164, 224), (304, 272)], radius=24, fill=(30, 32, 40, 255), outline=(204, 18, 28, 225), width=2)
            draw_rtl_text(ld, (218, 232), "LIVE", load_font("bold", 25), (255, 255, 255, 255), align="left", shadow=False, is_rtl=False)
            ld.rounded_rectangle([(w - 280, 210), (w - 54, 274)], radius=14, fill=(204, 18, 28, 255))
            draw_rtl_text(ld, (w - 167, 220), f"ساعت {clock_str}", load_font("bold", 32), (255, 255, 255, 255), align="center", shadow=False)
            draw_rtl_text(ld, (w - 56, 288), f"{date_str}  |  بولتین خبری", load_font("regular", 24), (205, 214, 228, 235), align="right", shadow=False)

            ld.rounded_rectangle([(60, 360), (w - 60, 920)], radius=24, outline=(255, 255, 255, 92), width=4)
            ld.polygon([(w - 400, 852), (w - 64, 852), (w - 64, 916), (w - 430, 916)], fill=accent_c + (245,))
            draw_centered_block_in_box(ld, (w - 395, 856, w - 70, 912), f"{tag_txt}  |  {cnt_str}", "bold", (255, 255, 255, 255), max_size=26, min_size=20, max_lines=1)

            ld.rounded_rectangle([(60, 948), (w - 60, 1318)], radius=24, fill=(18, 24, 36, 238), outline=(255, 255, 255, 72), width=3)
            ld.rectangle([(TEXT_SAFE_RIGHT + 4, 976), (TEXT_SAFE_RIGHT + 18, 1290)], fill=accent_c + (255,))
            line_lays = make_line_layers(
                hl_txt, hl_words, TEXT_SAFE_RIGHT - 110, 320, TEXT_SAFE_RIGHT - 22, 972,
                "display", 54, 26, 4, "right", (255, 255, 255, 255), (255, 255, 255, 255),
                pill_bg=accent_c + (235,), canvas_size=(w, h)
            )
            entry["live_ov"], entry["line_lays"] = live_ov, line_lays

        else:  # style == "hologram" (سبک ۶: کنتراست شفاف سفید روی باکس قرمز + نشان خبر ۰۱ + حاشیه امن بدون بریدگی)
            neon_c = (0, 226, 255) if (idx % 2 == 1) else (255, 198, 42)
            entry["neon"] = neon_c
            card_w, card_h = 850, 990
            if has_photo:
                entry["photo_arr"] = np.array(fit_cover(Image.open(photo_p).convert("RGB"), 920, 620), dtype=np.uint8)

            holo_chrome = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
            hcd = ImageDraw.Draw(holo_chrome)
            hcd.rounded_rectangle([(0, 0), (card_w - 1, card_h - 1)], radius=34, fill=(12, 18, 30, 222), outline=neon_c + (235,), width=5)
            photo_hole_mask = Image.new("L", (card_w - 44, 515), 0)
            ImageDraw.Draw(photo_hole_mask).rounded_rectangle([(0, 0), (card_w - 45, 514)], radius=24, fill=255)
            hcd.rounded_rectangle([(22, 22), (card_w - 22, 537)], radius=24, outline=neon_c + (185,), width=3)

            # برچسب دسته خبر (راست) + نشان مرتب «خبر ۰۱» داخل کپسول (چپ — دیگر شبیه «خبرا» نمی‌شود)
            hcd.rounded_rectangle([(card_w - 295, 560), (card_w - 34, 618)], radius=14, fill=accent_c + (250,))
            draw_centered_block_in_box(hcd, (card_w - 289, 564, card_w - 40, 614), tag_txt, "bold", (255, 255, 255, 255), max_size=28, min_size=20, max_lines=1)

            hcd.rounded_rectangle([(34, 560), (225, 618)], radius=14, fill=(22, 32, 52, 240), outline=neon_c + (210,), width=2)
            num_badge = f"خبر  {to_persian_digits(f'{idx:02d}')}"
            draw_centered_block_in_box(hcd, (42, 564, 217, 614), num_badge, "bold", neon_c + (255,), max_size=30, min_size=22, max_lines=1)

            # متن داخل کارت با ۵۰ پیکسل حاشیه امن از هر طرف و کنتراست عالی (سفید روی باکس قرمز برند)
            card_line_lays = make_line_layers(
                hl_txt, hl_words, card_w - 108, card_h - 662, card_w - 50, 638,
                "display", 52, 24, 4, "right", (255, 255, 255, 255), (255, 255, 255, 255),
                pill_bg=accent_c + (235,), canvas_size=(card_w, card_h)
            )
            holo_hud = Image.new("RGBA", (w, 330), (0, 0, 0, 0))
            hhd = ImageDraw.Draw(holo_hud)
            paste_logo(holo_hud, hhd, 56, 226, 102, 76)
            draw_rtl_text(hhd, (170, 250), BRAND_HANDLE, load_font("bold", 28), neon_c + (238,), align="left", shadow=True, is_rtl=False)
            hhd.rounded_rectangle([(w - 256, 232), (w - 56, 298)], radius=32, fill=(10, 16, 28, 218), outline=neon_c + (195,), width=3)
            draw_rtl_text(hhd, (w - 156, 246), cnt_str, load_font("bold", 32), (255, 255, 255, 255), align="center", shadow=False, is_rtl=False)
            entry["holo_chrome"], entry["photo_hole_mask"] = holo_chrome, photo_hole_mask
            entry["card_line_lays"], entry["holo_hud"] = card_line_lays, holo_hud

        prepared.append(entry)

    def frame_gen():
        global_t = 0.0
        f_idx = 0
        wipe_dur = 0.24

        def cur_energy():
            return eq_energies[min(len(eq_energies) - 1, f_idx)]

        # ۱. قلاب رگباری سریع (حدود ۲ ثانیه)
        n_intro = int(round(intro_dur * fps))
        for i in range(n_intro):
            lt = i / fps
            global_t += 1.0 / fps
            if cold_photos and lt < 0.90:
                p_sel = cold_photos[min(len(cold_photos) - 1, int(lt / 0.30))]
                bg = zoom_pan_slice(p_sel, w, h, (lt % 0.30) / 0.30, zoom_amt=0.14, pan_dir=1)
                bg_rgba = Image.fromarray(bg).convert("RGBA")
                bg_rgba.alpha_composite(Image.new("RGBA", (w, h), (12, 16, 26, 132)))
                bg = np.array(bg_rgba.convert("RGB"), dtype=np.uint8)
            else:
                bg = make_dark_gradient_bg(global_t, (0, 175, 235) if style == "hologram" else (204, 18, 28))

            dy = int(55 * ((1.0 - min(1.0, lt / 0.36)) ** 3))
            frame = apply_glass_box(bg, (intro_box[0], intro_box[1] + dy, intro_box[2], intro_box[3] + dy), radius=36, alpha=0.62)
            frame.alpha_composite(intro_ov, (0, dy))
            if lt > (intro_dur - wipe_dur):
                draw_broadcast_wipe(frame, "in", (lt - (intro_dur - wipe_dur)) / wipe_dur)
            f_idx += 1
            yield np.array(frame.convert("RGB"), dtype=np.uint8)

        # ۲. اسلایدهای خبرها
        for s_idx, sl in enumerate(prepared):
            dur = sl["dur"]
            n_f = int(round(dur * fps))
            photo_arr = sl["photo_arr"]
            amb_bg = sl["amb_bg"]
            pan_d = 1 if (s_idx % 2 == 0) else -1

            for i in range(n_f):
                lt = i / fps
                global_t += 1.0 / fps
                prog = lt / max(0.1, dur)
                en = cur_energy()

                if style == "broadcast":
                    bg_rgb = zoom_pan_slice(photo_arr, w, h, prog, 0.10, pan_d) if photo_arr is not None else make_dark_gradient_bg(global_t, sl["accent"])
                    base_rgba = Image.fromarray(bg_rgb).convert("RGBA")
                    base_rgba.alpha_composite(vignette)
                    dy = int(85 * ((1.0 - min(1.0, max(0.0, (lt - 0.08) / 0.44))) ** 3))
                    cur_box = (64, 990 + dy, w - 64, 1395 + dy)
                    frame = apply_glass_box(np.array(base_rgba.convert("RGB"), dtype=np.uint8), cur_box, radius=32, alpha=0.62)
                    frame.alpha_composite(sl["card_chrome"], (cur_box[0], cur_box[1]))
                    for li, l_lay in enumerate(sl["line_lays"]):
                        if lt >= (0.18 + li * 0.20):
                            frame.alpha_composite(l_lay, (cur_box[0], cur_box[1]))
                    frame.alpha_composite(sl["hud_top"], (0, 0))
                    draw_equalizer(frame, 498, 245, en, global_t, (242, 200, 68, 240))
                    draw_progress_bars(frame, s_idx, prog, bar_y=202)
                    draw_rtl_text(ImageDraw.Draw(frame), (w // 2, 1418), "بسته خبری روزانه  |  مهم‌ترین اخبار ایران و شیراز", load_font("regular", 25), (210, 218, 232, 220), align="center", shadow=False)
                    if lt < wipe_dur:
                        draw_broadcast_wipe(frame, "out", lt / wipe_dur)
                    elif lt > (dur - wipe_dur):
                        draw_broadcast_wipe(frame, "in", (lt - (dur - wipe_dur)) / wipe_dur)

                elif style == "split":
                    canvas_rgb = make_dark_gradient_bg(global_t, sl["accent"])
                    if photo_arr is not None:
                        canvas_rgb[0:848, 0:w] = zoom_pan_slice(photo_arr, w, 848, prog, 0.09, pan_d)
                    frame = Image.fromarray(canvas_rgb).convert("RGBA")
                    frame.alpha_composite(sl["static_split"])
                    for li, l_lay in enumerate(sl["line_lays"]):
                        if lt >= (0.14 + li * 0.20):
                            lp = min(1.0, (lt - (0.14 + li * 0.20)) / 0.26)
                            dx = int(75 * ((1.0 - lp) ** 3))
                            frame.alpha_composite(l_lay, (dx, 0))
                    draw_equalizer(frame, 498, 242, en, global_t, (255, 255, 255, 230))
                    draw_progress_bars(frame, s_idx, prog, bar_y=202)
                    if ticker_strip is not None:
                        tw_safe = TEXT_SAFE_RIGHT + 14
                        avail = max(1, ticker_strip.width - tw_safe)
                        src_x = avail - (int(global_t * 170) % avail)
                        frame.alpha_composite(ticker_strip.crop((src_x, 0, src_x + tw_safe, 68)), (0, 1365))
                        ImageDraw.Draw(frame).rectangle([(tw_safe - 8, 1365), (tw_safe, 1433)], fill=sl["accent"] + (255,))
                    if lt < wipe_dur:
                        draw_broadcast_wipe(frame, "out", lt / wipe_dur)
                    elif lt > (dur - wipe_dur):
                        draw_broadcast_wipe(frame, "in", (lt - (dur - wipe_dur)) / wipe_dur)

                elif style == "editorial":
                    if amb_bg is not None:
                        bg_ed = cv2.addWeighted(paper_bg_arr, 0.68, zoom_pan_slice(amb_bg, w, h, prog, 0.05, pan_d), 0.32, 0)
                    else:
                        bg_ed = paper_bg_arr.copy()
                    frame = Image.fromarray(bg_ed).convert("RGBA")
                    px1, py1, px2, py2 = 68, 336, w - 68, 898
                    pw, ph = px2 - px1, py2 - py1
                    pic_pil = Image.fromarray(zoom_pan_slice(photo_arr, pw, ph, prog, 0.08, pan_d)) if photo_arr is not None else Image.fromarray(make_dark_gradient_bg(global_t, sl["accent"])[0:ph, 0:pw])
                    fd = ImageDraw.Draw(frame)
                    fd.rectangle([(px1 + 12, py1 + 12), (px2 + 12, py2 + 12)], fill=(8, 9, 12, 195))
                    frame.paste(pic_pil, (px1, py1))
                    fd.rectangle([(px1, py1), (px2, py2)], outline=(225, 216, 196, 225), width=4)
                    frame.alpha_composite(sl["ed_frame"])
                    hl_prog = min(1.0, max(0.0, (lt - 0.25) / 1.05))
                    n_rects = max(1, len(sl["line_rects"]))
                    for ri, (rx1, ry1, rx2, ry2) in enumerate(sl["line_rects"]):
                        lp = min(1.0, max(0.0, hl_prog * n_rects - ri))
                        if lp > 0:
                            fd.rectangle([(int(rx2 - (rx2 - rx1) * lp), ry1), (rx2, ry2)], fill=sl["accent"] + (215,))
                    frame.alpha_composite(sl["hl_lay"])
                    draw_progress_bars(frame, s_idx, prog, bar_y=202)
                    if lt < wipe_dur:
                        draw_broadcast_wipe(frame, "out", lt / wipe_dur)
                    elif lt > (dur - wipe_dur):
                        draw_broadcast_wipe(frame, "in", (lt - (dur - wipe_dur)) / wipe_dur)

                elif style == "kinetic":
                    if photo_arr is not None:
                        snap = 0.14 * ((1.0 - min(1.0, lt / 0.32)) ** 2)
                        bg_rgb = zoom_pan_slice(photo_arr, w, h, prog, 0.07 + snap, pan_d)
                    else:
                        bg_rgb = make_dark_gradient_bg(global_t, sl["accent"])
                    frame = Image.fromarray(bg_rgb).convert("RGBA")
                    frame.alpha_composite(vignette)
                    frame.alpha_composite(sl["k_hud"])
                    for li, lay in enumerate(sl["line_layers"]):
                        if lt >= (0.12 + li * 0.20):
                            frame.alpha_composite(lay)
                    draw_equalizer(frame, 498, 248, en, global_t, (255, 224, 52, 240))
                    draw_progress_bars(frame, s_idx, prog, bar_y=202)
                    if lt < 0.07:
                        frame.alpha_composite(Image.new("RGBA", (w, h), (255, 255, 255, 165)))

                elif style == "live":
                    bg_lv = zoom_pan_slice(amb_bg, w, h, prog, 0.06, pan_d) if amb_bg is not None else make_dark_gradient_bg(global_t, (24, 58, 128))
                    frame = Image.fromarray(bg_lv).convert("RGBA")
                    mx1, my1, mx2, my2 = 64, 364, w - 64, 916
                    mw, mh = mx2 - mx1, my2 - my1
                    mon_pil = Image.fromarray(zoom_pan_slice(photo_arr, mw, mh, prog, 0.09, pan_d)) if photo_arr is not None else Image.fromarray(make_dark_gradient_bg(global_t * 1.4, sl["accent"])[0:mh, 0:mw])
                    mmask = Image.new("L", (mw, mh), 0)
                    ImageDraw.Draw(mmask).rounded_rectangle([(0, 0), (mw, mh)], radius=22, fill=255)
                    frame.paste(mon_pil, (mx1, my1), mmask)
                    frame.alpha_composite(sl["live_ov"])
                    if int(global_t * 3.0) % 2 == 0:
                        ImageDraw.Draw(frame).ellipse([(184, 237), (206, 259)], fill=(239, 35, 48, 255))
                    draw_equalizer(frame, 485, 228, en, global_t, (255, 255, 255, 235))
                    for li, l_lay in enumerate(sl["line_lays"]):
                        if lt >= (0.14 + li * 0.20):
                            frame.alpha_composite(l_lay)
                    if ticker_strip is not None:
                        tw_safe = TEXT_SAFE_RIGHT + 14
                        avail = max(1, ticker_strip.width - tw_safe)
                        src_x = avail - (int(global_t * 175) % avail)
                        frame.alpha_composite(ticker_strip.crop((src_x, 0, src_x + tw_safe, 68)), (0, 1348))
                        ImageDraw.Draw(frame).rectangle([(tw_safe - 8, 1348), (tw_safe, 1416)], fill=(250, 204, 21, 255))
                    if lt < wipe_dur:
                        draw_broadcast_wipe(frame, "out", lt / wipe_dur)
                    elif lt > (dur - wipe_dur):
                        draw_broadcast_wipe(frame, "in", (lt - (dur - wipe_dur)) / wipe_dur)

                else:  # style == "hologram"
                    neon_c = sl["neon"]
                    bg_h = zoom_pan_slice(amb_bg, w, h, prog, 0.06, pan_d) if amb_bg is not None else make_dark_gradient_bg(global_t * 1.1, neon_c)
                    frame = Image.fromarray(bg_h).convert("RGBA")
                    frame.alpha_composite(vignette)
                    fd = ImageDraw.Draw(frame)
                    for px0, py0, spd, rad, pcol in particles:
                        py = (py0 - global_t * spd) % h
                        px = (px0 + math.sin(global_t * 1.6 + py0 * 0.01) * 18) % w
                        fd.ellipse([(px - rad, py - rad), (px + rad, py + rad)], fill=pcol + (145,))

                    card_frame = sl["holo_chrome"].copy()
                    cw_in, ch_in = card_frame.width - 44, 515
                    live_pic = Image.fromarray(zoom_pan_slice(photo_arr, cw_in, ch_in, prog, 0.11, pan_d)) if photo_arr is not None else Image.fromarray(make_dark_gradient_bg(global_t * 1.3, neon_c)[0:ch_in, 0:cw_in])
                    card_frame.paste(live_pic, (22, 22), sl["photo_hole_mask"])
                    for li, c_lay in enumerate(sl["card_line_lays"]):
                        if lt >= (0.14 + li * 0.22):
                            card_frame.alpha_composite(c_lay)

                    base_yaw = 6.5 if (s_idx % 2 == 0) else -6.5
                    yaw = base_yaw * math.cos(lt * 0.85)
                    pitch = 2.8 * math.sin(lt * 1.1)
                    float_y = int(11 * math.sin(lt * 1.8))
                    warped = warp_3d_card_rgba(card_frame, yaw, pitch)
                    frame.alpha_composite(warped, ((w - warped.width) // 2, 304 + float_y))
                    frame.alpha_composite(sl["holo_hud"], (0, 0))
                    draw_equalizer(frame, 498, 245, en, global_t, neon_c + (245,))
                    draw_progress_bars(frame, s_idx, prog, bar_y=202, active_c=neon_c + (255,))
                    draw_rtl_text(ImageDraw.Draw(frame), (w // 2, 1416), "گزارش صوتی و تصویری  |  مهم‌ترین اخبار ایران و شیراز", load_font("bold", 26), (225, 234, 248, 230), align="center", shadow=False)
                    if lt < wipe_dur:
                        draw_broadcast_wipe(frame, "out", lt / wipe_dur, accent_rgba=neon_c + (255,))
                    elif lt > (dur - wipe_dur):
                        draw_broadcast_wipe(frame, "in", (lt - (dur - wipe_dur)) / wipe_dur, accent_rgba=neon_c + (255,))

                f_idx += 1
                yield np.array(frame.convert("RGB"), dtype=np.uint8)

        # ۳. پایان فالوئرگیر ۲.۶ ثانیه‌ای با انیمیشن کلیک دکمه فالو
        n_out = int(round(outro_dur * fps))
        for i in range(n_out):
            lt = i / fps
            global_t += 1.0 / fps
            bg = make_dark_gradient_bg(global_t, (0, 175, 235) if style == "hologram" else (204, 18, 28))
            frame = apply_glass_box(bg, outro_box, radius=36, alpha=0.60)
            frame.alpha_composite(outro_base)
            click_t = outro_dur * 0.45
            if lt < click_t:
                frame.alpha_composite(btn_pre)
            else:
                frame.alpha_composite(btn_post)
                rip_dt = lt - click_t
                if rip_dt < 0.35:
                    rp = rip_dt / 0.35
                    rr = int(28 + 115 * rp)
                    ra = int(230 * (1.0 - rp))
                    ImageDraw.Draw(frame).ellipse([(w // 2 - rr, 1020 - rr), (w // 2 + rr, 1020 + rr)], outline=(255, 255, 255, ra), width=6)
            if lt < wipe_dur:
                draw_broadcast_wipe(frame, "out", lt / wipe_dur)
            f_idx += 1
            yield np.array(frame.convert("RGB"), dtype=np.uint8)

    pipe_frames_to_mp4(frame_gen(), out_mp4, audio_path, fps=fps, loop_audio=False)
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
    draw_centered_block_in_box(d, (96, 855, 984, 965), "برای پیگیری مهم‌ترین خبرهای ایران و شیراز فالو کنید", "bold", theme["subtext"], max_size=38, min_size=26, max_lines=2, align="center")
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
        await send_message(session, chat_id, "✨ در حال پاک‌سازی تیترها، استخراج کلمات کلیدی هایلایت و ساخت سؤال کامنت‌گیر...")
        editorial = await prepare_viral_daily_editorial(session, items_copy)

        narration_plan = None
        if style_key == "hologram":
            nar_dir = tempfile.mkdtemp(dir=TMP_ROOT)
            await send_message(session, chat_id, "🎙️ در حال تولید صدای گوینده اختصاصی (Gemini TTS) با اعراب‌گذاری دقیق و میکس رادیویی...")
            narration_plan = await prepare_hologram_narration_audio(session, items_copy, editorial, nar_dir)

        mp4 = await asyncio.to_thread(build_daily_summary_reel_sync, items_copy, style_key, narration_plan, editorial)
        voice_note = ""
        if narration_plan and narration_plan.get("narrated"):
            voice_note = f"\n🎙️ گویندگی فارسی اختصاصی ({narration_plan.get('engine', 'Gemini TTS')}) با داکینگ خودکار انجام شد."
        await send_video_file(
            session,
            chat_id,
            mp4,
            caption=(
                f"🎬 ریلز وایرال جمع‌بندی سبک «{style_title}» ({to_persian_digits(str(len(items_copy)))} خبر) آماده انتشار است!{voice_note}\n"
                "💡 خبرها هنوز در صف ذخیره هستند؛ می‌توانید با سبک‌های دیگر هم خروجی بگیرید."
            ),
        )
        if CONFIG.get("make_grid_cover", True) and items_copy:
            first_photo = next((it.get("photo") for it in items_copy if it.get("photo") and os.path.exists(it["photo"])), "")
            cov = await asyncio.to_thread(render_reel_grid_cover_sync, first_photo, "۶۰ ثانیه خبر", "مهم‌ترین اخبار ایران و شیراز")
            await send_photo_file(session, chat_id, cov, caption="🧩 کاور گرید ۴:۵ هماهنگ با پروفایل")
            if os.path.exists(cov):
                os.remove(cov)

        headlines_text = "\n".join(f"- {it['display_headline']}" for it in editorial.get("items", []))
        cap = await generate_editorial_caption(session, f"جمع‌بندی مهم‌ترین اخبار امروز ایران و شیراز:\n{headlines_text}")
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

    # --- دریافت دسته‌ای خبرهای صف جمع‌بندی با دکمه شیشه‌ای تایید/اصلاح زیر هر خبر ---
    if mode == "daily_collect":
        photo_path = await download_tg_file(session, msg["photo"][-1]["file_id"], ".jpg") if msg.get("photo") else ""
        clean_lines = [strip_emojis_for_font(ln) for ln in text.splitlines() if strip_emojis_for_font(ln)]
        if not photo_path and not clean_lines:
            await send_message(session, chat_id, "❌ عکس یا متن خبر را بفرستید.", kb_daily_collect())
            return
        joined_news = " — ".join(clean_lines[:2]) if clean_lines else "خبر تصویری جدید"
        raw_hl = sanitize_display_headline(joined_news)
        tag = "خبر فوری" if ("فوری" in text or "حادثه" in text) else ("ورزشی" if "ورزش" in text else "خبر شیراز")
        item = add_to_daily_items(raw_hl, photo_path, tag=tag, exact_lock=False)
        await send_message(
            session,
            chat_id,
            format_daily_item_card(item),
            kb_daily_item_inline(item["id"], approved=False),
        )
        return

    # --- دریافت متن اصلاح‌شده کاربر پس از کلیک روی دکمه شیشه‌ای «✏️ اصلاح متن خبر» ---
    if mode == "daily_edit_item":
        item_id = state.get("item_id")
        target = next((it for it in DAILY_ITEMS if it.get("id") == item_id), None)
        if not target:
            USER_STATE[chat_id] = {"mode": "daily_collect"}
            await send_message(session, chat_id, "⚠️ این خبر دیگر در صف وجود ندارد.", kb_daily_collect())
            return
        if not text:
            await send_message(session, chat_id, "❌ لطفاً متن اصلاح‌شده خبر را به‌صورت متنی ارسال کنید:")
            return
        new_hl = sanitize_display_headline(text)
        target["headline"] = new_hl
        target["exact_lock"] = True
        USER_STATE[chat_id] = {"mode": "daily_collect"}
        await send_message(
            session,
            chat_id,
            format_daily_item_card(target),
            kb_daily_item_inline(target["id"], approved=True),
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

async def handle_callback_query(session: aiohttp.ClientSession, cq: dict):
    cq_id = cq.get("id", "")
    from_id = str(cq.get("from", {}).get("id", ""))
    msg = cq.get("message") or {}
    chat_id = str(msg.get("chat", {}).get("id", ""))
    msg_id = msg.get("message_id")
    data = cq.get("data", "")

    if not is_admin(from_id):
        await tg_api(session, "answerCallbackQuery", {"callback_query_id": cq_id})
        return

    if data.startswith("di_ok:"):
        item_id = data.split(":", 1)[1]
        target = next((it for it in DAILY_ITEMS if it.get("id") == item_id), None)
        if not target:
            await tg_api(session, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "این خبر در صف یافت نشد."})
            return
        target["exact_lock"] = True
        await tg_api(session, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ متن خبر تایید و قفل شد."})
        await tg_api(session, "editMessageText", {
            "chat_id": chat_id,
            "message_id": msg_id,
            "text": format_daily_item_card(target),
            "reply_markup": kb_daily_item_inline(item_id, approved=True),
        })
        return

    if data.startswith("di_edit:"):
        item_id = data.split(":", 1)[1]
        target = next((it for it in DAILY_ITEMS if it.get("id") == item_id), None)
        if not target:
            await tg_api(session, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "این خبر در صف یافت نشد."})
            return
        USER_STATE[chat_id] = {"mode": "daily_edit_item", "item_id": item_id}
        await tg_api(session, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "✏️ متن جدید خبر را بفرستید"})
        await send_message(
            session,
            chat_id,
            f"✏️ متن دقیق و نهایی این خبر را (با تعداد کاراکتر دلخواه خودتان) بفرستید تا جایگزین و قفل شود:\n\n"
            f"متن فعلی برای کپی سریع:\n{target['headline']}",
            {"inline_keyboard": [[{"text": "❌ انصراف از اصلاح", "callback_data": f"di_cancel:{item_id}"}]]},
        )
        return

    if data.startswith("di_cancel:"):
        USER_STATE[chat_id] = {"mode": "daily_collect"}
        await tg_api(session, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "اصلاح لغو شد."})
        await tg_api(session, "editMessageText", {
            "chat_id": chat_id,
            "message_id": msg_id,
            "text": "❌ اصلاح لغو شد؛ می‌توانید خبر بعدی را بفرستید یا یکی از ۶ سبک را انتخاب کنید.",
        })
        return

    if data.startswith("di_del:"):
        item_id = data.split(":", 1)[1]
        target = next((it for it in DAILY_ITEMS if it.get("id") == item_id), None)
        if target:
            if target.get("photo") and os.path.exists(target["photo"]):
                try:
                    os.remove(target["photo"])
                except Exception:
                    pass
            DAILY_ITEMS.remove(target)
        if USER_STATE.get(chat_id, {}).get("item_id") == item_id:
            USER_STATE[chat_id] = {"mode": "daily_collect"}
        await tg_api(session, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "🗑️ خبر از صف حذف شد."})
        await tg_api(session, "editMessageText", {
            "chat_id": chat_id,
            "message_id": msg_id,
            "text": f"🗑️ این خبر از صف جمع‌بندی حذف شد. (تعداد باقی‌مانده: {to_persian_digits(str(len(DAILY_ITEMS)))} خبر)",
        })
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
                params = {"offset": offset, "timeout": 25, "allowed_updates": '["message","callback_query"]'}
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
                            elif "callback_query" in update:
                                await handle_callback_query(session, update["callback_query"])
            except Exception as e:
                print(f"Loop error: {e}")
                await asyncio.sleep(4)

        if BG_TASKS:
            await asyncio.gather(*BG_TASKS, return_exceptions=True)

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    print(f"Studio Bot shift ended cleanly at {get_tehran_now().strftime('%H:%M')} Tehran.")


if __name__ == "__main__":
    asyncio.run(main())
