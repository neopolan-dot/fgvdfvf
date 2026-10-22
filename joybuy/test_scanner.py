import unittest
from joybuy.scanner import normalize_link, parse_card, selected_evidence, tab_pattern


class DealSafetyTests(unittest.TestCase):
    def test_today_tabs_do_not_match_tomorrow(self):
        for hour, label in ((20,"8:00pm"),(21,"9:00pm"),(22,"10:00pm")):
            self.assertRegex(label, tab_pattern(hour))
            self.assertIsNone(tab_pattern(hour).fullmatch(label + " morgen"))
            self.assertIsNone(tab_pattern(hour).fullmatch("morgen " + label))

    def test_external_urls_are_not_published(self):
        self.assertIsNone(normalize_link("https://joybuy.de.example.org/dp/item/123"))
        self.assertIsNone(normalize_link("javascript:alert(1)"))
        self.assertEqual(normalize_link("https://m.joybuy.de/dp/item/123?tracking=1#top"),
                         "https://m.joybuy.de/dp/item/123")

    def test_reference_price_is_not_taken_as_action_price(self):
        result = parse_card({"id":"1","url":"https://m.joybuy.de/dp/item/1",
            "text":"35% Rabatt TV Nur noch 9 Artikel verfügbar UVP:249,00 € 159,98 € Jetzt kaufen"})
        self.assertEqual(result["displayed_price"], "159,98€")
        self.assertEqual(result["reference_price"], "249,00€")
        self.assertEqual(result["displayed_stock"], 9)

    def test_no_action_price_is_not_fabricated(self):
        result = parse_card({"id":"1","url":"https://m.joybuy.de/dp/item/1", "text":"Produkt UVP:99,99 € Erinnern"})
        self.assertIsNone(result["displayed_price"])

    def test_selection_must_be_unique(self):
        states = {20:[{"selected":"true"}],21:[{"selected":"false"}],22:[]}
        self.assertIsNotNone(selected_evidence(states,20))
        self.assertIsNone(selected_evidence(states,21))
        states[21] = [{"selected":"true"}]
        self.assertIsNone(selected_evidence(states,20))


if __name__ == "__main__":
    unittest.main()
