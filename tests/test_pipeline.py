import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scraper import collect, common
from scraper.classify import classify
from scraper.hotels import Matcher

CFG = common.load_config()


class ClassifyTest(unittest.TestCase):
    def test_matches(self):
        cases = {
            "La moquette était pleine de taches, dégoûtant.": "Moquette / tapis",
            "The curtains were dusty and smelled of smoke.": "Rideaux / voilages",
            "Le fauteuil de la chambre était crasseux.": "Sièges / canapés",
            "Nous avons trouvé des punaises de lit.": "Punaises de lit",
            "Tête de lit tachée et matelas usé.": "Literie / tête de lit",
        }
        for text, cat in cases.items():
            r = classify(text)
            self.assertIsNotNone(r, text)
            self.assertIn(cat, r["categories"], text)

    def test_ignores(self):
        for text in ["Personnel adorable, petit-déjeuner sale et froid.",
                     "Chambre bruyante, le rideau ne fermait pas.",
                     "Une tendance à la saleté dans la salle de bain."]:
            self.assertIsNone(classify(text), text)


class MatcherTest(unittest.TestCase):
    def test_match(self):
        m = Matcher([{"name": "HÔTEL LUTETIA", "postcode": "75006", "rooms": 184},
                     {"name": "HOTEL DU LOUVRE", "postcode": "75001", "rooms": 164}])
        self.assertEqual(m.match("Hotel Lutetia Paris", "75006")["rooms"], 184)
        self.assertIsNone(m.match("Ibis Budget", "75006"))


class CollectTest(unittest.TestCase):
    def test_run_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            common.save_json(d / "hotels.json", {"hotels": [
                {"key": "af-1", "name": "Grand Hôtel", "rooms": 300,
                 "booking_url": "https://www.booking.com/hotel/fr/grand.html",
                 "tripadvisor_url": "https://www.tripadvisor.fr/Hotel_Review-g1-d42-Reviews-X.html",
                 "tripadvisor_id": "42"},
                {"key": "af-2", "name": "Petit Hôtel", "rooms": 12,
                 "booking_url": "https://www.booking.com/hotel/fr/petit.html"}]})
            booking = [
                {"id": "b1", "rating": 4, "dislikedText": "Moquette tachée et rideaux poussiéreux",
                 "reviewDate": "2026-10-20", "customData": {"hotelKey": "af-1"}},
                {"id": "b2", "rating": 9, "dislikedText": "Moquette sale", "customData": {"hotelKey": "af-1"}},
                {"id": "b3", "rating": 5, "dislikedText": "Trop cher", "customData": {"hotelKey": "af-2"}},
            ]
            trip = [{"id": "t1", "rating": 1, "locationId": "42", "text": "The armchair was filthy.",
                     "publishedDate": "2026-10-21", "url": "https://ta/r/t1"}]

            def fake(actor, inp, token, cap):
                return booking if "booking" in actor else trip

            with mock.patch.multiple(collect, HOTELS_FILE=d / "hotels.json", REVIEWS_FILE=d / "r.json",
                                     STATE_FILE=d / "s.json", MANUAL_HOTELS_FILE=d / "m.json"), \
                    mock.patch.object(collect.apify, "run_actor", side_effect=fake):
                new, _, errors = collect.run(CFG, "x")
                self.assertEqual(sorted(r["id"] for r in new), ["booking:b1", "tripadvisor:t1"])
                self.assertEqual(errors, [])
                again, _, _ = collect.run(CFG, "x")
                self.assertEqual(again, [])
                self.assertEqual(len(common.load_json(d / "r.json", {})["reviews"]), 2)


if __name__ == "__main__":
    unittest.main()
