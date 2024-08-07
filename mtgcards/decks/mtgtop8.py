"""

    mtgcards.decks.mtgtop8.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MTGTop8 decklist page.

    @author: z33k

"""
import logging
from datetime import datetime

from mtgcards.const import Json
from mtgcards.decks import Deck, DeckScraper, InvalidDeck, find_card_by_name
from mtgcards.utils import extract_int
from mtgcards.utils.scrape import getsoup

_log = logging.getLogger(__name__)


EVENT_RANKS = "minor", "regular", "major"  # indicated by number of stars (1, 2, 3)


# TODO: scrape event as an object (basically a list of decks with event metadata taken from the
#  first), scrape metagame
class MtgTop8Scraper(DeckScraper):
    """Scraper of MTGTop8 decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(url)
        self._scrape_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgtop8.com/event?e=" in url and "&d=" in url

    def _scrape_metadata(self) -> None:  # override
        event_tag, _, name_tag, *_ = self._soup.find_all("div", class_="event_title")
        self._metadata["event"] = {}
        self._metadata["event"]["name"] = event_tag.text.strip().removesuffix(" Event")
        place, name = name_tag.text.strip().split(maxsplit=1)
        self._metadata["event"]["place"] = place
        if "-" in name:
            name, author = name.split("-", maxsplit=1)
            self._metadata["name"] = name.strip()
            self._metadata["author"] = author.strip()
        else:
            self._metadata["name"] = name.strip()
        fmt_tag = self._soup.find("div", class_="meta_arch")
        self._update_fmt(fmt_tag.text.strip().lower())
        try:
            self._metadata["event"]["rank"] = EVENT_RANKS[len(fmt_tag.find_all("img")) - 1]
        except IndexError:
            pass
        players_date_text = self._soup.find('div', style='margin-bottom:5px;').text.strip()
        if "-" in players_date_text:
            players_text, date_text = players_date_text.split("-", maxsplit=1)
            self._metadata["event"]["players"] = extract_int(players_text)
        else:
            date_text = players_date_text
        self._metadata["event"]["date"] = datetime.strptime(date_text.strip(), '%d/%m/%y').date()
        source_tag = self._soup.find("a", target="_blank")
        self._metadata["event"]["source"] = source_tag.text.strip()

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander = [], [], None
        deck_tag = self._soup.find("div", style="display:flex;align-content:stretch;")
        cards, commander_on = mainboard, False
        for block_tag in deck_tag:
            for sub_tag in block_tag:
                if sub_tag.name == "div" and sub_tag.attrs.get("class") == ['O14']:
                    if sub_tag.text == "SIDEBOARD":
                        cards = sideboard
                        commander_on = False
                    elif sub_tag.text == "COMMANDER":
                        commander_on = True
                    else:
                        commander_on = False
                if "deck_line" in sub_tag.attrs["class"]:
                    quantity, name = sub_tag.text.split(maxsplit=1)
                    card = find_card_by_name(name.strip(), fmt=self.fmt)
                    if commander_on:
                        commander = card
                    else:
                        quantity = extract_int(quantity)
                        cards += [card] * quantity

        try:
            return Deck(mainboard, sideboard, commander, metadata=self._metadata)
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            return None
