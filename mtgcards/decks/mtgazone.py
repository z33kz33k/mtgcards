"""

    mtgcards.decks.mtgazone.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MTG Arena Zone decklist page.

    @author: z33k

"""
import logging
from datetime import datetime

from bs4 import Tag

from mtgcards.const import Json
from mtgcards.decks import Deck, DeckScraper, InvalidDeck, Mode, get_playset
from mtgcards.scryfall import Card, all_formats, arena_formats
from mtgcards.utils import extract_int, from_iterable, timed
from mtgcards.utils.scrape import ScrapingError, getsoup


_log = logging.getLogger(__name__)


# alternative approach would be to scrape:
# self._soup.find("input", {"type": "hidden", "name": "c"}).attrs["value"].split("||")
# but it has a downside of not having clear sideboard-mainboard separation
class MtgazoneScraper(DeckScraper):
    """Scraper of MTG Arena Zone decklist page.

    This scraper can be used both to scrape individual MTGAZone deck pages and to scrape
    decklist blocks that are aggregated on thematic (e.g. meta, post-rotation, guide) sites. In
    the latter case a deck block Tag object should be provided - a URL is not needed so an empty
    string should be passed instead.
    """
    def __init__(self, url: str, metadata: Json | None = None, deck_tag: Tag | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_tag = deck_tag
        self._soup = deck_tag or getsoup(url)
        self._scrape_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgazone.com/user-decks/" in url or "mtgazone.com/deck/" in url

    def _scrape_metadata(self) -> None:  # override
        name_author_tag = self._soup.find("div", class_="name-container")
        name_tag = name_author_tag.find("div", class_="name")
        name, author, event = name_tag.text.strip(), None, None
        if " by " in name:
            name, author = name.split(" by ")
        elif " – " in name:
            name, event = name.split(" – ")
        self._metadata["name"] = name
        if not self.author:
            if not author:
                author_tag = name_author_tag.find("div", class_="by")
                author = author_tag.text.strip().removeprefix("by ")
            self._metadata["author"] = author
        if event:
            self._metadata["event"] = event
        fmt_tag = self._soup.find("div", class_="format")
        fmt = fmt_tag.text.strip().lower()
        self._update_fmt(fmt)
        if time_tag := self._soup.find("time", class_="ct-meta-element-date"):
            self._metadata["date"] = datetime.fromisoformat(time_tag.attrs["datetime"]).date()

    def _to_playset(self, card_tag) -> list[Card]:
        quantity = int(card_tag.attrs["data-quantity"])
        a_tag = card_tag.find("a")
        name = a_tag.text.strip()
        *_, scryfall_id = a_tag.attrs["data-cimg"].split("/")
        scryfall_id, *_ = scryfall_id.split(".jpg")
        if playset := self._get_playset_by_id(scryfall_id, quantity):
            return playset
        return get_playset(name, quantity, fmt=self.fmt)

    def _process_decklist(self, decklist_tag: Tag) -> list[Card]:
        decklist = []
        card_tags = decklist_tag.find_all("div", class_="card")
        for card_tag in card_tags:
            decklist.extend(self._to_playset(card_tag))
        return decklist

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander, companion = [], [], None, None

        if commander_tag := self._soup.select_one("div.decklist.short.commander"):
            commander = self._process_decklist(commander_tag)[0]

        if companion_tag := self._soup.select_one("div.decklist.short.companion"):
            companion = self._process_decklist(companion_tag)[0]

        main_tag = self._soup.select_one("div.decklist.main")
        mainboard = self._process_decklist(main_tag)

        if sideboard_tags := self._soup.select("div.decklist.sideboard"):
            sideboard_tag = sideboard_tags[1]
            sideboard = self._process_decklist(sideboard_tag)

        try:
            return Deck(mainboard, sideboard, commander, companion, self._metadata)
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            return None


def _parse_tiers(table: Tag) -> dict[str, int]:
    tiers = {}
    for row in table.find_all("tr"):
        tier_col, deck_col = row.find_all("td")
        tier = extract_int(tier_col.find("strong").text)
        deck = deck_col.find("a").text.strip()
        tiers[deck] = tier
    return tiers


def _parse_deck(deck_tag: Tag, decks2tiers: dict[str, int], deck_place: int) -> Deck:
    try:
        deck = MtgazoneScraper("", deck_tag=deck_tag).deck
    except InvalidDeck as err:
        raise ScrapingError(f"Scraping meta deck failed with: {err}")
    meta = {
        "meta": {
            "place": deck_place
        }
    }
    tier = decks2tiers.get(deck.name)
    if tier is None:
        deck_name = from_iterable(decks2tiers, lambda d: deck.name in d)
        if deck_name:
            tier = decks2tiers[deck_name]
    if tier:
        meta["meta"]["tier"] = tier
    deck.update_metadata(meta=meta["meta"])
    return deck


@timed("scraping meta decks")
def scrape_meta(fmt="standard", bo3=True) -> list[Deck]:
    formats = {fmt for fmt in arena_formats() if fmt not in {"brawl", "standardbrawl"}}
    formats = sorted({*formats, "pioneer"})
    fmt = fmt.lower()
    if fmt not in formats:
        raise ValueError(f"Invalid format: {fmt!r}. Can be only one of: {formats}")

    mode = "-bo3" if bo3 else "-bo1"
    if fmt == "pioneer":
        mode = ""
    url = f"https://mtgazone.com/{fmt}{mode}-metagame-tier-list/"

    soup = getsoup(url)
    time_tag = soup.find("time", class_="ct-meta-element-date")
    deck_date = datetime.fromisoformat(time_tag.attrs["datetime"]).date()
    tier_table = soup.find("figure", class_="wp-block-table")
    table_body = tier_table.find("tbody")
    decks2tiers = _parse_tiers(table_body)

    decks = []
    for i, deck_tag in enumerate(soup.find_all("div", class_="deck-block"), start=1):
        deck = _parse_deck(deck_tag, decks2tiers, i)
        deck.update_metadata(date=deck_date)
        deck.update_metadata(mode=mode[1:].title() if mode else Mode.BO3.value)
        decks.append(deck)

    return decks


