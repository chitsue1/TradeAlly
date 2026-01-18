# 🤖 AI Trading Bot v2.0

## 📁 სტრუქტურა

```
your-bot/
├── main.py                    # Main launcher
├── config.py                  # კონფიგურაციები
├── trading_engine.py          # Trading logic
├── telegram_handler.py        # Telegram functions
├── requirements.txt           # Dependencies
├── README.md                  # ეს ფაილი
├── My-AI-Agent_needs/         # PDF-ები (optional)
└── *.json                     # Auto-generated data files
```

---

## 🚀 გაშვება Railway-ზე

### 1. ფაილების ატვირთვა

Railway-ში ატვირთე ყველა ფაილი:
- `main.py`
- `config.py`
- `trading_engine.py`
- `telegram_handler.py`
- `requirements.txt`

### 2. Start Command დააყენე

Railway Settings → Deploy → Start Command:
```bash
python main.py
```

### 3. გაშვება

Railway ავტომატურად:
- დააინსტალირებს `requirements.txt`-დან
- გაუშვებს `main.py`-ს

---

## 🔧 Local გაშვება (ტესტირებისთვის)

```bash
# 1. დააინსტალირე პაკეტები
pip install -r requirements.txt

# 2. შექმენი PDF საქაღალდე (optional)
mkdir My-AI-Agent_needs

# 3. გაუშვი ბოტი
python main.py
```

---

## ⚙️ კონფიგურაცია

### config.py-ში შეცვალე:

```python
TELEGRAM_TOKEN = "შენი-ბოტის-ტოკენი"
ADMIN_ID = 123456789  # შენი Telegram ID
```

### მონიტორინგის პარამეტრები:

```python
SCAN_INTERVAL = 300        # სკანირების ციკლი (წამი)
ASSET_DELAY = 2            # აქტივებს შორის დაყოვნება
STOP_LOSS_PERCENT = 5.0    # Stop Loss
TAKE_PROFIT_PERCENT = 10.0 # Take Profit
AI_ENTRY_THRESHOLD = 60    # AI Score threshold (buy)
```

---

## 📊 როგორ მუშაობს

### 1. **Data Fetching:**
- 🪙 Crypto: CoinGecko API (50 req/min)
- 📈 Stocks: YFinance with retry (30 req/min)
- Rate limiting + exponential backoff

### 2. **AI Analysis:**
- RSI (Relative Strength Index)
- EMA200 (Trend detection)
- Bollinger Bands
- Fear & Greed Index
- PDF Knowledge Base

### 3. **Signal Generation:**
- Entry: AI Score ≥ 60
- News validation (RSS feeds)
- Dynamic Take Profit calculation

### 4. **Exit Conditions:**
- Stop Loss: -5%
- Take Profit: +10%
- RSI overbought (>75)
- Time limit (72h)
- Trailing stop (15%+)
- AI bearish patterns

---

## 🎯 ბრძანებები

### მომხმარებლებისთვის:
```
/start       - დაწყება
/subscribe   - გამოწერა
/mystatus    - სტატუსი
/stop        - გაუქმება
```

### ადმინისთვის:
```
/admin       - ადმინ პანელი
/adduser ID  - user დამატება
/listusers   - user-ების სია
/botstats    - სტატისტიკა
```

---

## 🔍 Logs-ის ნახვა

Railway-ში:
```
View Logs → Real-time logs
```

ეძებე:
- `✅ Telegram Bot აქტიურია`
- `🧠 AI სკანირება: 19 crypto`
- `🟢 BUY სიგნალი`
- `🔔 SELL სიგნალი`

---

## ⚠️ გავრცელებული პრობლემები

### "ModuleNotFoundError"
```bash
# გადაჭრა: Railway-ში Redeploy
Railway → Deployments → Redeploy
```

### "Rate limit exceeded"
```bash
# Rate limiters ავტომატურად ამუშავებს
# ლოგებში დაინახავ: "⏸️ Rate limit backoff"
```

### "No price data found"
```bash
# CoinGecko-ს უკან აბრუნებს fallback data
# Stocks-ისთვის: 3 retry with exponential backoff
```

---

## 📈 სტატისტიკა

`/botstats` გაჩვენებს:
- აქტიური გამომწერები
- სულ სიგნალები
- Win Rate %
- საშუალო მოგება
- აქტიური პოზიციები

---

## 💡 რჩევები

1. **PDF-ების დამატება:**
   - ჩადე Trading PDF-ები `My-AI-Agent_needs/` საქაღალდეში
   - ბოტი ავტომატურად მოიძებს patterns და strategies

2. **Rate Limits დაცვა:**
   - CoinGecko: 50 calls/min (უფასო)
   - ბოტი ავტომატურად ნელდება

3. **Backtesting:**
   - `trading_engine.py`-ში შეგიძლია დაამატო historical testing

---

## 🚨 Security

**არასდროს:**
- არ გაასაჯარო `config.py` (Telegram token)
- არ დადო GitHub public repo-ში
- გამოიყენე Environment Variables Railway-ზე

---

## 📞 Support

კითხვები? https://t.me/Kagurashinakami

---

**Made with ❤️ by Claude & You! 🚀**