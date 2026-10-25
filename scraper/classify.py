"""Détection des plaintes de propreté visant les textiles et le mobilier.

Une phrase est retenue si elle cite un élément (moquette, siège, rideau…) ET un mot de saleté
(taché, sale, odeur…). Les textes sont comparés en minuscules, sans accents.
Les mots se terminant par « * » sont des préfixes.
"""
import re

from .common import fold

ITEMS = {
    "Moquette / tapis": [
        "moquette*", "tapis", "sol textile", "carpet*", "rug", "rugs", "moqueta*", "alfombra*",
        "teppich*", "tappet*",
    ],
    "Sièges / canapés": [
        "fauteuil*", "siege*", "chaise*", "canape*", "sofa*", "banquette*", "pouf*", "chair*",
        "armchair*", "couch", "seat*", "upholster*", "sillon*", "silla*", "poltron*", "divan*",
        "sedi*", "sessel*", "stuhl*", "stuhle*",
    ],
    "Rideaux / voilages": [
        "rideau*", "voilage*", "tenture*", "curtain*", "drape*", "cortina*", "tenda", "tende",
        "vorhang*", "vorhange*", "gardine*",
    ],
    "Literie / tête de lit": [
        "tete de lit", "tete du lit", "couvre-lit*", "couvre lit*", "dessus de lit", "jete de lit",
        "plaid*", "coussin*", "matelas", "headboard*", "bedspread*", "bed cover*",
        "cushion*", "mattress*", "colcha*", "cabecero*", "copriletto", "testiera*", "materass*",
        "colchon*", "tagesdecke*", "kopfteil*", "matratze*",
    ],
    "Tissus (général)": [
        "tissu*", "textile*", "tapisserie*", "fabric*", "tela*", "tessut*", "stoff*",
    ],
}

DIRT = [
    "sale", "sales", "salete*", "salissure*", "sali", "salie*", "salis", "crasse*", "crado*", "cradingue*",
    "tache*", "aureole*", "poussiere*", "poussiereu*", "odeur*", "puant*", "pue", "puait",
    "moisi*", "cheveu*", "poil*", "miette*", "usee*", "tres use", "tout use", "elime*", "degoutant*",
    "degueu*", "repugnant*", "douteu*", "jauni*", "collant*", "immonde*", "infect*", "vomi*",
    "brulure*", "acarien*", "graisseu*", "pas propre*", "pas nettoye*", "jamais nettoye*",
    "dirty", "dirt", "stain*", "filth*", "grim*", "dust*", "smell*", "stink*", "stank",
    "mould*", "mold*", "musty", "hair", "hairs", "crumb*", "worn", "threadbare", "disgust*",
    "gross", "sticky", "greasy", "vomit*", "burn mark*", "not clean*", "unclean*",
    "sucio*", "suciedad*", "mancha*", "polvo*", "olor*", "sporc*", "macchi*", "polver*",
    "odore*", "puzz*", "schmutz*", "fleck*", "staub*", "geruch*", "dreckig*",
]

# Signalements suffisants à eux seuls (presque toujours liés aux textiles).
STANDALONE = {
    "Punaises de lit": ["punaise* de lit", "punaise* des lits", "bed bug*", "bedbug*",
                        "chinche*", "cimici", "bettwanze*"],
}


def _compile(words):
    parts = []
    for w in words:
        parts.append(re.escape(fold(w)).replace(r"\ ", r"\s+").replace(r"\*", r"\w*"))
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)")


ITEM_RE = {cat: _compile(words) for cat, words in ITEMS.items()}
DIRT_RE = _compile(DIRT)
STANDALONE_RE = {cat: _compile(words) for cat, words in STANDALONE.items()}
SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")


def classify(text):
    """Renvoie {'categories': [...], 'excerpts': [...], 'terms': [...]} ou None."""
    categories, excerpts, terms = [], [], set()
    for sentence in SENTENCE_SPLIT.split(text or ""):
        s = sentence.strip()
        if not s:
            continue
        f = fold(s)
        hit = False
        for cat, rx in STANDALONE_RE.items():
            found = rx.findall(f)
            if found:
                hit = True
                terms.update(found)
                if cat not in categories:
                    categories.append(cat)
        dirt = DIRT_RE.findall(f)
        if dirt:
            for cat, rx in ITEM_RE.items():
                found = rx.findall(f)
                if found:
                    hit = True
                    terms.update(found)
                    terms.update(dirt)
                    if cat not in categories:
                        categories.append(cat)
        if hit and s not in excerpts:
            excerpts.append(s[:400])
    if not categories:
        return None
    return {"categories": categories, "excerpts": excerpts[:4], "terms": sorted(terms)}
