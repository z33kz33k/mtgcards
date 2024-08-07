"""

    mtgcards.decks.moxfield.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Moxfield decklist page.

    @author: z33k

"""
import logging
from datetime import datetime

from mtgcards.const import Json
from mtgcards.decks import Deck, InvalidDeck, DeckScraper, get_playset
from mtgcards.scryfall import Card, all_formats, all_set_codes
from mtgcards.utils.scrape import timed_request


_log = logging.getLogger(__name__)


# no apparent ways to scrape an Arena list
class MoxfieldScraper(DeckScraper):
    """Scraper of Moxfield decklist page.
    """
    API_URL_TEMPLATE = "https://api2.moxfield.com/v3/decks/all/{}"
    HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Authorization": "Bearer undefined",
        "Cookie": "_ga=GA1.1.1202643745.1722108358; "
                  "ncmp.domain=moxfield.com; _ga_BW2XPQDNK2=GS1.1.1722108357.1.1.1722108385.0.0.0",
        "Origin": "https://www.moxfield.com",
        "Priority": "u=1, i",
        "Referer": "https://www.moxfield.com/",
        "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Google Chrome\";v=\"126\"",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "\"Linux\"",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0.0.0 Safari/537.36",
        "X-Moxfield-Version": "2024.07.26.5",
    }

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        *_, self._decklist_id = url.split("/")
        self._json_data = timed_request(
            self.API_URL_TEMPLATE.format(self._decklist_id), return_json=True,
            headers=self.HEADERS)
        self._scrape_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.moxfield.com/decks/" in url

    def _scrape_metadata(self) -> None:  # override
        fmt = self._json_data["format"]
        self._update_fmt(fmt)
        name = self._json_data["name"]
        if " - " in name:
            *_, name = name.split(" - ")
        self._metadata["name"] = name
        self._metadata["likes"] = self._json_data["likeCount"]
        self._metadata["views"] = self._json_data["viewCount"]
        self._metadata["comments"] = self._json_data["commentCount"]
        if not self.author:
            self._metadata["author"] = self._json_data["createdByUser"]["displayName"]
        self._metadata["date"] = datetime.strptime(
            self._json_data["lastUpdatedAtUtc"], "%Y-%m-%dT%H:%M:%S.%fZ").date()
        if desc := self._json_data["description"]:
            self._metadata["description"] = desc

    def _parse_card(self, json_card: Json) -> list[Card]:
        scryfall_id = json_card["card"]["scryfall_id"]
        quantity = json_card["quantity"]
        playset = self._get_playset_by_id(scryfall_id, quantity)
        if playset:
            return playset
        set_code, name = json_card["card"]["set"], json_card["card"]["name"]
        set_code = set_code if set_code in set(all_set_codes()) else ""
        return get_playset(name, quantity, set_code, self.fmt)

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander, companion = [], [], None, None
        for card in self._json_data["boards"]["mainboard"]["cards"].values():
            mainboard.extend(self._parse_card(card))
        for card in self._json_data["boards"]["sideboard"]["cards"].values():
            sideboard.extend(self._parse_card(card))
        if self._json_data["boards"]["commanders"]["cards"]:
            card = next(iter(self._json_data["boards"]["commanders"]["cards"].items()))[1]
            result = self._parse_card(card)
            commander = result[0]
        if self._json_data["boards"]["companions"]["cards"]:
            card = next(iter(self._json_data["boards"]["companions"]["cards"].items()))[1]
            result = self._parse_card(card)
            companion = result[0]

        try:
            return Deck(mainboard, sideboard, commander, companion, metadata=self._metadata)
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            return None
