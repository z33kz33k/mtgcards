"""

    mtgcards.yt.parsers.goldfish.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MtGGoldfish decklist page.

    @author: z33k

"""
from enum import Enum, auto
from typing import Optional, Set

from bs4 import Tag

from mtgcards.scryfall import Deck, InvalidDeckError, find_by_name_narrowed_by_collector_number, \
    set_cards, Card
from mtgcards.yt.parsers import ParsingError, UrlParser


class _ParsingState(Enum):
    """State machine for parsing.
    """
    IDLE = auto()
    COMMANDER = auto()
    MAINBOARD = auto()
    SIDEBOARD = auto()

    @classmethod
    def shift_to_commander(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state is not _ParsingState.IDLE:
            raise RuntimeError(f"Invalid transition to COMMANDER from: {current_state.name}")
        return _ParsingState.COMMANDER

    @classmethod
    def shift_to_mainlist(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state not in (_ParsingState.IDLE, _ParsingState.COMMANDER):
            raise RuntimeError(f"Invalid transition to MAINBOARD from: {current_state.name}")
        return _ParsingState.MAINBOARD

    @classmethod
    def shift_to_sideboard(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state is not _ParsingState.MAINBOARD:
            raise RuntimeError(f"Invalid transition to SIDEBOARD from: {current_state.name}")
        return _ParsingState.SIDEBOARD


class GoldfishParser(UrlParser):
    """Parser of MtGGoldfish decklist page.
    """
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/96.0.4664.113 Safari/537.36}",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                  "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
    }

    def __init__(self, url: str, format_cards: Set[Card]) -> None:
        super().__init__(url, format_cards)
        self._soup = self._get_soup(headers=self.HEADERS)
        self._state = _ParsingState.IDLE
        self._deck = self._get_deck()

    def _get_deck(self) -> Optional[Deck]:
        mainboard, sideboard, commander = [], [], None
        table = self._soup.find("table", class_="deck-view-deck-table")
        rows = table.find_all("tr")
        for row in rows:
            if row.has_attr("class") and "deck-category-header" in row.attrs["class"]:
                if row.text.strip() == "Commander":
                    self._state = _ParsingState.shift_to_commander(self._state)
                elif "Creatures" in row.text.strip():
                    self._state = _ParsingState.shift_to_mainlist(self._state)
                elif "Sideboard" in row.text.strip():
                    self._state = _ParsingState.shift_to_sideboard(self._state)
            else:
                cards = self._parse_row(row)
                if self._state is _ParsingState.COMMANDER:
                    if cards:
                        commander = cards[0]
                elif self._state is _ParsingState.MAINBOARD:
                    mainboard.extend(cards)
                elif self._state is _ParsingState.SIDEBOARD:
                    sideboard.extend(cards)

        try:
            return Deck(mainboard, sideboard, commander)
        except InvalidDeckError:
            return None

    def _parse_row(self, row: Tag):
        quantity_tag = row.find(class_="text-right")
        if not quantity_tag:
            raise ParsingError("Can't find quantity data in a row tag")
        quantity = quantity_tag.text.strip()
        try:
            quantity = int(quantity)
        except ValueError:
            raise ParsingError(f"Can't parse card quantity from tag's text:"
                               f" {quantity_tag.text!r}")

        a_tag = row.find("a")
        if not a_tag:
            raise ParsingError("Can't find name and set data a row tag")
        text = a_tag.attrs.get("data-card-id")
        if not text:
            raise ParsingError("Can't find name and set data a row tag")
        if "[" not in text or "]" not in text:
            raise ParsingError(f"No set data in: {text!r}")
        name, set_code = text.split("[")
        name = name.strip()
        if "<" in name:
            name, *rest = name.split("<")
            name = name.strip()

        set_code = set_code[:-1].lower()

        cards = set_cards(set_code)
        card = find_by_name_narrowed_by_collector_number(name, cards)
        if card:
            return [card] * quantity
        card = find_by_name_narrowed_by_collector_number(name, self._format_cards)
        return [card] * quantity if card else []

