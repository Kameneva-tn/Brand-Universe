"""
Brand Universal AI — Моніторинг-агент
======================================
Запускається за розкладом (кожні N годин) або вручну.
Збирає дані з Instagram/Facebook/Threads → ML-аналіз → Supabase.

Запуск вручну:  python main.py
Розклад:        автоматично через Railway Cron або schedule
"""
import os
import json
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from collectors.apify_collector import (
    collect_instagram_posts,
    collect_facebook_posts,
    collect_threads_posts,
)
from ml.analyzer import (
    score_engagement,
    add_content_classification,
    analyze_posting_patterns,
    detect_trends,
    detect_anomalies,
    generate_ai_insights,
)
from storage.supabase_client import (
    upsert_competitor_posts,
    upsert_competitor_metrics,
    insert_ml_insights,
)


def run_monitoring_cycle(brand_id: str = "default"):
    """
    Один повний цикл моніторингу:
    1. Збір постів з усіх платформ
    2. ML-аналіз
    3. Збереження в Supabase
    4. Генерація AI-інсайту
    """
    started_at = datetime.utcnow()
    print(f"\n{'='*60}")
    print(f"🚀 Моніторинг-агент запущено: {started_at.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    # ── Зчитуємо конфіги ──────────────────────────────────────────
    ig_competitors = [u.strip() for u in os.getenv("INSTAGRAM_COMPETITORS", "").split(",") if u.strip()]
    fb_competitors = [u.strip() for u in os.getenv("FACEBOOK_COMPETITORS", "").split(",") if u.strip()]
    th_competitors = [u.strip() for u in os.getenv("THREADS_COMPETITORS", "").split(",") if u.strip()]
    posts_limit = int(os.getenv("POSTS_PER_COMPETITOR", "20"))

    all_posts = []

    # ── 1. ЗБІР ДАНИХ ─────────────────────────────────────────────
    print("📥 КРОК 1: Збір постів конкурентів\n")

    if ig_competitors:
        try:
            ig_posts = collect_instagram_posts(ig_competitors, posts_limit)
            all_posts.extend(ig_posts)
        except Exception as e:
            print(f"  ❌ Instagram помилка: {e}")

    if fb_competitors:
        try:
            fb_posts = collect_facebook_posts(fb_competitors, posts_limit)
            all_posts.extend(fb_posts)
        except Exception as e:
            print(f"  ❌ Facebook помилка: {e}")

    if th_competitors:
        try:
            th_posts = collect_threads_posts(th_competitors, posts_limit)
            all_posts.extend(th_posts)
        except Exception as e:
            print(f"  ❌ Threads помилка: {e}")

    if not all_posts:
        print("\n⚠ Не вдалося зібрати жодного поста. Перевір API ключі і список конкурентів.")
        return

    print(f"\n  📊 Всього зібрано: {len(all_posts)} постів з {len(set(p['username'] for p in all_posts))} акаунтів\n")

    # ── 2. ML АНАЛІЗ ──────────────────────────────────────────────
    print("🤖 КРОК 2: ML-аналіз\n")

    all_posts = add_content_classification(all_posts)
    print("  ✓ Контент класифіковано")

    all_posts = score_engagement(all_posts)
    print("  ✓ Engagement scores розраховано")

    patterns = analyze_posting_patterns(all_posts)
    print(f"  ✓ Патерни публікацій: {len(patterns)} акаунтів")

    trends = detect_trends(all_posts)
    print(f"  ✓ Тренди: {len(trends.get('rising', []))} зростаючих хештегів")

    anomalies = detect_anomalies(all_posts)
    print(f"  ✓ Аномалії: {len(anomalies)} вірусних постів виявлено")

    # ── 3. AI ІНСАЙТ ──────────────────────────────────────────────
    print("\n✨ КРОК 3: Генерація AI-інсайту\n")
    ai_text = generate_ai_insights(patterns, trends, anomalies)
    print(f"  {ai_text[:200]}...")

    # ── 4. ЗБЕРЕЖЕННЯ В SUPABASE ──────────────────────────────────
    print("\n💾 КРОК 4: Збереження в Supabase\n")

    upsert_competitor_posts(all_posts)

    # Агреговані метрики по акаунту
    metrics = _build_metrics(all_posts, patterns)
    upsert_competitor_metrics(metrics)

    # ML Insights
    insights_to_save = []

    # Зберігаємо аномалії як інсайти
    for a in anomalies[:5]:
        insights_to_save.append({
            "brand_id": brand_id,
            "insight_type": "anomaly",
            "platform": a["platform"],
            "username": a["username"],
            "title": f"Вірусний пост @{a['username']}",
            "body": f"ER {a['engagement_rate']}% (норма {a['avg_engagement']}%) — {a['caption_preview'][:150]}",
            "url": a.get("post_url", ""),
            "score": a.get("spike_factor", 0),
            "created_at": datetime.utcnow().isoformat(),
        })

    # Зберігаємо зростаючі тренди
    for trend in trends.get("rising", [])[:3]:
        insights_to_save.append({
            "brand_id": brand_id,
            "insight_type": "trend",
            "platform": "all",
            "username": "",
            "title": f"Зростаючий тренд #{trend['tag']}",
            "body": f"Хештег #{trend['tag']} зріс: {trend['change']} за останній тиждень",
            "url": "",
            "score": trend.get("count", 0),
            "created_at": datetime.utcnow().isoformat(),
        })

    # AI-інсайт
    insights_to_save.append({
        "brand_id": brand_id,
        "insight_type": "ai_summary",
        "platform": "all",
        "username": "",
        "title": "Щотижневий AI-аналіз конкурентів",
        "body": ai_text,
        "url": "",
        "score": 0,
        "created_at": datetime.utcnow().isoformat(),
    })

    insert_ml_insights(insights_to_save)

    duration = (datetime.utcnow() - started_at).total_seconds()
    print(f"\n{'='*60}")
    print(f"✅ Цикл завершено за {duration:.1f}с | Збережено {len(insights_to_save)} інсайтів")
    print(f"{'='*60}\n")


def _build_metrics(posts: list[dict], patterns: dict) -> list[dict]:
    """Будує агреговані метрики по акаунту × платформа × дата."""
    from collections import defaultdict
    today = datetime.utcnow().date().isoformat()
    grouped = defaultdict(list)

    for p in posts:
        key = (p.get("platform", ""), p.get("username", ""))
        grouped[key].append(p)

    metrics = []
    for (platform, username), user_posts in grouped.items():
        ers = [p.get("engagement_rate", 0) for p in user_posts]
        pattern = patterns.get(username, {})
        metrics.append({
            "platform": platform,
            "username": username,
            "date": today,
            "posts_count": len(user_posts),
            "avg_engagement_rate": round(sum(ers) / len(ers), 4) if ers else 0,
            "max_engagement_rate": round(max(ers), 4) if ers else 0,
            "total_likes": sum(p.get("likes", 0) for p in user_posts),
            "total_comments": sum(p.get("comments", 0) for p in user_posts),
            "total_views": sum(p.get("views", 0) for p in user_posts),
            "best_hour": pattern.get("best_hour"),
            "best_day": pattern.get("best_day"),
            "posts_per_week": pattern.get("posts_per_week"),
            "top_content_type": max(
                pattern.get("top_content_types", {}).items(),
                key=lambda x: x[1], default=("other", 0)
            )[0] if pattern.get("top_content_types") else "other",
        })
    return metrics


# ── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    hours = int(os.getenv("SCHEDULE_HOURS", "6"))
    brand_id = os.getenv("BRAND_ID", "default")

    # Перший запуск одразу
    run_monitoring_cycle(brand_id)

    # Далі за розкладом
    schedule.every(hours).hours.do(run_monitoring_cycle, brand_id=brand_id)
    print(f"⏰ Наступний запуск через {hours} год. Агент працює у фоні...\n")

    while True:
        schedule.run_pending()
        time.sleep(60)
