"""Chemins, lecture/écriture JSON et petits utilitaires partagés."""
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
HOTELS_FILE = DATA_DIR / "hotels.json"
REVIEWS_FILE = DATA_DIR / "reviews.json"
STATE_FILE = DATA_DIR / "state.json"
MANUAL_HOTELS_FILE = ROOT / "hotels_manuels.json"


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def load_config():
    return load_json(ROOT / "config.json", {})


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fold(text):
    """Minuscules sans accents, pour les comparaisons."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def parse_date(value):
    """Renvoie 'AAAA-MM-JJ' à partir des formats renvoyés par les actors, ou None."""
    if not value:
        return None
    s = str(value)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def find_key(obj, names, depth=0):
    """Cherche récursivement la première valeur non vide d'une des clés `names`.

    Les actors Apify ne documentent pas tous leur format de sortie : on reste tolérant.
    """
    if depth > 4:
        return None
    if isinstance(obj, dict):
        for n in names:
            v = obj.get(n)
            if v not in (None, "", [], {}):
                return v
        for v in obj.values():
            r = find_key(v, names, depth + 1)
            if r not in (None, "", [], {}):
                return r
    elif isinstance(obj, list):
        for v in obj[:5]:
            r = find_key(v, names, depth + 1)
            if r not in (None, "", [], {}):
                return r
    return None


def extract_postcode(*values):
    for v in values:
        if isinstance(v, dict):
            v = " ".join(str(x) for x in v.values() if x)
        m = re.search(r"\b(75|77|78|9[1-5])\s?(\d{3})\b", str(v or ""))
        if m:
            return m.group(1) + m.group(2)
    return None


def site_url(config):
    if config.get("site_url"):
        return config["site_url"].rstrip("/") + "/"
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner.lower()}.github.io/{name}/"
    return ""
