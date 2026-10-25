"""Constitue la liste des hôtels d'Île-de-France présents sur Booking et TripAdvisor.

À lancer ponctuellement (mensuel) : python -m scraper.discover
"""
import hashlib
import os
import re
import sys

from . import apify
from .common import (HOTELS_FILE, MANUAL_HOTELS_FILE, extract_postcode, find_key, load_config,
                     load_json, now_iso, save_json)
from .hotels import Matcher, load_atout_france


def clean_url(url):
    return re.sub(r"[?#].*$", "", url or "") or None


def tripadvisor_id(url):
    m = re.search(r"-d(\d+)-", url or "")
    return m.group(1) if m else None


def booking_items(cfg, token):
    d = cfg["discovery"]
    items = apify.run_actor(cfg["actors"]["booking_search"], {
        "search": d["booking_search"],
        "maxItems": d["max_hotels_per_source"],
        "propertyType": "Hotels",
        "language": "fr",
        "currency": "EUR",
    }, token, d["max_charge_usd_per_run"])
    out = []
    for it in items:
        url = clean_url(find_key(it, ["url", "hotelUrl", "link"]))
        if not url or "booking.com/hotel/" not in url:
            continue
        out.append({
            "name": find_key(it, ["name", "title", "hotelName"]) or "",
            "postcode": extract_postcode(find_key(it, ["postalCode", "postcode", "zip"]),
                                         find_key(it, ["address", "fullAddress"])),
            "rooms": _int(find_key(it, ["numberOfRooms", "roomsCount", "totalRooms"])),
            "url": url,
        })
    return out


def tripadvisor_items(cfg, token):
    d = cfg["discovery"]
    items = apify.run_actor(cfg["actors"]["tripadvisor_search"], {
        "query": d["tripadvisor_query"],
        "maxItemsPerQuery": d["max_hotels_per_source"],
        "includeHotels": True,
        "includeRestaurants": False,
        "includeAttractions": False,
        "includeTags": False,
        "includeNearbyResults": False,
        "language": "fr",
        "currency": "EUR",
    }, token, d["max_charge_usd_per_run"])
    out = []
    for it in items:
        url = clean_url(find_key(it, ["webUrl", "url"]))
        if not url or "Hotel_Review" not in url:
            continue
        out.append({
            "name": find_key(it, ["name", "title"]) or "",
            "postcode": extract_postcode(find_key(it, ["postalcode", "postalCode"]),
                                         find_key(it, ["address", "addressObj"])),
            "rooms": _int(find_key(it, ["numberOfRooms", "roomsCount"])),
            "url": url,
        })
    return out


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def merge(existing, found, source, matcher, prefixes):
    """Ajoute/actualise les hôtels trouvés sur une source dans le dictionnaire `existing`."""
    url_field = f"{source}_url"
    by_url = {h.get(url_field): k for k, h in existing.items() if h.get(url_field)}
    added = 0
    for f in found:
        if f["postcode"] and f["postcode"][:2] not in prefixes:
            continue
        af = matcher.match(f["name"], f["postcode"])
        key = by_url.get(f["url"]) or (f"af-{af['af_id']}" if af else None)
        if not key:
            key = f"bk-{hashlib.sha1(f['url'].encode()).hexdigest()[:10]}" if source == "booking" else f"ta-{tripadvisor_id(f['url'])}"
        h = existing.setdefault(key, {"key": key})
        if not h.get(url_field):
            added += 1
        h[url_field] = f["url"]
        if source == "tripadvisor":
            h["tripadvisor_id"] = tripadvisor_id(f["url"])
        if af:
            for k in ("name", "address", "postcode", "city", "rooms", "stars"):
                if af.get(k) is not None:
                    h[k] = af[k]
            h["rooms_source"] = "Atout France"
        else:
            h.setdefault("name", f["name"])
            h.setdefault("postcode", f["postcode"])
            if f["rooms"] and not h.get("rooms"):
                h["rooms"] = f["rooms"]
                h["rooms_source"] = source
    return added


def main():
    cfg = load_config()
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("APIFY_TOKEN absent : découverte ignorée.")
        return 0
    prefixes = tuple(cfg["region_postcode_prefixes"])

    print("Chargement du référentiel Atout France…")
    matcher = Matcher(load_atout_france(cfg["discovery"]["atout_france_csv"], prefixes))
    print(f"  {len(matcher.all)} hôtels classés dans la région")

    data = load_json(HOTELS_FILE, {"hotels": []})
    existing = {h["key"]: h for h in data["hotels"]}
    for h in load_json(MANUAL_HOTELS_FILE, []):
        af = matcher.match(h.get("name", ""), h.get("postcode"))
        if af and not h.get("rooms"):
            h = {**h, "rooms": af["rooms"], "stars": af["stars"], "rooms_source": "Atout France"}
        existing.setdefault(h["key"], {}).update(h)

    errors = 0
    for source, fn in (("booking", booking_items), ("tripadvisor", tripadvisor_items)):
        try:
            found = fn(cfg, token)
            added = merge(existing, found, source, matcher, prefixes)
            print(f"{source}: {len(found)} hôtels trouvés, {added} nouveaux liens")
        except apify.ApifyError as e:
            errors += 1
            print(f"ERREUR {source}: {e}", file=sys.stderr)

    hotels = sorted(existing.values(), key=lambda h: (-(h.get("rooms") or 0), h.get("name", "")))
    save_json(HOTELS_FILE, {"updated_at": now_iso(), "hotels": hotels})
    with_rooms = sum(1 for h in hotels if h.get("rooms"))
    print(f"{len(hotels)} hôtels enregistrés ({with_rooms} avec nombre de chambres)")
    return 1 if errors == 2 else 0


if __name__ == "__main__":
    sys.exit(main())
