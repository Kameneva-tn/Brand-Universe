"""
Apify Collector — збирає пости конкурентів з Instagram, Facebook, Threads.
Документація Apify: https://apify.com/actors

Використовувані актори:
  Instagram: apify/instagram-scraper
  Facebook:  apify/facebook-pages-scraper
  Threads:   apify/threads-scraper
"""
import os
from apify_client import ApifyClient
from datetime import datetime
from typing import Optional


def _get_client() -> ApifyClient:
    return ApifyClient(os.environ["APIFY_API_TOKEN"])


# ─── INSTAGRAM ─────────────────────────────────────────────────────────────

def collect_instagram_posts(usernames: list[str], posts_limit: int = 20) -> list[dict]:
    """
    Збирає останні пости з публічних Instagram акаунтів конкурентів.
    Повертає нормалізований список постів.
    """
    client = _get_client()
    all_posts = []

    run_input = {
        "directUrls": [f"https://www.instagram.com/{u}/" for u in usernames],
        "resultsType": "posts",
        "resultsLimit": posts_limit,
        "addParentData": True,
    }

    print(f"  📸 Instagram: збираю {len(usernames)} акаунтів...")
    run = client.actor("apify/instagram-scraper").call(run_input=run_input)

    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        try:
            post = {
                "platform": "instagram",
                "post_id": item.get("id") or item.get("shortCode", ""),
                "username": item.get("ownerUsername", ""),
                "post_type": _detect_ig_type(item),
                "caption": (item.get("caption") or "")[:1000],
                "likes": item.get("likesCount", 0) or 0,
                "comments": item.get("commentsCount", 0) or 0,
                "views": item.get("videoViewCount", 0) or 0,
                "shares": 0,  # Instagram не дає shares публічно
                "url": f"https://www.instagram.com/p/{item.get('shortCode', '')}/",
                "thumbnail_url": item.get("displayUrl", ""),
                "posted_at": _parse_ts(item.get("timestamp")),
                "hashtags": _extract_hashtags(item.get("caption") or ""),
                "followers_at_post": item.get("ownerFullName", ""),  # placeholder
                "collected_at": datetime.utcnow().isoformat(),
            }
            # Розраховуємо engagement rate якщо є дані по підписниках
            post["engagement_rate"] = _calc_engagement(
                post["likes"], post["comments"], post["views"],
                item.get("owner", {}).get("followersCount", 0)
            )
            all_posts.append(post)
        except Exception as e:
            print(f"    ⚠ Помилка парсингу Instagram поста: {e}")

    print(f"  ✓ Instagram: зібрано {len(all_posts)} постів")
    return all_posts


def _detect_ig_type(item: dict) -> str:
    if item.get("isVideo"):
        return "reel" if item.get("productType") == "clips" else "video"
    if item.get("type") == "Sidecar":
        return "carousel"
    return "image"


# ─── FACEBOOK ──────────────────────────────────────────────────────────────

def collect_facebook_posts(page_names: list[str], posts_limit: int = 20) -> list[dict]:
    """
    Збирає пости з публічних Facebook сторінок.
    """
    client = _get_client()
    all_posts = []

    run_input = {
        "startUrls": [{"url": f"https://www.facebook.com/{p}"} for p in page_names],
        "maxPosts": posts_limit,
        "scrapeAbout": False,
        "scrapeReviews": False,
        "scrapeServices": False,
    }

    print(f"  📘 Facebook: збираю {len(page_names)} сторінок...")
    run = client.actor("apify/facebook-pages-scraper").call(run_input=run_input)

    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        for post in item.get("posts", []):
            try:
                p = {
                    "platform": "facebook",
                    "post_id": post.get("postId", ""),
                    "username": item.get("pageUrl", "").split("/")[-1],
                    "post_type": "video" if post.get("video") else "image" if post.get("media") else "text",
                    "caption": (post.get("text") or "")[:1000],
                    "likes": post.get("likes", 0) or 0,
                    "comments": post.get("comments", 0) or 0,
                    "views": post.get("videoViewCount", 0) or 0,
                    "shares": post.get("shares", 0) or 0,
                    "url": post.get("url", ""),
                    "thumbnail_url": post.get("media", [{}])[0].get("thumbnail", "") if post.get("media") else "",
                    "posted_at": _parse_ts(post.get("time")),
                    "hashtags": _extract_hashtags(post.get("text") or ""),
                    "followers_at_post": "",
                    "collected_at": datetime.utcnow().isoformat(),
                }
                p["engagement_rate"] = _calc_engagement(
                    p["likes"], p["comments"], p["views"],
                    item.get("likes", 0)
                )
                all_posts.append(p)
            except Exception as e:
                print(f"    ⚠ Помилка парсингу Facebook поста: {e}")

    print(f"  ✓ Facebook: зібрано {len(all_posts)} постів")
    return all_posts


# ─── THREADS ───────────────────────────────────────────────────────────────

def collect_threads_posts(usernames: list[str], posts_limit: int = 20) -> list[dict]:
    """
    Збирає пости з Threads (через Apify актор).
    """
    client = _get_client()
    all_posts = []

    run_input = {
        "startUrls": [{"url": f"https://www.threads.net/@{u}"} for u in usernames],
        "maxPostsPerPage": posts_limit,
    }

    print(f"  🧵 Threads: збираю {len(usernames)} акаунтів...")
    try:
        run = client.actor("apify/threads-scraper").call(run_input=run_input)

        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            try:
                post = {
                    "platform": "threads",
                    "post_id": item.get("id", ""),
                    "username": item.get("user", {}).get("username", ""),
                    "post_type": "video" if item.get("has_video") else "image" if item.get("media") else "text",
                    "caption": (item.get("caption") or "")[:1000],
                    "likes": item.get("like_count", 0) or 0,
                    "comments": item.get("text_post_app_info", {}).get("direct_reply_count", 0) or 0,
                    "views": 0,
                    "shares": item.get("text_post_app_info", {}).get("repost_count", 0) or 0,
                    "url": f"https://www.threads.net/@{item.get('user', {}).get('username', '')}/post/{item.get('code', '')}",
                    "thumbnail_url": "",
                    "posted_at": _parse_ts(item.get("taken_at")),
                    "hashtags": _extract_hashtags(item.get("caption") or ""),
                    "followers_at_post": "",
                    "collected_at": datetime.utcnow().isoformat(),
                }
                post["engagement_rate"] = _calc_engagement(
                    post["likes"], post["comments"], 0,
                    item.get("user", {}).get("follower_count", 0)
                )
                all_posts.append(post)
            except Exception as e:
                print(f"    ⚠ Помилка парсингу Threads поста: {e}")
    except Exception as e:
        print(f"    ⚠ Threads scraper недоступний: {e}")

    print(f"  ✓ Threads: зібрано {len(all_posts)} постів")
    return all_posts


# ─── HELPERS ───────────────────────────────────────────────────────────────

def _calc_engagement(likes: int, comments: int, views: int, followers: int) -> float:
    """engagement rate = (likes + comments + shares) / followers * 100"""
    total = likes + comments
    if followers and followers > 0:
        return round(total / followers * 100, 4)
    if views and views > 0:
        return round(total / views * 100, 4)
    return 0.0


def _parse_ts(ts) -> str:
    """Перетворює різні формати timestamp на ISO string."""
    if not ts:
        return datetime.utcnow().isoformat()
    if isinstance(ts, (int, float)):
        return datetime.utcfromtimestamp(ts).isoformat()
    if isinstance(ts, str):
        return ts
    return datetime.utcnow().isoformat()


def _extract_hashtags(text: str) -> list[str]:
    """Витягує хештеги з тексту поста."""
    import re
    return re.findall(r"#(\w+)", text.lower())
