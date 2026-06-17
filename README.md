# Бот монтажёра

Telegram-бот для управления расписанием видеомонтажёра бренда одежды. Каждое утро в 9:00 автоматически отправляет задания на день из Google Sheets, принимает подтверждения о готовности видео и уведомляет владельца.

---

## Структура проекта

```
editor-bot/
├── main.py          — бот, команды, планировщик
├── sheets.py        — работа с Google Sheets
├── .env.example     — шаблон переменных окружения
├── .gitignore
├── requirements.txt
├── Procfile         — для деплоя на Railway
└── README.md
```

---

## Структура Google Sheets

Создай таблицу с такими колонками (строго в этом порядке, без шапки или с любой шапкой — строки, где дата не совпадает с сегодняшней, автоматически пропускаются):

| A | B | C | D | E | F |
|---|---|---|---|---|---|
| Дата | День недели | Коллекция | Описание видео | Платформа | Статус |
| 12.06.2026 | Пятница | Лето 2026 | Reels в примерочной | Instagram | Монтаж |
| 12.06.2026 | Пятница | Лето 2026 | TikTok с моделью | TikTok | Монтаж |

- **Дата** — формат `ДД.ММ.ГГГГ`, например `12.06.2026`
- **Статус** — `Монтаж` → `Готово` → `Выложено`
  - `Монтаж` — кнопка «Готово» отображается
  - `Готово` / `Выложено` — кнопка не отображается

---

## Шаг 1 — Создать Google Service Account и получить creds.json

1. Открой [Google Cloud Console](https://console.cloud.google.com/)
2. Создай новый проект (или выбери существующий)
3. В поиске найди **"Google Sheets API"** → нажми **Включить**
4. В поиске найди **"Google Drive API"** → нажми **Включить**
5. Перейди в **IAM и администрирование → Сервисные аккаунты**
6. Нажми **Создать сервисный аккаунт**
   - Имя: `editor-bot` (любое)
   - Нажми **Создать и продолжить** → **Готово**
7. Кликни на созданный аккаунт → вкладка **Ключи**
8. **Добавить ключ → Создать новый ключ → JSON**
9. Скачанный файл переименуй в `creds.json` и положи в папку `editor-bot/`

### Дать боту доступ к таблице

1. Открой скачанный `creds.json`, найди поле `"client_email"` — это email вида `editor-bot@project-id.iam.gserviceaccount.com`
2. Открой свою Google Таблицу
3. Нажми кнопку **Поделиться** (Share)
4. Вставь этот email, дай права **Редактор**, нажми **Отправить**

---

## Шаг 2 — Создать бота в Telegram

1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Напиши `/newbot`
3. Придумай имя и username (`@username` должен оканчиваться на `bot`)
4. Скопируй **токен** — он выглядит как `123456789:AAFxxxxxxxxxxxxxxxx`

---

## Шаг 3 — Узнать Chat ID

**Способ 1 — через @userinfobot:**
1. Открой [@userinfobot](https://t.me/userinfobot) в Telegram
2. Напиши `/start` — бот ответит твоим `Id`

**Способ 2 — через своего бота:**
1. Напиши своему боту `/start`
2. Открой в браузере:
   ```
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```
3. В ответе найди `"chat": {"id": 123456789}` — это и есть chat_id

Нужно получить два ID:
- **EDITOR_CHAT_ID** — chat_id монтажёра
- **OWNER_CHAT_ID** — твой chat_id

---

## Шаг 4 — Заполнить .env

Скопируй шаблон:
```bash
cp .env.example .env
```

Открой `.env` и заполни:
```env
BOT_TOKEN=123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
EDITOR_CHAT_ID=123456789
OWNER_CHAT_ID=987654321
GOOGLE_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
GOOGLE_CREDS_FILE=creds.json
```

ID таблицы — это часть URL:
```
https://docs.google.com/spreadsheets/d/[ВОТ_ЭТО]/edit
```

---

## Шаг 5 — Запустить локально

```bash
# Перейди в папку проекта
cd editor-bot

# Создай виртуальное окружение
python3 -m venv venv
source venv/bin/activate       # macOS/Linux
# venv\Scripts\activate        # Windows

# Установи зависимости
pip install -r requirements.txt

# Запусти
python main.py
```

Бот должен написать в консоль:
```
Scheduler started — daily tasks at 09:00 Europe/Moscow
Bot is running...
```

Проверь: напиши боту `/start`, затем `/today`.

---

## Шаг 6 — Деплой на Railway (бесплатно)

[Railway](https://railway.app) даёт бесплатный Starter-план с $5 кредитов в месяц — для лёгкого бота этого хватает.

### Подготовка

1. Зарегистрируйся на [railway.app](https://railway.app) через GitHub
2. Установи Railway CLI (опционально):
   ```bash
   npm install -g @railway/cli
   railway login
   ```

### Деплой через GitHub

1. Создай репозиторий на GitHub и запушь код:
   ```bash
   git init
   git add main.py sheets.py requirements.txt Procfile .gitignore
   # НЕ добавляй .env и creds.json — они в .gitignore
   git commit -m "init editor bot"
   git remote add origin https://github.com/YOUR_USERNAME/editor-bot.git
   git push -u origin main
   ```

2. В Railway: **New Project → Deploy from GitHub repo** → выбери репозиторий

3. Перейди в **Variables** и добавь все переменные из `.env`:
   ```
   BOT_TOKEN = ...
   EDITOR_CHAT_ID = ...
   OWNER_CHAT_ID = ...
   GOOGLE_SHEET_ID = ...
   GOOGLE_CREDS_FILE = creds.json
   TIMEZONE = Europe/Moscow
   ```

4. Для `creds.json` — файл нельзя запушить в Git (секрет). Есть два варианта:

   **Вариант А — через Variables (рекомендуется):**
   - Скопируй весь JSON из `creds.json`
   - Добавь переменную `GOOGLE_CREDS_JSON` со значением всего JSON
   - Добавь в начало `sheets.py`:
     ```python
     import json
     # В методе _connect():
     creds_json = os.getenv("GOOGLE_CREDS_JSON")
     if creds_json:
         import tempfile
         with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
             f.write(creds_json)
             self._creds_file = f.name
     ```

   **Вариант Б — Volume:**
   - В Railway создай Volume, примонтируй его и загрузи файл через SSH

5. Railway автоматически подхватит `Procfile` и запустит `python main.py`

### Деплой через Railway CLI

```bash
railway init
railway up
railway variables set BOT_TOKEN=... EDITOR_CHAT_ID=... OWNER_CHAT_ID=... GOOGLE_SHEET_ID=...
```

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и инструкция |
| `/today` | Задания на сегодня (с кнопками «Готово») |
| `/status` | Статистика за текущий месяц |

---

## Часовой пояс

По умолчанию используется `Europe/Moscow` (UTC+3). Чтобы изменить, добавь в `.env`:
```env
TIMEZONE=Europe/Kyiv
```

Все доступные зоны: [список pytz](https://gist.github.com/heyalexej/8bf688fd67d7199be4a1682b3eec7568)

---

## Диагностика

**Бот не отвечает** — проверь, что `BOT_TOKEN` правильный и бот не заблокирован.

**Ошибка Google Sheets** — убедись, что:
- `creds.json` находится в папке с ботом
- Email сервисного аккаунта добавлен в таблицу с правами Редактора
- Google Sheets API и Google Drive API включены в Cloud Console

**Планировщик не отправляет в 9:00** — проверь часовой пояс (`TIMEZONE`) и что процесс не перезапускается ночью.
