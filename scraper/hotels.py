"""Référentiel des hôtels classés (Atout France) et rapprochement par nom + code postal."""
import csv
import hashlib
import io
import re
import urllib.request
from difflib import SequenceMatcher

from .common import fold

STOPWORDS = {
    "hotel", "hotels", "the", "le", "la", "les", "l", "de", "du", "des", "d", "et", "and", "by",
    "paris", "spa", "a", "au", "aux", "en", "residence", "suites", "suite",
}


def norm_name(name):
    words = re.findall(r"[a-z0-9]+", fold(name))
    kept = [w for w in words if w not in STOPWORDS]
    return " ".join(sorted(kept or words))


def load_atout_france(url, prefixes):
    """Hôtels classés de la région : liste de dicts {af_id, name, postcode, city, rooms, stars}."""
    with urllib.request.urlopen(url, timeout=120) as resp:
        text = resp.read().decode("utf-8-sig")
    rows = csv.reader(io.StringIO(text), delimiter=";")
    header = [fold(h) for h in next(rows)]

    def col(start):
        return next(i for i, h in enumerate(header) if h.startswith(start))

    i_type, i_class, i_name = col("typologie"), col("classement"), col("nom commercial")
    i_addr, i_cp, i_city, i_rooms = col("adresse"), col("code postal"), col("commune"), col("nombre de chambres")
    i_web = col("site internet")

    hotels = []
    for r in rows:
        if len(r) <= i_rooms or not fold(r[i_type]).startswith("hotel"):
            continue
        cp = r[i_cp].strip()
        if cp[:2] not in prefixes:
            continue
        stars = re.match(r"\d", r[i_class])
        hotels.append({
            "af_id": hashlib.sha1(f"{r[i_name]}|{cp}".encode()).hexdigest()[:10],
            "name": r[i_name].strip(),
            "address": r[i_addr].strip(),
            "postcode": cp,
            "city": r[i_city].strip().title(),
            "rooms": int(r[i_rooms]) if r[i_rooms].strip().isdigit() else None,
            "stars": int(stars.group(0)) if stars else None,
            "website": r[i_web].strip() if r[i_web].strip() not in ("", "-") else None,
        })
    return hotels


class Matcher:
    def __init__(self, af_hotels):
        self.by_cp = {}
        for h in af_hotels:
            h["_n"] = norm_name(h["name"])
            self.by_cp.setdefault(h["postcode"], []).append(h)
        self.all = af_hotels

    def match(self, name, postcode):
        n = norm_name(name)
        if not n:
            return None
        if postcode and postcode in self.by_cp:
            best = max(self.by_cp[postcode], key=lambda h: SequenceMatcher(None, n, h["_n"]).ratio())
            if SequenceMatcher(None, n, best["_n"]).ratio() >= 0.6:
                return best
            return None
        # Sans code postal : on exige une correspondance quasi exacte.
        best, score = None, 0
        for h in self.all:
            s = SequenceMatcher(None, n, h["_n"]).ratio()
            if s > score:
                best, score = h, s
        return best if score >= 0.92 else None
