"""

    mtgcards.yt.py
    ~~~~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
import itertools
import re
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import Type

import backoff
import gspread
import pytube
import pytube.exceptions
import requests
import scrapetube
from contexttimer import Timer
from youtubesearchpython import Channel as YtspChannel

from mtgcards.decks import Deck, UrlParser
from mtgcards.decks.aetherhub import AetherHubParser
from mtgcards.decks.arena import ArenaParser
from mtgcards.decks.goldfish import GoldfishParser
from mtgcards.decks.moxfield import MoxfieldParser
from mtgcards.decks.mtgazone import MtgaZoneParser
from mtgcards.decks.streamdecker import StreamdeckerParser
from mtgcards.decks.tcgplayer import TcgPlayerParser
from mtgcards.decks.untapped import UntappedParser
from mtgcards.scryfall import format_cards
from mtgcards.scryfall import formats as scryfall_formats
from mtgcards.utils import getrepr


def channels() -> dict[str, str]:
    """Retrieve a channel addresses mapping from a private Google Sheet spreadsheet.

    Mind that this operation takes about 2 seconds to complete.

    Returns:
        a dictionary of channel names mapped to their addresses
    """
    creds_file = "scraping_service_account.json"
    client = gspread.service_account(filename=creds_file)
    spreadsheet = client.open("mtga_yt")
    worksheet = spreadsheet.worksheet("channels")
    names = worksheet.col_values(1, value_render_option="UNFORMATTED_VALUE")[1:]
    addresses = worksheet.col_values(3, value_render_option="UNFORMATTED_VALUE")[1:]
    return dict((name, address) for name, address in zip(names, addresses))


class Video:
    """YouTube video showcasing a MtG deck with its most important metadata.
    """
    URL_TEMPLATE = "https://www.youtube.com/watch?v={}"

    # decklist hooks
    AETHERHUB_HOOK = "aetherhub.com/Deck/"
    GOLDFISH_HOOK = "mtggoldfish.com/deck/"
    MOXFIELD_HOOK = "moxfield.com/decks/"
    MTGAZONE_HOOK = "mtgazone.com/user-decks/"
    STREAMDECKER_HOOK = "streamdecker.com/deck/"
    TCGPLAYER_HOOK = "decks.tcgplayer.com/"
    UNTAPPED_HOOKS = {"mtga.untapped.gg", "/deck/"}

    SHORTENER_HOOKS = {"bit.ly/", "tinyurl.com/", "cutt.ly/", "rb.gy/", "shortcm.li/", "tiny.cc/",
                       "snip.ly/", "qti.ai/", "dub.sh/", "lyksoomu.com/", "zws.im/", "t.ly/"}

    formats = scryfall_formats()

    @property
    def id(self) -> str:
        return self._id

    @property
    def author(self) -> str:
        return self._author

    @property
    def description(self) -> str:
        return self._description

    @property
    def keywords(self) -> list[str]:
        return self._keywords

    @property
    def publish_date(self) -> datetime:
        return self._publish_date

    @property
    def title(self) -> str:
        return self._title

    @property
    def views(self) -> int:
        return self._views

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @cached_property
    def _desc_lines(self) -> list[str]:
        return [line.strip() for line in self.description.split("\n")] if self.description else []

    @property
    def links(self) -> list[str]:
        return self._links

    @property
    def shortened_links(self) -> set[str]:
        return {link for link in self.links if any(hook in link for hook in self.SHORTENER_HOOKS)}

    @property
    def format(self) -> str:
        return self._format

    @property
    def deck(self) -> Deck | None:
        return self._deck

    def __init__(self, video_id: str) -> None:
        """Initialize.

        Args:
            video_id: unique string identifying a YouTube video (the part after `v=` in the URL)
        """
        self._id = video_id
        self._pytube = self._get_pytube()
        self._author, self._description, self._title = None, None, None
        self._keywords, self._publish_date, self._views = None, None, None
        self._get_pytube_data()
        self._format_soup: defaultdict[str, list[str]] = defaultdict(list)
        self._extract_formats(self.title)
        self._links, self._arena_lines = self._parse_lines()
        self._format = self._get_format()
        self._format_cards = format_cards(self._format)
        self._deck = self._get_deck()

    def __repr__(self) -> str:
        return getrepr(self.__class__, ("title", self.title), ("deck", self.deck))

    def _get_pytube(self) -> pytube.YouTube:
        return pytube.YouTube(self.URL_TEMPLATE.format(self.id))

    def _get_pytube_data(self) -> None:
        self._author = self._get_author()
        self._description = self._get_description()
        self._title = self._get_title()
        self._keywords = self._get_keywords()
        self._publish_date = self._get_publish_date()
        self._views = self._get_views()
        self._channel_id = self._get_channel_id()

    def _get_author(self) -> str:
        try:
            author = self._pytube.author
        except pytube.exceptions.PytubeError:
            print("Problems with retrieving video author. Retrying with backoff (60 seconds "
                  "max)...")
            author = self._get_author_with_backoff()
        return author

    def _get_description(self) -> str:
        try:
            description = self._pytube.description
            if description is None:
                raise ValueError
        except (pytube.exceptions.PytubeError, ValueError):
            print("Problems with retrieving video description. Retrying with backoff (60 seconds "
                  "max)...")
            description = self._get_description_with_backoff()
        return description

    def _get_title(self) -> str:
        try:
            title = self._pytube.title
        except pytube.exceptions.PytubeError:
            print("Problems with retrieving video title. Retrying with backoff (60 seconds max)...")
            title = self._get_title_with_backoff()
        return title

    def _get_keywords(self) -> list[str]:
        try:
            keywords = self._pytube.keywords
        except pytube.exceptions.PytubeError:
            print("Problems with retrieving video keywords. Retrying with backoff (60 seconds "
                  "max)...")
            keywords = self._get_keywords_with_backoff()
        return keywords

    def _get_publish_date(self) -> datetime:
        try:
            publish_date = self._pytube.publish_date
        except pytube.exceptions.PytubeError:
            print("Problems with retrieving video publish date. Retrying with backoff (60 seconds "
                  "max)...")
            publish_date = self._get_publish_date_with_backoff()
        return publish_date

    def _get_views(self) -> int:
        try:
            views = self._pytube.views
        except pytube.exceptions.PytubeError:
            print("Problems with retrieving video views. Retrying with backoff (60 seconds max)...")
            views = self._get_views_with_backoff()
        return views

    def _get_channel_id(self) -> str:
        try:
            channel_id = self._pytube.channel_id
        except pytube.exceptions.PytubeError:
            print("Problems with retrieving video channel ID. Retrying with backoff (60 seconds "
                  "max)...")
            channel_id = self._get_channel_id_with_backoff()
        return channel_id

    @backoff.on_exception(backoff.expo, (pytube.exceptions.PytubeError, ValueError), max_time=60)
    def _get_author_with_backoff(self) -> str:
        self._pytube = self._get_pytube()
        author = self._pytube.author
        if author == 'unknown':
            raise ValueError
        return self._pytube.author

    @backoff.on_exception(backoff.expo, (pytube.exceptions.PytubeError, ValueError), max_time=60)
    def _get_description_with_backoff(self) -> str:
        self._pytube = self._get_pytube()
        desc = self._pytube.description
        if not desc:
            raise ValueError
        return self._pytube.description

    @backoff.on_exception(backoff.expo, pytube.exceptions.PytubeError, max_time=60)
    def _get_title_with_backoff(self) -> str:
        self._pytube = self._get_pytube()
        return self._pytube.title

    @backoff.on_exception(backoff.expo, pytube.exceptions.PytubeError, max_time=60)
    def _get_keywords_with_backoff(self) -> list[str]:
        self._pytube = self._get_pytube()
        return self._pytube.keywords

    @backoff.on_exception(backoff.expo, pytube.exceptions.PytubeError, max_time=60)
    def _get_publish_date_with_backoff(self) -> datetime:
        self._pytube = self._get_pytube()
        return self._pytube.publish_date

    @backoff.on_exception(backoff.expo, pytube.exceptions.PytubeError, max_time=60)
    def _get_views_with_backoff(self) -> int:
        self._pytube = self._get_pytube()
        return self._pytube.views

    @backoff.on_exception(backoff.expo, pytube.exceptions.PytubeError, max_time=60)
    def _get_channel_id_with_backoff(self) -> str:
        self._pytube = self._get_pytube()
        return self._pytube.channel_id

    def _extract_formats(self, line: str) -> None:
        words = [word.lower() for word in line.strip().split()]
        formats = [fmt for fmt in self.formats if any(fmt in word for word in words)]
        for fmt in formats:
            self._format_soup[fmt].append(fmt)

    def _get_format(self) -> str:
        # if format soup has been populated, take the most common item
        if self._format_soup:
            two_best = Counter(itertools.chain(*self._format_soup.values())).most_common(2)
            two_best = [pair[0] for pair in two_best]
            if len(two_best) == 2 and all(fmt in ("brawl", "historic") for fmt in two_best):
                return "historicbrawl"
            return two_best[0]
        # if not, fall back to default
        return "standard"

    def _parse_lines(self) -> tuple[list[str], list[str]]:
        links, arena_lines = [], []
        for line in self._desc_lines:
            self._extract_formats(line)
            url = extract_url(line)
            if url:
                links.append(url)
            else:
                if ArenaParser.is_arena_line(line):
                    arena_lines.append(line)
        return links, arena_lines

    @classmethod
    def _process_hooks(cls, links: list[str]) -> dict[Type[UrlParser], str]:
        parsers_map = {}
        for link in links:
            if not parsers_map.get(AetherHubParser) and cls.AETHERHUB_HOOK in link:
                parsers_map[AetherHubParser] = link
            elif not parsers_map.get(GoldfishParser) and cls.GOLDFISH_HOOK in link:
                parsers_map[GoldfishParser] = link
            elif not parsers_map.get(MoxfieldParser) and cls.MOXFIELD_HOOK in link:
                parsers_map[MoxfieldParser] = link
            elif not parsers_map.get(MtgaZoneParser) and cls.MTGAZONE_HOOK in link:
                parsers_map[MtgaZoneParser] = link
            elif not parsers_map.get(StreamdeckerParser) and cls.STREAMDECKER_HOOK in link:
                parsers_map[StreamdeckerParser] = link
            elif not parsers_map.get(TcgPlayerParser) and cls.TCGPLAYER_HOOK in link:
                parsers_map[TcgPlayerParser] = link
            elif (not parsers_map.get(UntappedParser)
                  and all(hook in link for hook in cls.UNTAPPED_HOOKS)):
                parsers_map[UntappedParser] = link
        return parsers_map

    def _process_urls(self, urls: list[str]) -> Deck | None:
        parsers_map = self._process_hooks(urls)
        for parser_type, url in parsers_map.items():
            deck = parser_type(url, self._format_cards).deck
            if deck:
                return deck
        return None

    def _get_deck(self) -> Deck | None:
        # 1st stage: Arena lines
        if self._arena_lines:
            deck = ArenaParser(self._arena_lines, self._format_cards).deck
            if deck:
                return deck
        # 2nd stage: regular URLs
        deck = self._process_urls(self.links)
        if deck:
            return deck
        # 3rd stage: shortened URLs
        shortened_urls = [link for link in self.links
                          if any(hook in link for hook in self.SHORTENER_HOOKS)]
        unshortened_urls = [unshorten(url) for url in shortened_urls]
        return self._process_urls(unshortened_urls)


class Channel(list):
    """A list of videos showcasing a MtG deck with its most important metadata.
    """
    @property
    def url(self) -> str:
        return self._url

    @property
    def id(self) -> str | None:
        return self._id

    @property
    def title(self) -> str | None:
        return self._title

    @property
    def tags(self) -> list[str] | None:
        return self._tags

    @property
    def subscribers(self) -> int | None:
        return self._subscribers

    def __init__(self, url: str, limit=10) -> None:
        try:
            videos = [*scrapetube.get_channel(channel_url=url, limit=limit)]
        except OSError:
            raise ValueError(f"Invalid URL: {url!r}")
        super().__init__([Video(data["videoId"]) for data in videos])
        self._url = url
        self._id = self[0].channel_id if self else None
        self._ytsp_data = YtspChannel(self.id) if self._id else None
        self._title = self._ytsp_data.result["title"] if self._id else None
        self._tags = self._ytsp_data.result["tags"] if self._id else None
        self._subscribers = self._parse_subscribers() if self._id else None

    def _parse_subscribers(self) -> int:
        text = self._ytsp_data.result["subscribers"]["simpleText"]
        number = text.rstrip(" subscribers").rstrip("KM")
        subscribers = Decimal(number)
        if "K" in text:
            subscribers *= 1000
        elif "M" in text:
            subscribers *= 1_000_000
        return int(subscribers)


def unshorten(url: str) -> str:
    """Unshorten URL shortened by services like bit.ly, tinyurl.com etc.

    Pilfered from: https://stackoverflow.com/a/28918160/4465708
    """
    print(f"Unshortening: '{url}'...")
    with Timer() as t:
        session = requests.Session()  # so connections are recycled
        resp = session.head(url, allow_redirects=True)
    print(f"Request completed in {t.elapsed:.3f} seconds.")
    return resp.url


def extract_url(text: str, https=True) -> str | None:
    """Extract (the first occurrence of) URL from ``text``.

    Pilfered from: https://stackoverflow.com/a/840110/4465708
    """
    pattern = r"(?P<url>https?://[^\s'\"]+)" if https else r"(?P<url>http?://[^\s'\"]+)"
    match = re.search(pattern, text)
    return match.group("url") if match else None
