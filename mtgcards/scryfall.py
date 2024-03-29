"""

    mtgcards.scryfall.py
    ~~~~~~~~~~~~~~~~~~~
    Handle Scryfall data.

    @author: z33k

"""
import json
import re

from collections import defaultdict, namedtuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import lru_cache, cached_property
from pprint import pprint
from typing import Callable, DefaultDict, Dict, Iterable, List, Optional, Set, Tuple
import itertools
import math

import scrython

from mtgcards.utils import from_iterable, getrepr, parse_int_from_str
from mtgcards.utils.files import download_file, getdir
from mtgcards.const import DATADIR, Json
from mtgcards.mtgwiki import RACES, CLASSES

FILENAME = "scryfall.json"


class ScryfallError(ValueError):
    """Raised on invalid Scryfall data.
    """


def download_scryfall_bulk_data() -> None:
    """Download Scryfall 'Oracle Cards' bulk data JSON.
    """
    bd = scrython.BulkData()
    data = bd.data()[0]  # retrieve 'Oracle Cards' data dict
    url = data["download_uri"]
    download_file(url, file_name=FILENAME, dst_dir=DATADIR)


MULTIPART_SEPARATOR = "//"  # separates parts of card's name in multipart cards
MULTIPART_LAYOUTS = ['adventure', 'art_series', 'double_faced_token', 'flip', 'modal_dfc', 'split',
                     'transform']

# all cards that got Alchemy rebalance treatment have their rebalanced counterparts with names
# prefixed by 'A-'
ALCHEMY_REBALANCE_INDICATOR = "A-"


class Color(Enum):
    COLORLESS = ()  # technically, not a color
    # singletons
    WHITE = ("W",)
    BLUE = ("U",)
    BLACK = ("B",)
    RED = ("R",)
    GREEN = ("G",)
    # pairs
    GOLGARI = ("B", "G")
    RAKDOS = ("B", "R")
    DIMIR = ("B", "U")
    ORZHOV = ("B", "W")
    GRUUL = ("G", "R")
    SIMIC = ("G", "U")
    SELESNYA = ("G", "W")
    IZZET = ("R", "U")
    BOROS = ("R", "W")
    AZORIUS = ("U", "W")
    # triples
    JUND = ("B", "G", "R")
    SULTAI = ("B", "G", "U")
    ABZAN = ("B", "G", "W")
    GRIXIS = ("B", "R", "U")
    MARDU = ("B", "R", "W")
    ESPER = ("B", "U", "W")
    TEMUR = ("G", "R", "U")
    NAYA = ("G", "R", "W")
    BANT = ("G", "U", "W")
    JESKAI = ("R", "U", "W")
    # quadruples
    CHAOS = ("B", "G", "R", "U")
    AGGRESSION = ("B", "G", "R", "W")
    GROWTH = ("B", "G", "U", "W")
    ARTIFICE = ("B", "R", "U", "W")
    ALTRUISM = ("G", "R", "U", "W")
    # other
    ALL = ("B", "G", "R", "U", "W")

    @property
    def is_multi(self) -> bool:
        return len(self.value) > 1

    @staticmethod
    def from_letters(letters: Iterable[str]) -> "Color":
        letters = [*letters]
        if (any(letter not in Color.ALL.value for letter in letters)
                or any(letters.count(letter) > 1 for letter in letters)):
            raise ValueError(f"Invalid color letter designations: {letters}")
        relevant_colors = [color for color in Color if len(color.value) == len(letters)]
        if not relevant_colors:
            raise ValueError(f"Invalid number of color letter designation. Must be 1-5, "
                             f"got {len(letters)}")
        result = from_iterable(relevant_colors,
                               lambda color: all(letter in color.value for letter in letters))
        if not result:
            raise ValueError(f"No color for designations: {letters}")
        return result

    @staticmethod
    def from_cards(cards: Iterable["Card"]) -> "Color":
        letters = set()
        for card in cards:
            letters.update(card.color_identity.value)
        return Color.from_letters(letters)


class Rarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    MYTHIC = "mythic"
    SPECIAL = "special"
    BONUS = "bonus"

    @property
    def weight(self) -> Optional[float]:
        """Return fractional weight of this rarity based on frequency of occurence in boosters.

        Based on: https://mtg.fandom.com/wiki/Rarity
        """
        if self is Rarity.MYTHIC:
            return 1 / (1 / 15 * 1 / 8)  # 120.00
        if self is Rarity.RARE:
            return 1 / (1 / 15 * 7 / 8)  # 17.14
        if self is Rarity.UNCOMMON:
            return 1 / (1 / 15 * 3)  # 5.00
        if self is Rarity.COMMON:
            return 1 / (1 / 15 * 11)  # 1.36
        return None

    @property
    def is_special(self) -> bool:
        return self is Rarity.SPECIAL or self is Rarity.BONUS


class TypeLine:
    """Parser of type line in Scryfall data.
    """
    SEPARATOR = "—"

    # according to MtG Wiki (not updated since BRO)
    SUPERTYPES = {"Basic", "Elite", "Host", "Legendary", "Ongoing", "Snow", "Token", "Tribal",
                  "World"}
    PERMAMENT_TYPES = {"Artifact", "Battle", "Creature", "Enchantment", "Land", "Planeswalker"}
    NONPERMAMENT_TYPES = {"Sorcery", "Instant"}

    @property
    def text(self) -> str:
        return self._text

    @property
    def supertypes(self) -> List[str]:
        return [t for t in self._types if t in self.SUPERTYPES]

    @property
    def regular_types(self) -> List[str]:
        return [t for t in self._types if t not in self.SUPERTYPES]

    @property
    def subtypes(self) -> List[str]:
        return self._subtypes

    @property
    def is_permanent(self) -> bool:
        return all(p in self.PERMAMENT_TYPES for p in self.regular_types)

    @property
    def is_nonpermanent(self) -> bool:
        # type not being permanent doesn't mean it's 'non-permanent', e.g. 'dungeon' is neither
        return all(p in self.NONPERMAMENT_TYPES for p in self.regular_types)

    @property
    def is_artifact(self) -> bool:
        return "Artifact" in self.regular_types

    @property
    def is_creature(self) -> bool:
        return "Creature" in self.regular_types

    @property
    def is_enchantment(self) -> bool:
        return "Enchantment" in self.regular_types

    @property
    def is_instant(self) -> bool:
        return "Instant" in self.regular_types

    @property
    def is_land(self) -> bool:
        return "Land" in self.regular_types

    @property
    def is_planeswalker(self) -> bool:
        return "Planeswalker" in self.regular_types

    @property
    def is_sorcery(self) -> bool:
        return "Sorcery" in self.regular_types

    @property
    def races(self) -> List[str]:
        return [t for t in self.subtypes if t in RACES]

    @property
    def classes(self) -> List[str]:
        return [t for t in self.subtypes if t in CLASSES]

    def __init__(self, text: str) -> None:
        if MULTIPART_SEPARATOR in text:
            raise ValueError("Multipart type line")
        self._text = text
        self._types, self._subtypes = self._parse()

    def _parse(self) -> Tuple[List[str], List[str]]:
        """Parse text into types and subtypes.
        """
        if self.SEPARATOR in self.text:
            types, subtypes = self.text.split(f" {self.SEPARATOR} ", maxsplit=1)
            return types.split(), subtypes.split()
        return self.text.split(), []


class LordSentence:
    """Parser of 'lord'-effect related part of card's Oracle text.

    More on lords:  https://mtg.fandom.com/wiki/Lord

    A proper input should be a single isolated sentence (stripped of the trailing dot) from the
    whole bulk of any given card's Oracle text, e.g. for 'Leaf-Crowned Visionary' the relevant
    part is:

        'Other Elves you control get +1/+1'

    """
    PATTERN = re.compile(r".*(\bget\s\+[\dX]/\+[\dX]\b).*")

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def buff(self) -> str:
        return self._buff

    @property
    def suffix(self) -> str:
        return self._suffix

    @property
    def is_valid(self) -> bool:
        return bool(self.buff)

    def __init__(self, text: str) -> None:
        self._text = text
        self._prefix, self._buff, self._suffix = self._parse()

    def _parse(self) -> Tuple[str, str, str]:
        match = self.PATTERN.match(self._text)
        if match:
            prefix, suffix = self._text.split(match.group(1), maxsplit=1)
            return prefix.strip(), match.group(1), suffix.strip()
        return "", "", ""


# TODO: make Card inherit from CardFace
@dataclass(frozen=True)
class CardFace:
    """Thin wrapper on card face data that lives inside Scryfall card data.

    Somewhat similar to regular card but much simpler.
    """
    json: Json

    def __eq__(self, other: "Card") -> bool:
        left = self.name, self.mana_cost, self.type_line, self.oracle_text
        right = other.name, other.mana_cost, other.type_line, other.oracle_text
        return left == right

    def __hash__(self) -> int:
        return hash((self.name, self.mana_cost, self.type_line, self.oracle_text))

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return self.json["name"]

    @property
    def name_parts(self) -> Set[str]:
        return {*self.name.split()}

    @property
    def mana_cost(self) -> str:
        return self.json["mana_cost"]

    @property
    def type_line(self) -> Optional[str]:
        return self.json.get("type_line")

    @property
    def oracle_text(self) -> str:
        return self.json["oracle_text"]

    @property
    def colors(self) -> List[str]:
        result = self.json.get("colors")
        return result if result else []

    @lru_cache
    def parse_types(self) -> Optional[TypeLine]:
        return TypeLine(self.type_line) if self.type_line else None

    @property
    def supertypes(self) -> List[str]:
        return self.parse_types().supertypes if self.parse_types() else []

    @property
    def regular_types(self) -> List[str]:
        return self.parse_types().regular_types if self.parse_types() else []

    @property
    def subtypes(self) -> List[str]:
        return self.parse_types().subtypes if self.parse_types() else []

    @property
    def races(self) -> List[str]:
        return self.parse_types().races if self.parse_types() else []

    @property
    def classes(self) -> List[str]:
        return self.parse_types().classes if self.parse_types() else []

    @cached_property
    def lord_sentences(self) -> List[LordSentence]:
        return Card.parse_lord_sentences(self.oracle_text)

    @property
    def loyalty(self) -> Optional[str]:
        return self.json.get("loyalty")

    @property
    def loyalty_int(self) -> Optional[int]:
        return parse_int_from_str(self.loyalty) if self.loyalty is not None else None

    @property
    def has_special_loyalty(self) -> bool:
        return self.loyalty is not None and self.loyalty_int is None

    @property
    def power(self) -> Optional[int]:
        return self.json.get("power")

    @property
    def power_int(self) -> Optional[int]:
        return parse_int_from_str(self.power) if self.power is not None else None

    @property
    def has_special_power(self) -> bool:
        return self.power is not None and self.power_int is None

    @property
    def toughness(self) -> Optional[str]:
        return self.json.get("toughness")

    @property
    def toughness_int(self) -> Optional[int]:
        return parse_int_from_str(self.toughness) if self.toughness is not None else None

    @property
    def has_special_toughness(self) -> bool:
        return self.toughness is not None and self.toughness_int is None


@dataclass(frozen=True)
class Card:
    """Thin wrapper on Scryfall JSON data for an MtG card.

    Provides convenience access to the most important data pieces.
    """
    json: Json

    def __eq__(self, other: "Card") -> bool:
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __str__(self) -> str:
        text = f"{self.name} ({self.set.upper()})"
        if self.collector_number:
            text += f" {self.collector_number}"
        return text

    def __repr__(self) -> str:
        return getrepr(self.__class__, ("name", self.name), ("set", self.set),
                       ("collector_number", self.collector_number))

    def __post_init__(self) -> None:
        if self.is_multipart and self.card_faces is None:
            raise ScryfallError(f"Card faces data missing for multipart card {self.name!r}")
        if self.is_multipart and self.layout not in MULTIPART_LAYOUTS:
            raise ScryfallError(f"Invalid layout {self.layout!r} for multipart card {self.name!r}")

    @property
    def card_faces(self) -> List[CardFace]:
        data = self.json.get("card_faces")
        if data is None:
            return []
        return [CardFace(item) for item in data]

    @property
    def cmc(self) -> int:
        return math.ceil(self.json["cmc"])

    @property
    def color_identity(self) -> Color:
        # 'color_identity' is a wider term than 'colors' (that only take mana cost into account)
        # more on this here: https://mtg.fandom.com/wiki/Color_identity
        return Color(tuple(self.json["color_identity"]))

    @property
    def colors(self) -> List[str]:
        result = self.json.get("colors")
        return result if result else []

    @property
    def collector_number(self) -> str:
        return self.json["collector_number"]

    @property
    def collector_number_int(self) -> Optional[int]:
        """Return collector number as an integer, if it can be parsed as such.

        .. note: Parsing logic strips any non-digits and then parses a number. This means that
        some alternative versions (e.g. Alchemy variants) will have the same number. However,
        it needs to be this way, because there are some basic cards that still have the collector
        number in this format (for instance both parts of Meld pairs from BRO).

        `collector_number` can look like that:
            {"12e", "67f", "233f", "A-268", "4e"}
        """
        cn = "".join(char for char in self.collector_number if char.isdigit())
        return parse_int_from_str(cn)

    @property
    def formats(self) -> List[str]:
        """Return list of all Scryfall string format designations (e.g. `bro` for The Brothers'
        War).
        """
        return sorted(fmt for fmt in self.legalities)

    @property
    def games(self) -> List[str]:
        return self.json["games"]

    @property
    def id(self) -> str:
        return self.json["id"]

    @property
    def keywords(self) -> List[str]:
        return self.json["keywords"]

    @property
    def layout(self) -> str:
        return self.json["layout"]

    @property
    def legalities(self) -> Dict[str, str]:
        return self.json["legalities"]

    @property
    def loyalty(self) -> Optional[str]:
        return self.json.get("loyalty")

    @property
    def loyalty_int(self) -> Optional[int]:
        return parse_int_from_str(self.loyalty) if self.loyalty is not None else None

    @property
    def has_special_loyalty(self) -> bool:
        return self.loyalty is not None and self.loyalty_int is None

    @property
    def mana_cost(self) -> Optional[str]:
        return self.json.get("mana_cost")

    @property
    def oracle_text(self) -> Optional[str]:
        return self.json.get("oracle_text")

    @property
    def name(self) -> str:
        return self.json["name"]

    @property
    def name_parts(self) -> Set[str]:
        if not self.is_multipart:
            return {*self.name.split()}
        return {part for face in self.card_faces for part in face.name_parts}

    @property
    def power(self) -> Optional[int]:
        return self.json.get("power")

    @property
    def power_int(self) -> Optional[int]:
        return parse_int_from_str(self.power) if self.power is not None else None

    @property
    def has_special_power(self) -> bool:
        return self.power is not None and self.power_int is None

    @property
    def price(self) -> Optional[float]:
        """Return price in USD or `None` if unavailable.
        """
        return self.json["prices"].get("usd")

    @property
    def rarity(self) -> Rarity:
        return Rarity(self.json["rarity"])

    @property
    def has_special_rarity(self) -> bool:
        return self.rarity.is_special

    @property
    def is_common(self) -> bool:
        return self.rarity is Rarity.COMMON

    @property
    def is_uncommon(self) -> bool:
        return self.rarity is Rarity.UNCOMMON

    @property
    def is_rare(self) -> bool:
        return self.rarity is Rarity.RARE

    @property
    def is_mythic(self) -> bool:
        return self.rarity is Rarity.MYTHIC

    @property
    def released_at(self) -> datetime:
        return datetime.strptime(self.json["released_at"], "%Y-%m-%d")

    @property
    def reprint(self) -> bool:
        return self.json["reprint"]

    @property
    def set(self) -> str:
        return self.json["set"]

    @property
    def set_name(self) -> str:
        return self.json["set_name"]

    @property
    def set_type(self) -> str:
        return self.json["set_type"]

    @property
    def toughness(self) -> Optional[str]:
        return self.json.get("toughness")

    @property
    def toughness_int(self) -> Optional[int]:
        return parse_int_from_str(self.toughness) if self.toughness is not None else None

    @property
    def has_special_toughness(self) -> bool:
        return self.toughness is not None and self.toughness_int is None

    @property
    def type_line(self) -> str:
        return self.json["type_line"]

    @property
    def is_multipart(self) -> bool:
        return MULTIPART_SEPARATOR in self.name

    def is_legal_in(self, fmt: str) -> bool:
        """Returns `True` if this card is legal in format designated by `fmt`.

        :param fmt: Scryfall format designation
        :raises: ValueError on invalid format designation
        """
        if fmt.lower() not in self.formats:
            raise ValueError(f"No such format: {fmt!r}")

        if self.legalities[fmt] == "legal":
            return True
        return False

    def is_banned_in(self, fmt: str) -> bool:
        """Returns `True` if this card is banned in format designated by `fmt`.

        :param fmt: Scryfall format designation
        :raises: ValueError on invalid format designation
        """
        if fmt.lower() not in self.formats:
            raise ValueError(f"No such format: {fmt!r}")

        if self.legalities[fmt] == "banned":
            return True
        return False

    def is_restricted_in(self, fmt: str) -> bool:
        """Returns `True` if this card is restricted in format designated by `fmt`.

        :param fmt: Scryfall format designation
        :raises: ValueError on invalid format designation
        """
        if fmt.lower() not in self.formats:
            raise ValueError(f"No such format: {fmt!r}")

        if self.legalities[fmt] == "restricted":
            return True
        return False

    @lru_cache
    def parse_types(self) -> Optional[TypeLine]:
        if self.is_multipart:
            return None
        return TypeLine(self.type_line)

    @property
    def supertypes(self) -> List[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.supertypes})
        return self.parse_types().supertypes

    @property
    def regular_types(self) -> List[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.regular_types})
        return self.parse_types().regular_types

    @property
    def is_artifact(self) -> bool:
        return "Artifact" in self.regular_types

    @property
    def is_creature(self) -> bool:
        return "Creature" in self.regular_types

    @property
    def is_battle(self) -> bool:
        return "Battle" in self.regular_types

    @property
    def is_enchantment(self) -> bool:
        return "Enchantment" in self.regular_types

    @property
    def is_instant(self) -> bool:
        return "Instant" in self.regular_types

    @property
    def is_land(self) -> bool:
        return "Land" in self.regular_types

    @property
    def is_basic_land(self) -> bool:
        return "Land" in self.regular_types and "Basic" in self.supertypes

    @property
    def is_planeswalker(self) -> bool:
        return "Planeswalker" in self.regular_types

    @property
    def is_sorcery(self) -> bool:
        return "Sorcery" in self.regular_types

    @property
    def subtypes(self) -> List[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.subtypes})
        return self.parse_types().subtypes

    @property
    def races(self) -> List[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.races})
        return self.parse_types().races

    @property
    def classes(self) -> List[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.classes})
        return self.parse_types().classes

    @property
    def is_permanent(self) -> bool:
        if self.is_multipart:
            return all(face.parse_types().is_permanent for face in self.card_faces)
        return self.parse_types().is_permanent

    @property
    def is_nonpermanent(self) -> bool:
        if self.is_multipart:
            return all(face.parse_types().is_nonpermanent for face in self.card_faces)
        return self.parse_types().is_nonpermanent

    @property
    def is_alchemy_rebalance(self) -> bool:
        return self.name.startswith(ALCHEMY_REBALANCE_INDICATOR)

    @cached_property
    def alchemy_rebalance(self) -> Optional["Card"]:
        """Find Alchemy rebalanced version of this card and return it, or 'None' if there's no
        such card.
        """
        return find_by_name(f"{ALCHEMY_REBALANCE_INDICATOR}{self.name}")

    @property
    def alchemy_rebalance_original(self) -> Optional["Card"]:
        """If this card is Alchemy rebalance, return the original card. Return 'None' otherwise.
        """
        if not self.is_alchemy_rebalance:
            return None
        if not self.is_multipart:
            return find_by_name(self.name[2:], exact=True)
        # is multipart
        first_part_name, *_ = self.name.split(MULTIPART_SEPARATOR)
        original_name = first_part_name[2:]
        original = from_iterable(
            self.json["all_parts"],
            lambda p: original_name in p["name"] and not p["name"].startswith(
                ALCHEMY_REBALANCE_INDICATOR)
        )
        if original:
            return find_by_name(original["name"], exact=True)
        return None

    @property
    def has_alchemy_rebalance(self) -> bool:
        return self.alchemy_rebalance is not None

    @staticmethod
    def parse_lord_sentences(oracle_text: str) -> List[LordSentence]:
        if not oracle_text:
            return []
        lord_sentences = []
        for sentence in oracle_text.split("."):
            lord_sentence = LordSentence(sentence)
            if lord_sentence.is_valid:
                lord_sentences.append(lord_sentence)
        return lord_sentences

    @cached_property
    def lord_sentences(self) -> List[LordSentence]:
        sentences = []
        if self.is_multipart:
            for face in self.card_faces:
                sentences += face.lord_sentences
            return sentences
        return self.parse_lord_sentences(self.oracle_text)

    @property
    def multiples_allowed(self) -> bool:
        if not self.oracle_text:
            return False
        if "deck can have any number of cards named" in self.oracle_text:
            return True
        return False


@lru_cache
def bulk_data() -> Set[Card]:
    """Return Scryfall JSON data as set of Card objects.
    """
    source = getdir(DATADIR) / FILENAME
    if not source.exists():
        download_scryfall_bulk_data()

    with source.open() as f:
        data = json.load(f)

    return {Card(card_data) for card_data in data}


def games(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of string designations for games that can be played with cards in Scryfall data.
    """
    data = data if data else bulk_data()
    result = set()
    for card in data:
        result.update(card.games)

    return sorted(result)


def colors(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of string designations for MtG colors in Scryfall data.
    """
    data = data if data else bulk_data()
    result = set()
    for card in data:
        result.update(card.colors)
    return sorted(result)


def sets(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of string codes for MtG sets in Scryfall data (e.g. 'bro' for The Brothers'
    War).
    """
    data = data if data else bulk_data()
    return sorted({card.set for card in data})


def formats() -> List[str]:
    """Return list of string designations for MtG formats in Scryfall data.
    """
    return next(iter(bulk_data())).formats


def layouts(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of Scryfall string designations for card layouts in ``data``.
    """
    data = data if data else bulk_data()
    return sorted({card.layout for card in data})


def set_names(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of MtG set names in Scryfall data.
    """
    data = data if data else bulk_data()
    return sorted({card.set_name for card in data})


def rarities(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of MtG card rarities in Scryfall data.
    """
    data = data if data else bulk_data()
    return sorted({card.rarity.value for card in data})


def keywords(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of MtG card keywords in Scryfall data.
    """
    data = data if data else bulk_data()
    result = set()
    for card in data:
        result.update(card.keywords)
    return sorted(result)


def find_cards(predicate: Callable[[Card], bool],
               data: Optional[Iterable[Card]] = None) -> Set[Card]:
    """Return list of cards from ``data`` that satisfy ``predicate``.
    """
    data = data if data else bulk_data()
    return {card for card in data if predicate(card)}


@lru_cache
def set_cards(*set_codes: str, data: Optional[Iterable[Card]] = None) -> Set[Card]:
    """Return card data for sets designated by ``set_codes``.
    """
    return find_cards(lambda c: c.set in [code.lower() for code in set_codes], data)


@lru_cache
def arena_cards() -> Set[Card]:
    """Return Scryfall bulk data filtered for only cards available on Arena.
    """
    return find_cards(lambda c: "arena" in c.games)


@lru_cache
def format_cards(fmt: str, data: Optional[Iterable[Card]] = None) -> Set[Card]:
    """Return card data for MtG format designated by ``fmt``.
    """
    return find_cards(lambda c: c.is_legal_in(fmt), data)


def find_card(predicate: Callable[[Card], bool], data: Optional[Iterable[Card]] = None,
              narrow_by_collector_number=False) -> Optional[Card]:
    """Return card data from ``data`` that satisfies ``predicate`` or `None`.
    """
    data = data if data else bulk_data()
    if not narrow_by_collector_number:
        return from_iterable(data, predicate)

    cards = find_cards(predicate, data)
    cards = [card for card in cards if card.collector_number_int]
    cards = sorted(cards, key=lambda c: c.collector_number_int)
    # return card with the smallest collector number
    return cards[0] if cards else None


def find_by_name(card_name: str, data: Optional[Iterable[Card]] = None,
                 exact=False, narrow_by_collector_number=False) -> Optional[Card]:
    """Return a Scryfall card data of provided name or `None`.
    """
    data = data if data else bulk_data()
    if exact:
        return find_card(lambda c: c.name == card_name, data, narrow_by_collector_number)
    return find_card(lambda c: card_name.lower() in c.name.lower(), data,
                     narrow_by_collector_number)


def find_by_parts(name_parts: Iterable[str],
                  data: Optional[Iterable[Card]] = None) -> Optional[Card]:
    """Return a Scryfall card data designated by provided ``name_parts`` or `None`.
    """
    if isinstance(name_parts, str):
        name_parts = name_parts.split()
    data = data if data else bulk_data()
    return find_card(lambda c: all(part.lower() in c.name.lower() for part in name_parts), data)


def find_by_collector_number(collector_number: int,
                             data: Optional[Iterable[Card]] = None) -> Optional[Card]:
    """Return a Scryfall card data designated by provided ``collector_number`` from ``data`` or
    `None`.
    """
    data = data if data else bulk_data()
    data = [card for card in data if card.collector_number_int]
    return find_card(lambda c: c.collector_number == collector_number, data)


def find_by_name_narrowed_by_collector_number(
        name: str, data: Optional[Iterable[Card]] = None) -> Optional[Card]:
    """Return a Scryfall card data of provided name or `None`.
    """
    data = data if data else bulk_data()
    card = find_by_name(name, data, exact=True, narrow_by_collector_number=True)
    if card:
        return card
    # try less strictly
    card = find_by_name(name, data, exact=False, narrow_by_collector_number=True)
    return card if card else None


def find_by_id(scryfall_id: str, data: Optional[Iterable[Card]] = None) -> Optional[Card]:
    """Return a Scryfall card data of provided ``scryfall_id``.
    """
    data = data if data else bulk_data()
    return from_iterable(data, lambda c: c.id == scryfall_id)


class ColorIdentityDistibution:
    """Distribution of `color_identity` in card data.
    """

    @property
    def colorsmap(self) -> DefaultDict[Color, List[Card]]:
        """Return mapping of cards to colors.
        """
        return self._colorsmap

    @property
    def colors(self) -> List[Tuple[Color, List[Card]]]:
        """Return list of (color, cards) tuples sorted by color.
        """
        return self._colors

    def __init__(self, data: Optional[Iterable[Card]] = None) -> None:
        self._data = bulk_data() if not data else data
        self._colorsmap = defaultdict(list)
        for card in self._data:
            self._colorsmap[Color(tuple(card.color_identity))].append(card)
        self._colors = sorted([(k, v) for k, v in self._colorsmap.items()],
                              key=lambda p: (len(p[0].value), p[0].value))
        Triple = namedtuple("Triple", "color quantity percentage")
        self._triples = [Triple(c[0], len(c[1]), len(c[1]) / len(bulk_data()))
                         for c in self.colors]
        self._triples.sort(key=lambda t: t[1], reverse=True)

    def print(self) -> None:
        """Print this color distribution.
        """
        triples_str = [(str(t.color), f"quantity={t.quantity}", f"percentage={t.percentage:.4f}%")
                       for t in self._triples]
        pprint(triples_str)

    def color(self, color: Color) -> Optional[Tuple[Color, List[Card]]]:
        return from_iterable(self.colors, lambda c: c[0] is color)


def print_color_identity_distribution(data: Optional[Iterable[Card]] = None) -> None:
    dist = ColorIdentityDistibution(data)
    dist.print()


class InvalidDeckError(ValueError):
    """Raised on invalid decks.
    """


class Deck:
    """A deck of cards suitable for Constructed formats.
    """
    MIN_MAINBOARD_SIZE = 60
    MAX_SIDEBOARD_SIZE = 15

    @cached_property
    def mainboard(self) -> List[Card]:
        return [*itertools.chain(*self._playsets.values())]

    @property
    def sideboard(self) -> List[Card]:
        return self._sideboard

    @property
    def has_sideboard(self) -> bool:
        return bool(self.sideboard)

    @property
    def commander(self) -> Optional[Card]:
        return self._commander

    @property
    def companion(self) -> Optional[Card]:
        return self._companion

    @property
    def max_playset_count(self) -> int:
        return self._max_playset_count

    @property
    def all_cards(self) -> List[Card]:
        return [*self.mainboard, *self.sideboard]

    @property
    def color_identity(self) -> Color:
        return Color.from_cards(self.all_cards)

    @property
    def artifacts(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_artifact]

    @property
    def battles(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_battle]

    @property
    def creatures(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_creature]

    @property
    def enchantments(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_enchantment]

    @property
    def instants(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_instant]

    @property
    def lands(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_land]

    @property
    def planeswalkers(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_planeswalker]

    @property
    def sorceries(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_sorcery]

    @property
    def commons(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_common]

    @property
    def uncommons(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_uncommon]

    @property
    def rares(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_rare]

    @property
    def mythics(self) -> List[Card]:
        return [card for card in self.mainboard if card.is_mythic]

    @property
    def total_rarity_weight(self) -> float:
        return sum(card.rarity.weight for card in self.mainboard)

    @property
    def avg_rarity_weight(self):
        return self.total_rarity_weight / len(self.mainboard)

    @property
    def avg_cmc(self) -> float:
        return sum(card.cmc for card in self.mainboard) / len(self.mainboard)

    def __init__(self, mainboard: Iterable[Card], sideboard: Optional[Iterable[Card]] = None,
                 commander: Optional[Card] = None, companion: Optional[Card] = None) -> None:
        self._sideboard = [*sideboard] if sideboard else []
        self._companion = companion
        self._sideboard = [companion, *self.sideboard] if companion else self.sideboard
        if len(self.sideboard) > self.MAX_SIDEBOARD_SIZE:
            raise InvalidDeckError(f"Invalid sideboard size: {len(self.sideboard)} "
                                   f"> {self.MAX_SIDEBOARD_SIZE}")

        self._commander = commander
        if commander:
            for card in [*mainboard, *self.sideboard]:
                if any(letter not in commander.colors for letter in card.colors):
                    raise InvalidDeckError(f"Color of {card} doesn't match "
                                           f"commander color: {card.colors}!={commander.colors}")
            mainboard = [commander, *mainboard]

        self._max_playset_count = 1 if commander is not None else 4
        self._playsets: DefaultDict[Card, List[Card]] = defaultdict(list)
        for card in mainboard:
            if card.has_special_rarity:
                raise InvalidDeckError(f"Invalid rarity for {card.name!r}: {card.rarity.value!r}")
            self._playsets[card].append(card)
        self._validate_mainboard()
        if self.sideboard:
            self._validate_sideboard()

    def _validate_mainboard(self) -> None:
        for playset in self._playsets.values():
            card = playset[0]
            if card.is_basic_land or card.multiples_allowed:
                pass
            else:
                if len(playset) > self.max_playset_count:
                    raise InvalidDeckError(f"Invalid mainboard. Too many occurances of"
                                           f" {card.name!r}: "
                                           f"{len(playset)} > {self.max_playset_count}")
        if len(self.mainboard) < self.MIN_MAINBOARD_SIZE:
            raise InvalidDeckError(f"Invalid deck size: {len(self.mainboard)} "
                                   f"< {self.MIN_MAINBOARD_SIZE}")

    def _validate_sideboard(self) -> None:
        temp_playsets = defaultdict(list)
        for card in self.all_cards:
            temp_playsets[card].append(card)
        for playset in temp_playsets.values():
            card = playset[0]
            if card.is_basic_land or card.multiples_allowed:
                pass
            else:
                if len(playset) > self.max_playset_count:
                    raise InvalidDeckError(f"Invalid sideboard. Too many occurances of"
                                           f" {playset[0].name!r} in mainboard and sideboard "
                                           f"combined: "
                                           f"{len(playset)} > {self.max_playset_count}")

    def __repr__(self) -> str:
        reprs = [
            ("avg_cmc", f"{self.avg_cmc:.2f}"),
            ("avg_rarity_weight", f"{self.avg_rarity_weight:.1f}"),
            ("color_identity", self.color_identity.name),
            ("artifacts", len(self.artifacts)),
            ("battles", len(self.battles)),
            ("creatures", len(self.creatures)),
            ("enchantments", len(self.enchantments)),
            ("instants", len(self.instants)),
            ("lands", len(self.lands)),
            ("planeswalkers", len(self.planeswalkers)),
            ("sorceries", len(self.sorceries)),
        ]
        if self.commander:
            reprs.append(("commander", str(self.commander)))
        if self.companion:
            reprs.append(("companion", str(self.companion)))
        reprs.append(("sideboard", self.has_sideboard))
        return getrepr(self.__class__, *reprs)
