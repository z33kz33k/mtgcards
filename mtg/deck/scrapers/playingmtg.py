"""

    mtg.deck.scrapers.playingmtg
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape PlayingMTG decklists.

    @author: mazz3rr

"""
import logging
from collections.abc import Iterator
from typing import override

from mtg.constants import Json
from mtg.deck.abc import DeckJsonParser
from mtg.deck.scrapers.abc import (
    DEFAULT_THROTTLING, DeckScraper, DecksJsonContainerScraper, HybridContainerScraper,
)
from mtg.lib.scrape.core import (
    ScrapingError, fetch_json, get_path_segments, is_more_than_root_path, normalize_url,
    prepend_url, strip_url_query,
)
from mtg.lib.scrape.dynamic import Xpath
from mtg.lib.time import date_from_unixtime, parse_date

_log = logging.getLogger(__name__)
URL_PREFIX = "https://playingmtg.com"
_THROTTLING = DEFAULT_THROTTLING * 2


class PlayingMtgDeckJsonParser(DeckJsonParser):
    """Parser of PlayingMTG decklist JSON data.
    """
    @override
    def _parse_input_for_metadata(self) -> None:
        if fmt := self._deck_json.get("format"):
            self._update_fmt(fmt)
        if dt := self._deck_json.get("date"):
            self._metadata["date"] = date_from_unixtime(int(dt), 1)
        if name := self._deck_json.get("humanname"):
            self._metadata["name"] = name
        if desc := self._deck_json.get("description"):
            self._metadata["description"] = desc
        if views := self._deck_json.get("views"):
            self._metadata["views"] = int(views)
        if author := self._deck_json.get("authornick"):
            self._metadata["author"] = author
        if archetype := self._deck_json.get("archetype_name"):
            self._update_archetype_or_theme(archetype)

    def _get_boards_iterator(self) -> Iterator[tuple[int, dict]]:
        boards = self._deck_json["boards"]
        if isinstance(boards, list):
            for i, item in enumerate(boards):
                yield i, item
        elif isinstance(boards, dict):
            for k, v in boards.items():
                yield int(k), v
        else:
            raise TypeError(f"Unexpected type for boards collection: '{type(boards)}'")

    @override
    def _parse_input_for_decklist(self) -> None:
        for board_code, cards_data in self._get_boards_iterator():
            board = self._sideboard if board_code == 1 else self._maindeck
            for set_num, qty in cards_data.items():
                set_code, colnum = set_num.split("-", maxsplit=1)
                card = self.find_card_by_collector_number(set_code, colnum)
                playset = self.get_playset(card, int(qty))
                if board_code == 2:
                    self._set_commander(card)
                else:
                    board += playset


def get_deck_json(slug: str) -> Json:
    api_url = f"https://api.dotgg.gg/cgfw/getdeck?game=magic&slug={slug}&mode=boards"
    return fetch_json(api_url)


@DeckScraper.registered
class PlayingMtgDeckScraper(DeckScraper):
    """Scraper of PlayingMTG decklist page.
    """
    JSON_FROM_API = True
    EXAMPLE_URLS = (
        "https://playingmtg.com/decks/frodo-sam-and-their-favourite-squirrel-s-copy-2/",
        "https://playingmtg.com/decks/reckless-raid-mtg-arena-starter-deck/",
        "https://playingmtg.com/decks/greasefang-parhelion-jqckl/",
    )

    @classmethod
    @override
    def is_valid_url(cls, url: str) -> bool:
        return is_more_than_root_path(url, "playingmtg.com", "decks")

    @classmethod
    @override
    def normalize_url(cls, url: str) -> str:
        url = normalize_url(url, case_sensitive=True)
        return strip_url_query(url)

    def _get_slug(self) -> str:
        _, slug, *_ = get_path_segments(self._url)
        return slug

    @override
    def _fetch_json(self) -> None:
        slug = self._get_slug()
        self._json = get_deck_json(slug)

    @override
    def _validate_json(self) -> None:
        super()._validate_json()
        if not self._json.get("boards"):
            raise ScrapingError("No cards data", scraper=type(self), url=self.url)

    @override
    def _get_sub_parser(self) -> PlayingMtgDeckJsonParser:
        return PlayingMtgDeckJsonParser(self._json, self._metadata)

    @override
    def _parse_input_for_metadata(self) -> None:
        pass

    @override
    def _parse_input_for_decklist(self) -> None:
        pass


@DecksJsonContainerScraper.registered
class PlayingMtgTournamentScraper(DecksJsonContainerScraper):
    """Scraper of PlayingMTG tournament page.
    """
    CONTAINER_NAME = "PlayingMTG tournament"  # override
    DECK_JSON_PARSER_TYPE = PlayingMtgDeckJsonParser  # override
    JSON_FROM_API = True  # override
    EXAMPLE_URLS = (
        "https://playingmtg.com/tournaments/mtgo-league-7602/",
    )

    @classmethod
    @override
    def is_valid_url(cls, url: str) -> bool:
        return is_more_than_root_path(url, "playingmtg.com", "tournaments")

    def _get_slug(self) -> str:
        _, slug, *_ = get_path_segments(self._url)
        return slug

    @override
    def _fetch_json(self) -> None:
        slug = self._get_slug()
        api_url = f"https://api.dotgg.gg/cgfw/gettournament?game=magic&slug={slug}"
        self._json = fetch_json(api_url)

    def _parse_input_for_metadata(self) -> None:
        self._metadata["event"] = {}
        if fmt := self._json.get("format"):
            self._update_fmt(fmt)
        if dt := self._json.get("date"):
            dt = date_from_unixtime(int(dt), 1)
            self._metadata["date"] = dt
            self._metadata["event"]["date"] = dt
        if name := self._json.get("name"):
            self._metadata["event"]["name"] = name
        if organizer := self._json.get("organizer_name"):
            self._metadata["event"]["organizer"] = organizer
        if players := self._json.get("players_count"):
            self._metadata["event"]["players"] = int(players)
        if winner := self._json.get("winner_name"):
            self._metadata["event"]["winner"] = winner
        if winner_country := self._json.get("winner_country"):
            self._metadata["event"]["winner_country"] = winner_country
        if not self._metadata["event"]:
            del self._metadata["event"]

    @override
    def _parse_input_for_decks_data(self) -> None:
        self._decks_json = [
            get_deck_json(slug) for data in self._json.get("standings", [])
            if (slug := data["slug"])
        ]


@HybridContainerScraper.registered
class PlayingMtgArticleScraper(HybridContainerScraper):
    """Scraper of PlayingMTG article page.
    """
    SELENIUM_PARAMS = {  # override
        "xpaths": [
            Xpath(
                text='//div[@class="RootOfEmbeddedDeck"]//a[contains(@href, "/decks/")]',
                wait_for_all=True,
            ),
        ],
    }
    THROTTLING = _THROTTLING  # override
    CONTAINER_NAME = "PlayingMTG article"  # override
    CONTAINER_SCRAPER_TYPES = PlayingMtgTournamentScraper,  # override
    CONTAINER_URL_PREFIX = URL_PREFIX  # override
    EXAMPLE_URLS = (
        "https://playingmtg.com/pro-tour-aetherdrift-top-8-standard-decklists/",
    )

    @classmethod
    @override
    def is_valid_url(cls, url: str) -> bool:
        tokens = (
            "decks", "tournaments", "wp-content", "news", "mtg-arena", "spoilers", "commander",
            "standard", "modern", "pioneer", "collection", "prices", "products", "schedule",
            "builder", "meta", "tier-list"
        )
        if any(f"playingmtg.com/{t}" in url.lower() for t in tokens):
            return False
        return is_more_than_root_path(url, "playingmtg.com")

    @override
    def _parse_input_for_metadata(self) -> None:
        self._metadata["article"] = {}
        if title_tag := self._soup.select_one("h1.page-title"):
            self._metadata["article"]["title"] = title_tag.text.strip()
        if author_tag := self._soup.find("a", {"rel": "author"}):
            self._metadata["article"]["author"] = author_tag.find("span").text.strip()
        if date_tag := self._soup.find("li", {"itemprop": "dateModified"}):
            date_text = date_tag.find("time")["datetime"]
            self._metadata["article"]["date"] = parse_date(date_text)
        if not self._metadata["article"]:
            del self._metadata["article"]

    @override
    def _parse_input_for_decks_data(self) -> None:
        deck_tags = [*self._soup.find_all("div", class_="RootOfEmbeddedDeck")]
        a_tags = [t.find("a", href=lambda h: h and "/decks/" in h) for t in deck_tags]
        deck_urls = [prepend_url(t["href"], URL_PREFIX) for t in a_tags if t]

        article_tag = self._soup.find("article")
        if not article_tag:
            err = ScrapingError("Article tag not found", scraper=type(self), url=self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            self._deck_urls = deck_urls
            return

        p_deck_urls, self._container_urls = self._find_links_in_tags(*article_tag.find_all("p"))
        self._deck_urls = deck_urls + [l for l in p_deck_urls if l not in deck_urls]
