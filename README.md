# Veille propreté · Hôtels Île-de-France

Site qui recense les avis négatifs **Booking** et **TripAdvisor** sur des hôtels d'Île-de-France
quand ils signalent un problème de propreté sur les **moquettes, sièges, canapés, rideaux, têtes de lit et textiles**
(et les punaises de lit). Les avis sont triables par **date d'ajout** et par **taille de l'hôtel** (nombre de chambres).
Un **e-mail** est envoyé à chaque nouvelle détection.

Réglé en **mode gratuit** : les 50 plus grands hôtels d'Île-de-France, une collecte par jour,
pour rester dans le crédit gratuit mensuel d'Apify (5 $).

## Fonctionnement

```
GitHub Actions (1×/jour, 5 h UTC)
  └─ scraper/collect.py
       ├─ hotels_manuels.json : les hôtels suivis (liens Booking / TripAdvisor, nombre de chambres)
       ├─ Apify : derniers avis négatifs Booking (note ≤ 7/10) et TripAdvisor (1–2/5)
       ├─ classify.py : garde les avis qui associent un élément textile ET un mot de saleté
       ├─ docs/data/reviews.json  ← nouveaux avis ajoutés (dédoublonnés)
       └─ e-mail récapitulatif (SMTP)
  └─ publication de docs/ sur GitHub Pages
```

Le nombre de chambres vient du registre officiel des hôtels classés (Atout France, data.gouv.fr).

## Mise en route

1. **Compte Apify** (gratuit) : créer un compte sur apify.com, puis copier le jeton (*Settings → API & Integrations*).
2. **Secrets GitHub** (*Settings → Secrets and variables → Actions → New repository secret*) :

   | Secret | Exemple |
   |---|---|
   | `APIFY_TOKEN` | `apify_api_…` |
   | `SMTP_HOST` | `smtp.gmail.com` |
   | `SMTP_PORT` | `465` |
   | `SMTP_USER` | `mon.adresse@gmail.com` |
   | `SMTP_PASSWORD` | mot de passe d'application Gmail (pas le mot de passe du compte) |
   | `MAIL_TO` | adresse(s) qui reçoivent les alertes, séparées par des virgules |

3. Onglet **Actions** → *Collecte des avis* → **Run workflow** pour un premier passage (ensuite automatique chaque jour).

## Hôtels suivis (`hotels_manuels.json`)

50 hôtels, du plus grand (Disney Newport Bay Club, 1 097 chambres) au 50ᵉ (~305 chambres).
Pour en ajouter ou en retirer, modifier ce fichier :

```json
{"key": "manuel-1", "name": "Nom de l'hôtel", "postcode": "75008", "city": "Paris", "rooms": 120, "stars": 4,
 "booking_url": "https://www.booking.com/hotel/fr/....html",
 "tripadvisor_url": "https://www.tripadvisor.com/Hotel_Review-g187147-d123456-Reviews-....html",
 "tripadvisor_id": "123456"}
```

`tripadvisor_id` est le nombre après `-d` dans l'adresse TripAdvisor. Un hôtel sans `booking_url` n'est suivi que sur TripAdvisor.

## Réglages (`config.json` → `collect`)

| Clé | Rôle |
|---|---|
| `max_hotels` | nombre d'hôtels suivis (les plus grands d'abord). **Principal levier de coût.** |
| `min_rooms` | ignorer les hôtels plus petits que ce nombre de chambres |
| `booking_review_scores` | notes Booking collectées (`review_adj_poor` = 3–5, `review_adj_average_passable` = 5–7) |
| `tripadvisor_review_ratings` | notes TripAdvisor collectées (`"1"`, `"2"`…) |
| `max_charge_usd_per_run` | plafond de dépense Apify par jour et par site |
| `first_run_max_charge_usd` | plafond du tout premier passage (qui remonte `first_run_lookback_days` jours) |

La fréquence se règle dans `.github/workflows/collect.yml` (ligne `cron`).
Les mots-clés détectés sont dans `scraper/classify.py`.

## Coûts

- Avis Booking : ~0,002 $ l'avis · avis TripAdvisor : ~0,005 $ l'avis (seuls les avis négatifs récents sont payés).
- Plafonds : 0,40 $ par site au premier passage, puis 0,07 $ par site et par jour, soit au plus ~4,2 $/mois
  hors premier passage. Sur l'offre gratuite d'Apify, les lancements sont bloqués une fois le crédit
  mensuel épuisé, au lieu d'être facturés (à vérifier dans *Billing* sur apify.com).
- Si un plafond est atteint, les avis restants de la journée ne sont pas récupérés.

`scraper/discover.py` (découverte automatique de tous les hôtels via Apify, ~4 $ par lancement) reste disponible
pour un usage payant : `python -m scraper.discover`.

## Tests

```bash
python -m unittest discover tests
```

## Avertissement

Les avis proviennent de pages publiques, récupérées par un service tiers (Apify).
Les conditions d'utilisation de Booking.com et de TripAdvisor encadrent la réutilisation de leurs contenus :
vérifiez qu'elles autorisent l'usage que vous en faites, en particulier pour un usage commercial.
Les avis sont des opinions de clients, non vérifiées ; la détection par mots-clés peut produire des faux positifs.
