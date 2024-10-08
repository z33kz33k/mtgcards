"""

    mtg.deck.scrapers.deckstats.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Deckstats.net decklists.

    @author: z33k

"""
import itertools
import logging
from datetime import datetime

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.utils.scrape import ScrapingError, getsoup
from mtg.scryfall import Card

_log = logging.getLogger(__name__)


_FORMATS = {
    2: "vintage",
    3: "legacy",
    4: "modern",
    6: "standard",
    9: "pauper",
    10: "commander",
    15: "penny",
    16: "brawl",
    17: "oathbreaker",
    18: "pioneer",
    19: "historic",
    21: "duel",
    22: "explorer",
}


@DeckScraper.registered
class DeckstatsScraper(DeckScraper):
    """Scraper of Deckstats.net decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        if not "deckstats.net/decks/" in url:
            return False
        url = DeckScraper.sanitize_url(url)
        _, right_part = url.split("deckstats.net/decks/")
        right_part = "deckstats.net/decks/" + right_part
        return len(right_part.split("/")) > 3

    def _get_json(self) -> Json:
        return self.dissect_js(
            "init_deck_data(", "deck_display();", lambda s: s.removesuffix(", false);"))

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._json_data = self._get_json()

    def _parse_metadata(self) -> None:  # override
        author_text = self._soup.find("div", id="deck_folder_subtitle").text.strip()
        self._metadata["author"] = author_text.removeprefix("in  ").removesuffix("'s Decks")
        self._metadata["name"] = self._json_data["name"]
        self._metadata["views"] = self._json_data["views"]
        fmt = _FORMATS.get(self._json_data["format_id"])
        if fmt:
            self._update_fmt(fmt)
        self._metadata["date"] = datetime.utcfromtimestamp(self._json_data["updated"]).date()
        if tags := self._json_data.get("tags"):
            self._metadata["tags"] = tags
        if description := self._json_data.get("description"):
            self._metadata["description"] = description

    def _parse_card_json(self, card_json: Json) -> list[Card]:
        name = card_json["name"]
        quantity = card_json["amount"]
        if tcgplayer_id := card_json["data"].get("price_tcgplayer_id"):
            tcgplayer_id = int(tcgplayer_id)
        if mtgo_id := card_json["data"].get("price_cardhoarder_id"):
            mtgo_id = int(mtgo_id)
        card = self.find_card(name, tcgplayer_id=tcgplayer_id, mtgo_id=mtgo_id)
        if card_json.get("isCommander"):
            self._set_commander(card)
        return self.get_playset(card, quantity)

    def _parse_deck(self) -> None:  # override
        cards = itertools.chain(
            *[section["cards"] for section in self._json_data["sections"]])
        for card_json in cards:
            self._maindeck.extend(self._parse_card_json(card_json))
        if sideboard := self._json_data.get("sideboard"):
            for card_json in sideboard:
                self._sideboard.extend(self._parse_card_json(card_json))
