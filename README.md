# 🤖 Instagram & YouTube Video Yuklovchi Telegram Bot

Python bilan yozilgan, Instagram va YouTube videolarini yuklab beruvchi Telegram bot.

---

## ⚡ Imkoniyatlar

- ✅ Instagram post, reel, IGTV videolarini yuklash
- ✅ YouTube video va Shorts yuklash
- ✅ 720p gacha sifat
- ✅ O'zbek tilidagi xabarlar
- ✅ Xatolarni aniq ko'rsatish

---

## 🛠 O'rnatish (0 dan boshlab)

### 1. Python o'rnatish
Python 3.10 yoki yuqori versiya kerak.
- Windows: https://python.org/downloads
- Linux: `sudo apt install python3 python3-pip`

### 2. Loyihani yuklab oling
```bash
# Bu papkani kompyuteringizga ko'chiring
cd telegram_bot
```

### 3. Kerakli kutubxonalarni o'rnating
```bash
pip install -r requirements.txt
```

### 4. Bot token olish
1. Telegramda **@BotFather** ga yozing
2. `/newbot` buyrug'ini yuboring
3. Bot nomini kiriting (masalan: `MyVideoBot`)
4. Username kiriting (masalan: `my_video_dl_bot`)
5. BotFather sizga token beradi — nusxalang!

Token shunday ko'rinadi: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

### 5. Token ni o'rnating

**Windows (CMD):**
```cmd
set BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

**Linux / Mac:**
```bash
export BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

Yoki `.env.example` faylini `.env` deb nusxalang va tokenni kiriting:
```
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

Keyin `bot.py` ichida quyidagi qatorni o'zgartiring:
```python
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
```
Bu qatorni shunday qiling:
```python
BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"  # tokenni to'g'ridan-to'g'ri yozing
```

### 6. Botni ishga tushiring
```bash
python bot.py
```

Ekranda `🚀 Bot ishga tushdi!` degan xabar chiqsa — hammasi yaxshi!

---

## 📱 Ishlatish

1. Telegramda o'z botingizni toping (username orqali)
2. `/start` yuboring
3. Instagram yoki YouTube havolasini yuboring
4. Biroz kuting — video keladi!

---

## 🔧 Muammolar va yechimlar

| Muammo | Yechim |
|--------|--------|
| `BOT_TOKEN o'rnatilmagan` | Token ni to'g'ri kiriting |
| `Private video` xatosi | Private videolarni yuklab bo'lmaydi |
| Video kelmayapti | Internet aloqasini tekshiring |
| `File too large` | 50 MB dan katta videolar yuborilmaydi |

---

## 🚀 Server ga deploy qilish (ixtiyoriy)

Botni 24/7 ishlashi uchun **Railway** yoki **Render** ga joylashtirishingiz mumkin:

### Railway (bepul):
1. https://railway.app ga boring
2. GitHub repo yarating va kodlarni yuklang
3. Environment variable ga `BOT_TOKEN` qo'shing
4. Deploy qiling!

---

## 📁 Fayl tuzilmasi

```
telegram_bot/
├── bot.py           ← Asosiy kod
├── requirements.txt ← Kutubxonalar
├── .env.example     ← Token namunasi
├── README.md        ← Shu fayl
└── downloads/       ← Vaqtinchalik papka (avtomatik yaratiladi)
```
