"""
Supabase client — зберігає всі дані моніторингу в Lovable Cloud.
Таблиці створюються автоматично через SQL міграцію (migrations/001_monitoring.sql)
"""
import os
from supabase import create_client, Client
from datetime import datetime
from typing import Optional

_client: Optional[Client] = None

def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


def upsert_competitor_posts(posts: list[dict]) -> None:
    """Зберігає/оновлює пости конкурентів."""
    if not posts:
        return
    db = get_client()
    db.table("competitor_posts").upsert(
        posts,
        on_conflict="platform,post_id"
    ).execute()
    print(f"  ✓ Збережено {len(posts)} постів")


def upsert_competitor_metrics(metrics: list[dict]) -> None:
    """Зберігає агреговані метрики по акаунту за день."""
    if not metrics:
        return
    db = get_client()
    db.table("competitor_metrics").upsert(
        metrics,
        on_conflict="platform,username,date"
    ).execute()
    print(f"  ✓ Збережено {len(metrics)} метрик")


def insert_ml_insights(insights: list[dict]) -> None:
    """Додає ML-інсайти у стрічку аналітики."""
    if not insights:
        return
    db = get_client()
    db.table("ml_insights").insert(insights).execute()
    print(f"  ✓ Додано {len(insights)} інсайтів")


def get_recent_posts(platform: str, username: str, days: int = 30) -> list[dict]:
    """Читає свіжі пости для ML-аналізу."""
    from datetime import timedelta
    db = get_client()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = db.table("competitor_posts") \
        .select("*") \
        .eq("platform", platform) \
        .eq("username", username) \
        .gte("posted_at", since) \
        .order("posted_at", desc=True) \
        .execute()
    return result.data or []
