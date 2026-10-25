"""Collecte les avis récents et négatifs, garde ceux qui parlent de propreté des textiles,
enregistre les nouveaux dans docs/data/reviews.json et envoie un e-mail.

Lancé par GitHub Actions : python -m scraper.collect
"""
import os
import sys
from datetime import datetime, timedelta, timezone

from . import apify
from .classify import classify
from .common import (HOTELS_FILE, MANUAL_HOTELS_FILE, REVIEWS_FILE, STATE_FILE, find_key,
                     load_config, load_json, now_iso, parse_date, save_json, site_url)
from .notify import send_email


def select_hotels(cfg):
    c = cfg["collect"]
    hotels = {h["key"]: h for h in load_json(HOTELS_FILE, {"hotels": []})["hotels"]}
    for h in load_json(MANUAL_HOTELS_FILE, []):
        hotels.setdefault(h["key"], {}).update(h)
    eligible = [h for h in hotels.values()
                if (h.get("rooms") or 0) >= c["min_rooms"] or (not h.get("rooms") and c["min_rooms"] == 0)]
    # Les plus grands hôtels d'abord quand on plafonne le nombre suivi.
    eligible.sort(key=lambda h: -(h.get("rooms") or 0))
    return hotels, eligible[: c["max_hotels"]]


def cutoff_for(state, source, cfg):
    last = (state.get("sources", {}).get(source) or {}).get("last_success")
    if last:
        return last[:10]
    since = datetime.now(timezone.utc) - timedelta(days=cfg["collect"]["first_run_lookback_days"])
    return since.strftime("%Y-%m-%d")


def fetch_booking(hotels, cutoff, cfg, token):
    c = cfg["collect"]
    targets = [h for h in hotels if h.get("booking_url")]
    if not targets:
        return []
    items = apify.run_actor(cfg["actors"]["booking_reviews"], {
        "startUrls": [{"url": h["booking_url"], "userData": {"customData": {"hotelKey": h["key"]}}}
                      for h in targets],
        "maxReviewsPerHotel": c["max_reviews_per_hotel"],
        "sortReviewsBy": "f_recent_desc",
        "cutoffDate": cutoff,
        "reviewScores": c["booking_review_scores"],
    }, token, c["max_charge_usd_per_run"])
    by_url = {h["booking_url"]: h["key"] for h in targets}
    out = []
    for it in items:
        key = (it.get("customData") or {}).get("hotelKey") or by_url.get((it.get("startUrl") or "").split("?")[0])
        rating = it.get("rating")
        if not key or not it.get("id") or rating is None or rating > c["booking_max_rating"]:
            continue
        parts = [it.get("reviewTitle"), it.get("dislikedText"), it.get("likedText")]
        out.append({
            "id": f"booking:{it['id']}",
            "source": "booking",
            "hotelKey": key,
            "rating": rating,
            "ratingLabel": f"{rating:g}/10",
            "title": it.get("reviewTitle") or "",
            "text": "\n".join(f"{label} : {p}" for label, p in (("Négatif", parts[1]), ("Positif", parts[2])) if p),
            "reviewDate": parse_date(it.get("reviewDate")),
            "lang": it.get("reviewLanguage"),
            "url": next(h["booking_url"] for h in targets if h["key"] == key) + "#tab-reviews",
            "_classify_text": "\n".join(p for p in parts if p),
        })
    return out


def fetch_tripadvisor(hotels, cutoff, cfg, token):
    c = cfg["collect"]
    targets = [h for h in hotels if h.get("tripadvisor_url")]
    if not targets:
        return []
    items = apify.run_actor(cfg["actors"]["tripadvisor_reviews"], {
        "startUrls": [{"url": h["tripadvisor_url"]} for h in targets],
        "maxItemsPerQuery": c["max_reviews_per_hotel"],
        "lastReviewDate": cutoff,
        "reviewRatings": c["tripadvisor_review_ratings"],
        "reviewsLanguages": ["ALL_REVIEW_LANGUAGES"],
        "scrapeReviewerInfo": False,
    }, token, c["max_charge_usd_per_run"])
    by_id = {h.get("tripadvisor_id"): h["key"] for h in targets}
    out = []
    for it in items:
        loc = str(it.get("locationId") or find_key(it.get("placeInfo") or {}, ["id"]) or "")
        key = by_id.get(loc)
        rating = it.get("rating")
        if not key or not it.get("id") or rating is None or rating > c["tripadvisor_max_rating"]:
            continue
        out.append({
            "id": f"tripadvisor:{it['id']}",
            "source": "tripadvisor",
            "hotelKey": key,
            "rating": rating,
            "ratingLabel": f"{rating:g}/5",
            "title": it.get("title") or "",
            "text": it.get("text") or "",
            "reviewDate": parse_date(it.get("publishedDate")),
            "lang": it.get("lang"),
            "url": it.get("url"),
            "_classify_text": "\n".join(p for p in (it.get("title"), it.get("text")) if p),
        })
    return out


FETCHERS = {"booking": fetch_booking, "tripadvisor": fetch_tripadvisor}


def run(cfg, token, fetchers=FETCHERS):
    all_hotels, targets = select_hotels(cfg)
    reviews = load_json(REVIEWS_FILE, {"reviews": []})["reviews"]
    state = load_json(STATE_FILE, {})
    seen = {r["id"] for r in reviews}
    print(f"{len(targets)} hôtels suivis sur {len(all_hotels)} connus")

    new, errors = [], []
    added_at = now_iso()
    for source, fetch in fetchers.items():
        cutoff = cutoff_for(state, source, cfg)
        print(f"{source}: avis depuis le {cutoff}")
        try:
            fetched = fetch(targets, cutoff, cfg, token)
        except apify.ApifyError as e:
            errors.append(f"{source}: {e}")
            print(f"ERREUR {e}", file=sys.stderr)
            continue
        matched = 0
        for r in fetched:
            text = r.pop("_classify_text")
            if r["id"] in seen:
                continue
            found = classify(text)
            if not found:
                continue
            matched += 1
            seen.add(r["id"])
            h = all_hotels.get(r["hotelKey"], {})
            new.append({**r, **found, "addedAt": added_at, "hotelName": h.get("name")})
        print(f"{source}: {len(fetched)} avis négatifs lus, {matched} nouveaux sur la propreté")
        state.setdefault("sources", {})[source] = {"last_success": added_at, "fetched": len(fetched)}

    reviews = sorted(new + reviews, key=lambda r: r["addedAt"], reverse=True)
    reviews = reviews[: cfg["collect"]["keep_max_reviews"]]
    save_json(REVIEWS_FILE, {"updated_at": added_at, "reviews": reviews})
    state.update({"last_run": added_at, "last_new": len(new), "errors": errors,
                  "hotels_tracked": len(targets)})
    save_json(STATE_FILE, state)
    return new, all_hotels, errors


def main():
    cfg = load_config()
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("APIFY_TOKEN absent : ajoutez le secret dans GitHub pour activer la collecte.")
        return 0
    new, hotels, errors = run(cfg, token)
    print(f"Total : {len(new)} nouveaux avis.")
    if new:
        try:
            send_email(new, hotels, site_url(cfg))
        except Exception as e:  # l'e-mail ne doit pas faire perdre la collecte
            print(f"ERREUR e-mail : {e}", file=sys.stderr)
    return 1 if len(errors) == len(FETCHERS) else 0


if __name__ == "__main__":
    sys.exit(main())
