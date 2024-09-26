"""

    mtg.deck.scrapers.mtgarenapro.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGArena.Pro decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.utils.scrape import ScrapingError, getsoup
from mtg.scryfall import Card

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MtgArenaProScraper(DeckScraper):
    """Scraper of MTGArena.Pro decklist page.
    """

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgarena.pro/decks/" in url

    def _get_json(self) -> Json:
        return self.dissect_js("var precachedDeck=", '"card_ids":', lambda s: s + '"card_ids":[]}')

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._json_data = self._get_json()
        if not self._json_data or not self._json_data.get("deck_order"):
            raise ScrapingError("Data not available")

    def _parse_fmt(self) -> str:
        if self._json_data["explorer"]:
            return "explorer"
        elif self._json_data["timeless"]:
            return "timeless"
        elif self._json_data["alchemy"]:
            return "alchemy"
        elif self._json_data["brawl"]:
            if self._json_data["standard"]:
                return "standardbrawl"
            return "brawl"
        elif self._json_data["historic"]:
            return "historic"
        elif self._json_data["standard"]:
            return "standard"
        return ""

    def _parse_metadata(self) -> None:  # override
        self._metadata["author"] = self._json_data["author"]
        self._metadata["name"] = self._json_data["humanname"]
        if fmt := self._parse_fmt():
            self._update_fmt(fmt)
        self._metadata["date"] = datetime.utcfromtimestamp(self._json_data["date"]).date()

    @classmethod
    def _parse_card_json(cls, card_json: Json) -> list[Card]:
        name = card_json["name"]
        quantity = card_json["cardnum"]
        card = cls.find_card(name)
        return cls.get_playset(card, quantity)

    def _parse_deck(self) -> None:  # override
        for card_json in self._json_data["deck_order"]:
            self._maindeck.extend(self._parse_card_json(card_json))
        for card_json in self._json_data["sidedeck_order"]:
            self._sideboard.extend(self._parse_card_json(card_json))
        for card_json in self._json_data["commander_order"]:
            self._set_commander(self._parse_card_json(card_json)[0])