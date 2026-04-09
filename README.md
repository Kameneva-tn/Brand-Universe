# Brand Universal AI — Моніторинг-агент

Python ML сервіс, який 24/7 відстежує конкурентів в Instagram, Facebook, Threads.

## Що робить

- Збирає пости конкурентів через Apify
- Класифікує контент (освіта, промо, lifestyle...)
- Розраховує engagement score
- Знаходить найкращий час публікацій
- Детектує вірусні пости (Z-score аномалії)
- Виявляє зростаючі тренди і хештеги
- Генерує AI-інсайти через Claude
- Зберігає все в Supabase (Lovable Cloud)

## Кроки налаштування

### 1. Supabase — створи таблиці
Зайди в Lovable → відкрий Supabase → SQL Editor → виконай файл:
`migrations/001_monitoring_tables.sql`

### 2. Отримай API ключі

**Apify** (для збору постів конкурентів):
- Зареєструйся на https://apify.com
- Settings → Integrations → API Token
- Тарифний план: ~$49/міс (Starter)

**Supabase** (твоя Lovable Cloud база):
- В Lovable: натисни іконку бази даних → Connect to Supabase
- Або: https://supabase.com → твій проєкт → Settings → API
- Скопіюй `Project URL` і `service_role` key (не anon!)

**Anthropic** (вже є в Lovable Secrets):
- https://console.anthropic.com → API Keys

### 3. Налаштуй конкурентів
Скопіюй `.env.example` → `.env` і заповни:
```
INSTAGRAM_COMPETITORS=competitor1,competitor2
FACEBOOK_COMPETITORS=CompetitorPage1
THREADS_COMPETITORS=competitor1,competitor2
```

### 4. Деплой на Railway

```bash
# 1. Встанови Railway CLI
npm install -g @railway/cli

# 2. Залогінься
railway login

# 3. Ініціалізуй проєкт в цій папці
railway init

# 4. Додай змінні середовища
railway variables set APIFY_API_TOKEN=...
railway variables set SUPABASE_URL=...
railway variables set SUPABASE_KEY=...
railway variables set ANTHROPIC_API_KEY=...
railway variables set INSTAGRAM_COMPETITORS=competitor1,competitor2
railway variables set SCHEDULE_HOURS=6

# 5. Деплой
railway up
```

### 5. Тест локально
```bash
pip install -r requirements.txt
cp .env.example .env
# Заповни .env
python main.py
```

## Структура проєкту

```
monitoring-agent/
├── main.py                    # Головний файл, розклад запуску
├── collectors/
│   └── apify_collector.py     # Збір даних: Instagram, Facebook, Threads
├── ml/
│   └── analyzer.py            # ML: engagement, класифікація, тренди, аномалії
├── storage/
│   └── supabase_client.py     # Запис і читання з Supabase
├── migrations/
│   └── 001_monitoring_tables.sql  # SQL для створення таблиць
├── requirements.txt
├── railway.json
└── .env.example
```

## Що потрапляє в Lovable дашборд

Після першого запуску в Supabase з'являться дані в таблицях:
- `competitor_posts` → всі пости конкурентів
- `competitor_metrics` → агреговані метрики по днях
- `ml_insights` → аномалії, тренди, AI-висновки

Lovable дашборд читає ці таблиці через Supabase Realtime.
