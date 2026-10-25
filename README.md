# Veille propreté · Hôtels Île-de-France

Site qui recense les avis négatifs **Booking** et **TripAdvisor** sur des hôtels d'Île-de-France
quand ils signalent un problème de propreté sur les **moquettes, sièges, canapés, rideaux, têtes de lit et textiles**
(et les punaises de lit). Les avis sont triables par **date d'ajout** et par **taille de l'hôtel** (nombre de chambres).
Un **e-mail** est envoyé à chaque nouvelle détection.

## Fonctionnement

```
GitHub Actions (2×/jour)
  └─ scraper/collect.py
       ├─ Apify : derniers avis négatifs Booking (note ≤ 7/10) et TripAdvisor (1–2/5)
       ├─ classify.py : garde les avis qui associent un élément textile ET un mot de saleté
       ├─ docs/data/reviews.json  ← nouveaux avis ajoutés (dédoublonnés)
       └─ e-mail récapitulatif (SMTP)
  └─ publication de docs/ sur GitHub Pages

GitHub Actions (1×/mois)
  └─ scraper/discover.py
       ├─ Apify : hôtels Booking + TripAdvisor d'Île-de-France
       ├─ registre officiel Atout France (data.gouv.fr) → nombre de chambres, étoiles
       └─ docs/data/hotels.json
```

## Mise en route

1. **Compte Apify** : créer un compte sur apify.com, puis copier le jeton (*Settings → API & Integrations*).
2. **Secrets GitHub** (*Settings → Secrets and variables → Actions*) :

   | Secret | Exemple |
   |---|---|
   | `APIFY_TOKEN` | `apify_api_…` |
   | `SMTP_HOST` | `smtp.gmail.com` |
   | `SMTP_PORT` | `465` |
   | `SMTP_USER` | `mon.adresse@gmail.com` |
   | `SMTP_PASSWORD` | mot de passe d'application Gmail (pas le mot de passe du compte) |
   | `MAIL_TO` | adresse(s) qui reçoivent les alertes, séparées par des virgules |

3. Onglet **Actions** → *Découverte des hôtels* → **Run workflow** (constitue la liste des hôtels).
4. Puis *Collecte des avis* → **Run workflow** pour un premier passage (ensuite automatique).

## Réglages (`config.json`)

| Clé | Rôle |
|---|---|
| `collect.max_hotels` | nombre d'hôtels suivis (les plus grands d'abord). **Principal levier de coût.** |
| `collect.min_rooms` | ignorer les hôtels plus petits que ce nombre de chambres |
| `collect.booking_review_scores` | notes Booking collectées (`review_adj_poor` = 3–5, `review_adj_average_passable` = 5–7) |
| `collect.tripadvisor_review_ratings` | notes TripAdvisor collectées (`"1"`, `"2"`…) |
| `collect.max_charge_usd_per_run` | plafond de dépense Apify par lancement et par site |
| `collect.first_run_lookback_days` | profondeur d'historique au premier lancement |
| `discovery.max_hotels_per_source` | nombre d'hôtels listés par site lors de la découverte |

La fréquence se règle dans `.github/workflows/collect.yml` (ligne `cron`).
Les mots-clés détectés sont dans `scraper/classify.py`.

Pour suivre un hôtel précis, l'ajouter dans `hotels_manuels.json` :

```json
[{"key": "manuel-1", "name": "Nom de l'hôtel", "postcode": "75008",
  "booking_url": "https://www.booking.com/hotel/fr/....html",
  "tripadvisor_url": "https://www.tripadvisor.fr/Hotel_Review-g187147-d123456-Reviews-....html",
  "tripadvisor_id": "123456"}]
```

## Coûts (tarif Apify « Free » : 5 $ de crédit offert par mois)

- Avis Booking : ~0,002 $ l'avis · avis TripAdvisor : ~0,005 $ l'avis (seuls les avis négatifs récents sont payés).
- Découverte : ~0,005 $ par hôtel listé et par site (≈ 4 $ pour 400 hôtels × 2 sites, une fois par mois).
- Chaque lancement est plafonné par `max_charge_usd_per_run`.

## Tests

```bash
python -m unittest discover tests
```

## Avertissement

Les avis proviennent de pages publiques, récupérées par un service tiers (Apify).
Les conditions d'utilisation de Booking.com et de TripAdvisor encadrent la réutilisation de leurs contenus :
vérifiez qu'elles autorisent l'usage que vous en faites, en particulier pour un usage commercial.
Les avis sont des opinions de clients, non vérifiées ; la détection par mots-clés peut produire des faux positifs.
