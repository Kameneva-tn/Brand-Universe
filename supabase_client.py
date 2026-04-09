"""
HTTP клієнт для Lovable Edge Function.
Замість прямого підключення до Supabase — всі операції йдуть через
Edge Function monitoring-receiver яка має service_role доступ.

Змінні середовища:
  LOVABLE_FUNCTION_BASE_URL  — https://gwwwkcodzhrdyzyhnznj.supabase.co/functions/v1
  MONITORING_RECEIVER_KEY    — секретний ключ (той самий що в Lovable Secrets)
"""
import os
import requests
from datetime import datetime, timedelta


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "x-receiver-key": os.environ["MONITORING_RECEIVER_KEY"],
    }


def _url() -> str:
    base = os.environ["LOVABLE_FUNCTION_BASE_URL"].rstrip("/")
    return f"{base}/monitoring-receiver"


def _call(action: str, data) -> dict:
    """Викликає Edge Function з action та даними."""
    resp = requests.post(
        _url(),
        json={"action": action, "data": data},
        headers=_headers(),
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


# ─── WRITE ──────────────────────────────────────────────────────────────────

def upsert_competitor_posts(posts: list[dict]) -> None:
    """Зберігає/оновлює пости конкурентів."""
    if not posts:
        return
    _call("upsert_posts", posts)
    print(f"  ✓ Збережено {len(posts)} постів")


def upsert_competitor_metrics(metrics: list[dict]) -> None:
    """Зберігає агреговані метрики по акаунту за день."""
    if not metrics:
        return
    _call("upsert_metrics", metrics)
    print(f"  ✓ Збережено {len(metrics)} метрик")


def insert_ml_insights(insights: list[dict]) -> None:
    """Додає ML-інсайти у стрічку аналітики."""
    if not insights:
        return
    _call("insert_insights", insights)
    print(f"  ✓ Додано {len(insights)} інсайтів")


# ─── READ ───────────────────────────────────────────────────────────────────

def get_recent_posts(platform: str, username: str, days: int = 30) -> list[dict]:
    """Читає свіжі пости для ML-аналізу через Edge Function."""
    result = _call("get_posts", {
        "platform": platform,
        "username": username,
        "days": days,
    })
    return result.get("posts", [])
