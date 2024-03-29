"""

    mtgcards.yt.parsers.aetherhub.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse AetherHub decklist page.

    @author: z33k

"""
from typing import List, Optional, Set

from bs4 import Tag

from mtgcards.scryfall import Deck, InvalidDeckError, find_by_name_narrowed_by_collector_number, \
    set_cards, Card
from mtgcards.yt.parsers import ParsingError, UrlParser


class AetherHubParser(UrlParser):
    """Parser of AetherHub decklist page.
    """
    def __init__(self, url: str, format_cards: Set[Card]) -> None:
        super().__init__(url, format_cards)
        self._soup = self._get_soup()
        self._deck = self._get_deck()

    def _get_deck(self) -> Optional[Deck]:
        mainboard, sideboard, commander = [], [], None

        tables = self._soup.find_all("table", class_="table table-borderless")
        if not tables:
            raise ParsingError(f"No 'table table-borderless' tables (that contain grouped card "
                               f"data) in the soup")

        hovers = []
        for table in tables:
            hovers.append([*table.find_all("div", "hover-imglink")])
        hovers = [h for h in hovers if h]
        hovers = sorted([h for h in hovers if h], key=lambda h: len(h), reverse=True)

        commander_tag = None
        if len(hovers[-1]) == 1:  # commander
            hovers, commander_tag = hovers[:-1], hovers[-1][0]

        if len(hovers) == 2:
            main_list_tags, sideboard_tags = hovers
        elif len(hovers) == 1:
            main_list_tags, sideboard_tags = hovers[0], []
        else:
            raise ParsingError(f"Unexpected number of 'hover-imglink' div tags "
                               f"(that contain card data): {len(hovers)}")

        for tag in main_list_tags:
            mainboard.extend(self._parse_hover_tag(tag))

        for tag in sideboard_tags:
            sideboard.extend(self._parse_hover_tag(tag))

        if commander_tag is not None:
            result = self._parse_hover_tag(commander_tag)
            if result:
                commander = result[0]

        try:
            return Deck(mainboard, sideboard, commander)
        except InvalidDeckError:
            return None

    def _parse_hover_tag(self, hover_tag: Tag) -> List[Card]:
        quantity, *_ = hover_tag.text.split()
        try:
            quantity = int(quantity)
        except ValueError:
            raise ParsingError(f"Can't parse card quantity from tag's text:"
                               f" {hover_tag.text.split()}")

        card_tag = hover_tag.find("a")
        if card_tag is None:
            raise ParsingError(f"No 'a' tag inside 'hover-imglink' div tag: {hover_tag!r}")

        name, set_code = card_tag.attrs["data-card-name"], card_tag.attrs["data-card-set"].lower()
        cards = set_cards(set_code)
        card = find_by_name_narrowed_by_collector_number(name, cards)
        if card:
            return [card] * quantity
        card = find_by_name_narrowed_by_collector_number(name, self._format_cards)
        return [card] * quantity if card else []
