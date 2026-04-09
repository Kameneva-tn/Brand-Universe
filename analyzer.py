"""
ML Analyzer — аналізує пости конкурентів і генерує інсайти.

Що робить:
  1. engagement_score     — рахує та нормалізує ER по кожному акаунту
  2. content_classifier   — класифікує тип контенту (освіта, промо, lifestyle...)
  3. posting_patterns     — знаходить найкращий час і день публікацій
  4. trend_detector       — виявляє зростаючі теми і хештеги
  5. anomaly_detector     — помічає незвичні сплески активності
  6. ai_insight_generator — Claude генерує текстовий висновок
"""
import os
import re
from datetime import datetime, timedelta
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from anthropic import Anthropic


# ─── 1. ENGAGEMENT SCORING ─────────────────────────────────────────────────

def score_engagement(posts: list[dict]) -> list[dict]:
    """
    Нормалізує engagement_rate по кожній платформі (0–100).
    Додає поле 'engagement_score'.
    """
    if not posts:
        return posts

    df = pd.DataFrame(posts)
    scaler = MinMaxScaler(feature_range=(0, 100))

    for platform in df["platform"].unique():
        mask = df["platform"] == platform
        er_values = df.loc[mask, "engagement_rate"].fillna(0).values.reshape(-1, 1)
        if er_values.max() > 0:
            df.loc[mask, "engagement_score"] = scaler.fit_transform(er_values).flatten()
        else:
            df.loc[mask, "engagement_score"] = 0.0

    return df.to_dict("records")


# ─── 2. CONTENT CLASSIFIER ─────────────────────────────────────────────────

CONTENT_KEYWORDS = {
    "educational":  ["поради", "як", "tips", "guide", "навчання", "дізнайся", "секрет",
                     "results", "before", "after", "до", "після", "routine", "ритуал"],
    "promotional":  ["знижка", "sale", "акція", "купити", "замовити", "ціна", "безкоштовно",
                     "discount", "offer", "buy", "shop", "link in bio", "посилання"],
    "lifestyle":    ["настрій", "вечір", "ранок", "відпочинок", "подорож", "life",
                     "morning", "evening", "mood", "вайб", "естетика"],
    "ugc_repost":   ["дякую", "наш клієнт", "відгук", "результат клієнта", "review",
                     "customer", "результат", "трансформація"],
    "engagement":   ["питання", "як ти думаєш", "голосування", "поділись", "розкажи",
                     "question", "poll", "comment", "what do you think"],
    "product_focus":["склад", "формула", "інгредієнт", "технологія", "ingredient",
                     "formula", "technology", "патент"],
}

def classify_content(caption: str) -> str:
    """Класифікує тип контенту за ключовими словами."""
    if not caption:
        return "other"
    text = caption.lower()
    scores = {cat: 0 for cat in CONTENT_KEYWORDS}
    for cat, keywords in CONTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"


def add_content_classification(posts: list[dict]) -> list[dict]:
    """Додає поле content_type до кожного поста."""
    for post in posts:
        post["content_type"] = classify_content(post.get("caption", ""))
    return posts


# ─── 3. POSTING PATTERNS ───────────────────────────────────────────────────

DAYS_UA = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]

def analyze_posting_patterns(posts: list[dict]) -> dict:
    """
    Знаходить оптимальні час і день для публікацій на основі ER.
    Повертає словник з інсайтами по кожному акаунту.
    """
    results = defaultdict(dict)
    df = pd.DataFrame(posts)

    if df.empty or "posted_at" not in df.columns:
        return {}

    df["posted_at"] = pd.to_datetime(df["posted_at"], errors="coerce", utc=True)
    df["hour"] = df["posted_at"].dt.hour
    df["weekday"] = df["posted_at"].dt.weekday
    df["engagement_rate"] = df.get("engagement_rate", 0)

    for username in df["username"].unique():
        user_df = df[df["username"] == username]

        # Найкраща година
        by_hour = user_df.groupby("hour")["engagement_rate"].mean()
        best_hour = int(by_hour.idxmax()) if not by_hour.empty else 12

        # Найкращий день
        by_day = user_df.groupby("weekday")["engagement_rate"].mean()
        best_day = int(by_day.idxmax()) if not by_day.empty else 0

        # Частота публікацій
        total_days = max((user_df["posted_at"].max() - user_df["posted_at"].min()).days, 1)
        posts_per_week = round(len(user_df) / total_days * 7, 1)

        results[username] = {
            "best_hour": best_hour,
            "best_hour_label": f"{best_hour:02d}:00–{best_hour+1:02d}:00",
            "best_day": DAYS_UA[best_day],
            "posts_per_week": posts_per_week,
            "top_content_types": user_df["content_type"].value_counts().head(3).to_dict()
                if "content_type" in user_df.columns else {},
        }

    return dict(results)


# ─── 4. TREND DETECTOR ─────────────────────────────────────────────────────

def detect_trends(posts: list[dict], top_n: int = 10) -> dict:
    """
    Знаходить топ хештеги і теми за останній тиждень vs попередній.
    Повертає зростаючі і падаючі тренди.
    """
    df = pd.DataFrame(posts)
    if df.empty:
        return {"rising": [], "falling": [], "top_hashtags": []}

    df["posted_at"] = pd.to_datetime(df["posted_at"], errors="coerce", utc=True)
    now = pd.Timestamp.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    recent = df[df["posted_at"] >= week_ago]
    previous = df[(df["posted_at"] >= two_weeks_ago) & (df["posted_at"] < week_ago)]

    # Хештеги
    def count_tags(frame: pd.DataFrame) -> Counter:
        tags = []
        for row in frame.itertuples():
            tags.extend(getattr(row, "hashtags", []) or [])
        return Counter(tags)

    recent_tags = count_tags(recent)
    previous_tags = count_tags(previous)
    top_hashtags = [tag for tag, _ in recent_tags.most_common(top_n)]

    # Rising / falling
    rising, falling = [], []
    for tag in set(list(recent_tags.keys()) + list(previous_tags.keys())):
        r = recent_tags.get(tag, 0)
        p = previous_tags.get(tag, 0)
        if p == 0 and r > 2:
            rising.append({"tag": tag, "count": r, "change": "+нове"})
        elif p > 0:
            delta = round((r - p) / p * 100, 0)
            if delta >= 50:
                rising.append({"tag": tag, "count": r, "change": f"+{int(delta)}%"})
            elif delta <= -50:
                falling.append({"tag": tag, "count": r, "change": f"{int(delta)}%"})

    # Контент-типи що зростають
    content_trends = {}
    if "content_type" in recent.columns:
        content_trends = recent["content_type"].value_counts().head(5).to_dict()

    return {
        "top_hashtags": top_hashtags,
        "rising": sorted(rising, key=lambda x: x["count"], reverse=True)[:5],
        "falling": sorted(falling, key=lambda x: x["count"])[:5],
        "content_trends": content_trends,
    }


# ─── 5. ANOMALY DETECTOR ───────────────────────────────────────────────────

def detect_anomalies(posts: list[dict]) -> list[dict]:
    """
    Z-score аномалії: знаходить пости з незвичайно високим engagement.
    Threshold: Z > 2.0 (top ~2.3%)
    """
    anomalies = []
    df = pd.DataFrame(posts)

    if df.empty or "engagement_rate" not in df.columns:
        return []

    for username in df["username"].unique():
        user_df = df[df["username"] == username].copy()
        er = user_df["engagement_rate"].fillna(0)

        if len(er) < 3 or er.std() == 0:
            continue

        z_scores = (er - er.mean()) / er.std()
        spikes = user_df[z_scores > 2.0]

        for _, post in spikes.iterrows():
            anomalies.append({
                "username": username,
                "platform": post.get("platform", ""),
                "post_url": post.get("url", ""),
                "engagement_rate": round(post.get("engagement_rate", 0), 2),
                "avg_engagement": round(er.mean(), 2),
                "spike_factor": round(float(z_scores[post.name]), 2),
                "caption_preview": (post.get("caption") or "")[:200],
                "content_type": post.get("content_type", ""),
                "posted_at": str(post.get("posted_at", "")),
            })

    return anomalies


# ─── 6. AI INSIGHT GENERATOR ───────────────────────────────────────────────

def generate_ai_insights(
    patterns: dict,
    trends: dict,
    anomalies: list[dict],
    brand_name: str = "ваш бренд",
) -> str:
    """
    Claude генерує короткий стратегічний висновок на основі ML-аналізу.
    """
    try:
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        summary = f"""
Результати ML-аналізу конкурентів для бренду "{brand_name}":

ПАТЕРНИ ПУБЛІКАЦІЙ:
{_format_patterns(patterns)}

ТРЕНДИ ХЕШТЕГІВ:
- Зростаючі: {', '.join(f"#{t['tag']} ({t['change']})" for t in trends.get('rising', []))}
- Топ хештеги: {', '.join('#' + t for t in trends.get('top_hashtags', [])[:5])}

АНОМАЛІЇ (вірусні пости):
{_format_anomalies(anomalies[:3])}

Зроби 3-4 конкретні стратегічні рекомендації для бренду.
Відповідь українською мовою, коротко і по суті.
"""
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": summary}]
        )
        return response.content[0].text

    except Exception as e:
        return f"AI-інсайт недоступний: {e}"


def _format_patterns(patterns: dict) -> str:
    lines = []
    for username, data in list(patterns.items())[:3]:
        lines.append(
            f"  @{username}: найкраще {data.get('best_day')} о {data.get('best_hour_label')}, "
            f"{data.get('posts_per_week')} постів/тиждень"
        )
    return "\n".join(lines) if lines else "немає даних"


def _format_anomalies(anomalies: list[dict]) -> str:
    lines = []
    for a in anomalies:
        lines.append(
            f"  @{a['username']} ({a['platform']}): ER {a['engagement_rate']}% "
            f"(x{a['spike_factor']} від норми) — {a['caption_preview'][:80]}..."
        )
    return "\n".join(lines) if lines else "немає значних аномалій"
