"""

    mtgcards.scryfall.py
    ~~~~~~~~~~~~~~~~~~~
    Handle Scryfall data.

    @author: z33k

"""
import itertools
import json
import math
import re
from collections import defaultdict, namedtuple
from dataclasses import dataclass
from datetime import date
from enum import Enum
from functools import cached_property, lru_cache
from pprint import pprint
from types import EllipsisType
from typing import Callable, Iterable, Optional

import scrython
from tqdm import tqdm
from unidecode import unidecode

from mtgcards.const import DATA_DIR, Json
from mtgcards.mtgwiki import CLASSES, RACES
from mtgcards.utils import from_iterable, getfloat, getint, getrepr
from mtgcards.utils.files import download_file, getdir


CARDS_FILENAME = "scryfall_cards.json"
SETS_FILENAME = "scryfall_sets.json"


class ScryfallError(ValueError):
    """Raised on invalid Scryfall data.
    """


def download_scryfall_bulk_data() -> None:
    """Download Scryfall 'Oracle Cards' bulk data JSON.
    """
    bd = scrython.BulkData()
    data = bd.data()[0]  # retrieve 'Oracle Cards' data dict
    url = data["download_uri"]
    download_file(url, file_name=CARDS_FILENAME, dst_dir=DATA_DIR)


@lru_cache  # pulling Scryfall data takes a few seconds
def api_set(set_code: str) -> scrython.sets.Code | None:
    try:
        return scrython.sets.Code(code=set_code)
    except scrython.ScryfallError:
        return None


def download_scryfall_set_data() -> None:
    """Ask Scryfall API for set data and dump it as .json files.
    """
    progress = tqdm(
        (api_set(code) for code in sorted(all_set_codes())), f"Downloading sets data...",
        total=len(all_set_codes()))

    data = []
    for set_data in progress:
        data.append(set_data.scryfallJson)

    dst = DATA_DIR / SETS_FILENAME
    with dst.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


MULTIFACE_SEPARATOR = "//"  # separates names of card's faces in multiface cards
MULTIFACE_LAYOUTS = (
    'adventure', 'art_series', 'double_faced_token', 'flip', 'modal_dfc', 'split', 'transform')

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
    def from_cards(cards: Iterable["Card"], identity=False) -> "Color":
        letters = set()
        for card in cards:
            color_value = card.color_identity.value if identity else card.color.value
            letters.update(color_value)
        return Color.from_letters(letters)


class Rarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    MYTHIC = "mythic"
    SPECIAL = "special"
    BONUS = "bonus"

    @property
    def weight(self) -> float:
        """Return fractional weight of this rarity based on frequency of occurrence in boosters.

        Based on: https://mtg.fandom.com/wiki/Rarity
        """
        if self is Rarity.MYTHIC or self is Rarity.BONUS:
            return 1 / (1 / 15 * 1 / 8)  # 120.00
        if self is Rarity.RARE:
            return 1 / (1 / 15 * 7 / 8)  # 17.14
        if self is Rarity.UNCOMMON:
            return 1 / (1 / 15 * 3)  # 5.00
        else:  # COMMON or SPECIAL
            return 1 / (1 / 15 * 11)  # 1.36

    @property
    def is_special(self) -> bool:
        return self is Rarity.SPECIAL or self is Rarity.BONUS


class TypeLine:
    """Parser of type line in Scryfall data.
    """
    SEPARATOR = "—"

    SUPERTYPES = {"Basic", "Elite", "Host", "Legendary", "Ongoing", "Snow", "Token", "Tribal",
                  "World"}
    PERMANENT_TYPES = {"Artifact", "Battle", "Creature", "Enchantment", "Land", "Planeswalker"}
    NONPERMANENT_TYPES = {"Sorcery", "Instant"}

    @property
    def text(self) -> str:
        return self._text

    @property
    def supertypes(self) -> list[str]:
        return [t for t in self._types if t in self.SUPERTYPES]

    @property
    def regular_types(self) -> list[str]:
        return [t for t in self._types if t not in self.SUPERTYPES]

    @property
    def subtypes(self) -> list[str]:
        return self._subtypes

    @property
    def is_permanent(self) -> bool:
        return all(p in self.PERMANENT_TYPES for p in self.regular_types)

    @property
    def is_nonpermanent(self) -> bool:
        # type not being permanent doesn't mean it's 'non-permanent', e.g. 'dungeon' is neither
        return all(p in self.NONPERMANENT_TYPES for p in self.regular_types)

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
    def races(self) -> list[str]:
        return [t for t in self.subtypes if t in RACES]

    @property
    def classes(self) -> list[str]:
        return [t for t in self.subtypes if t in CLASSES]

    def __init__(self, text: str) -> None:
        if MULTIFACE_SEPARATOR in text:
            raise ValueError("Multiface type line")
        self._text = text
        self._types, self._subtypes = self._parse()

    def _parse(self) -> tuple[list[str], list[str]]:
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

    def _parse(self) -> tuple[str, str, str]:
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

    def __eq__(self, other: "CardFace") -> bool:
        if not isinstance(other, CardFace):
            return False
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
    def name_parts(self) -> set[str]:
        return {*self.name.split()}

    @property
    def mana_cost(self) -> str:
        return self.json["mana_cost"]

    @property
    def type_line(self) -> str | None:
        return self.json.get("type_line")

    @property
    def oracle_text(self) -> str:
        return self.json["oracle_text"]

    @property
    def colors(self) -> list[str]:
        result = self.json.get("colors")
        return result if result else []

    @lru_cache
    def parse_types(self) -> TypeLine | None:
        return TypeLine(self.type_line) if self.type_line else None

    @property
    def supertypes(self) -> list[str]:
        return self.parse_types().supertypes if self.parse_types() else []

    @property
    def regular_types(self) -> list[str]:
        return self.parse_types().regular_types if self.parse_types() else []

    @property
    def subtypes(self) -> list[str]:
        return self.parse_types().subtypes if self.parse_types() else []

    @property
    def races(self) -> list[str]:
        return self.parse_types().races if self.parse_types() else []

    @property
    def classes(self) -> list[str]:
        return self.parse_types().classes if self.parse_types() else []

    @cached_property
    def lord_sentences(self) -> list[LordSentence]:
        return Card.parse_lord_sentences(self.oracle_text)

    @property
    def loyalty(self) -> str | None:
        return self.json.get("loyalty")

    @property
    def loyalty_int(self) -> int | None:
        return getint(self.loyalty)

    @property
    def has_special_loyalty(self) -> bool:
        return self.loyalty is not None and self.loyalty_int is None

    @property
    def power(self) -> int | None:
        return self.json.get("power")

    @property
    def power_int(self) -> int | None:
        return getint(self.power)

    @property
    def has_special_power(self) -> bool:
        return self.power is not None and self.power_int is None

    @property
    def toughness(self) -> str | None:
        return self.json.get("toughness")

    @property
    def toughness_int(self) -> int | None:
        return getint(self.toughness)

    @property
    def has_special_toughness(self) -> bool:
        return self.toughness is not None and self.toughness_int is None


@dataclass(frozen=True)
class Card:
    """Thin wrapper on Scryfall JSON data for a MtG card.

    Provides convenience access to the most important data pieces.
    """
    json: Json

    def __eq__(self, other: "Card") -> bool:
        if not isinstance(other, Card):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __lt__(self, other: "Card") -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.name < other.name

    def __str__(self) -> str:
        text = f"{self.name} ({self.set.upper()})"
        if self.collector_number:
            text += f" {self.collector_number}"
        return text

    def __repr__(self) -> str:
        return getrepr(
            self.__class__, ("name", self.name), ("set", self.set),
            ("collector_number", self.collector_number), ("color", self.color.name),
            ("type_line", self.type_line))

    def __post_init__(self) -> None:
        if self.is_multiface and self.card_faces is None:
            raise ScryfallError(f"Card faces data missing for multiface card {self.name!r}")
        if self.is_multiface and self.layout not in MULTIFACE_LAYOUTS:
            raise ScryfallError(f"Invalid layout {self.layout!r} for multiface card {self.name!r}")

    @property
    def card_faces(self) -> list[CardFace]:
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
    def colors(self) -> list[str]:
        if result := self.json.get("colors"):
            return result
        if self.is_multiface:
            return self.card_faces[0].colors
        return []

    @property
    def color(self) -> Color:
        return Color(tuple(self.colors))

    @property
    def collector_number(self) -> str:
        return self.json["collector_number"]

    @property
    def collector_number_int(self) -> int | None:
        """Return collector number as an integer, if it can be parsed as such.

        Note:
            Parsing logic strips any non-digits and then parses a number. This means that
            some alternative versions (e.g. Alchemy variants) will have the same number. However,
            it needs to be this way, because there are some basic cards that still have the
            collector number in this format (for instance both parts of Meld pairs from BRO).

            `collector_number` can look like that:
                {"12e", "67f", "233f", "A-268", "4e"}
        """
        return getint(self.collector_number)

    @property
    def formats(self) -> list[str]:
        """Return list of all Scryfall string format designations.
        """
        return sorted(fmt for fmt in self.legalities)

    @property
    def games(self) -> list[str]:
        return self.json["games"]

    @property
    def id(self) -> str:
        return self.json["id"]

    @property
    def keywords(self) -> list[str]:
        return self.json["keywords"]

    @property
    def layout(self) -> str:
        return self.json["layout"]

    @property
    def legalities(self) -> dict[str, str]:
        return self.json["legalities"]

    @property
    def loyalty(self) -> str | None:
        return self.json.get("loyalty")

    @property
    def loyalty_int(self) -> int | None:
        return getint(self.loyalty)

    @property
    def has_special_loyalty(self) -> bool:
        return self.loyalty is not None and self.loyalty_int is None

    @property
    def mana_cost(self) -> str | None:
        return self.json.get("mana_cost")

    @property
    def oracle_text(self) -> str | None:
        return self.json.get("oracle_text")

    @property
    def name(self) -> str:
        return self.json["name"]

    @property
    def name_parts(self) -> set[str]:
        if not self.is_multiface:
            return {*self.name.split()}
        return {part for face in self.card_faces for part in face.name_parts}

    @property
    def main_name(self) -> str:
        return self.card_faces[0].name if self.is_multiface else self.name

    @property
    def power(self) -> int | None:
        return self.json.get("power")

    @property
    def power_int(self) -> int | None:
        return getint(self.power)

    @property
    def has_special_power(self) -> bool:
        return self.power is not None and self.power_int is None

    @property
    def price(self) -> float | None:
        """Return price in USD or `None` if unavailable.
        """
        return getfloat(self.json["prices"].get("usd"))

    @property
    def price_tix(self) -> float | None:
        """Return price in MGTO's currency or `None` if unavailable.
        """
        return getfloat(self.json["prices"].get("tix"))

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
    def is_legendary(self) -> bool:
        return "Legendary" in self.supertypes

    @property
    def released_at(self) -> date:
        return date.fromisoformat(self.json["released_at"])

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
    def set_uri(self) -> str:
        return self.json["set_uri"]

    @property
    def toughness(self) -> str | None:
        return self.json.get("toughness")

    @property
    def toughness_int(self) -> int | None:
        return getint(self.toughness)

    @property
    def has_special_toughness(self) -> bool:
        return self.toughness is not None and self.toughness_int is None

    @property
    def type_line(self) -> str:
        return self.json["type_line"]

    @property
    def is_multiface(self) -> bool:
        return MULTIFACE_SEPARATOR in self.name

    def is_legal_in(self, fmt: str) -> bool:
        """Returns `True` if this card is legal in format designated by `fmt`.

        Run all_formats() to see available format designations.

        Args:
            fmt: Scryfall format designation

        Raises:
            ValueError on invalid format designation
        """
        fmt = fmt.lower()
        if fmt not in self.formats:
            raise ValueError(f"Invalid format: {fmt!r}. Can be only one of: '{self.formats}'")

        if self.legalities[fmt] == "legal":
            return True
        return False

    def is_banned_in(self, fmt: str) -> bool:
        """Returns `True` if this card is banned in format designated by `fmt`.

        Run all_formats() to see available format designations.

        Args:
            fmt: Scryfall format designation

        Raises:
            ValueError on invalid format designation
        """
        fmt = fmt.lower()
        if fmt not in self.formats:
            raise ValueError(f"Invalid format: {fmt!r}. Can be only one of: '{self.formats}'")

        if self.legalities[fmt] == "banned":
            return True
        return False

    def is_restricted_in(self, fmt: str) -> bool:
        """Returns `True` if this card is restricted in format designated by `fmt`.

        Run all_formats() to see available format designations.

        Args:
            fmt: Scryfall format designation

        Raises:
            ValueError on invalid format designation
        """
        fmt = fmt.lower()
        if fmt not in self.formats:
            raise ValueError(f"Invalid format: {fmt!r}. Can be only one of: '{self.formats}'")

        if self.legalities[fmt] == "restricted":
            return True
        return False

    @property
    def legal_formats(self) -> list[str]:
        return sorted([fmt for fmt, legality in self.legalities.items() if legality == "legal"])

    @property
    def banned_formats(self) -> list[str]:
        return sorted([fmt for fmt, legality in self.legalities.items() if legality == "banned"])

    @property
    def restricted_formats(self) -> list[str]:
        return sorted(
            [fmt for fmt, legality in self.legalities.items() if legality == "restricted"])

    @property
    def not_legal_anywhere(self) -> bool:
        return all(v == "not_legal" for v in self.legalities.values())

    @lru_cache
    def parse_types(self) -> TypeLine | None:
        if self.is_multiface:
            return None
        return TypeLine(self.type_line)

    @property
    def supertypes(self) -> list[str]:
        if self.is_multiface:
            return sorted({t for face in self.card_faces for t in face.supertypes})
        return self.parse_types().supertypes

    @property
    def regular_types(self) -> list[str]:
        if self.is_multiface:
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
    def subtypes(self) -> list[str]:
        if self.is_multiface:
            return sorted({t for face in self.card_faces for t in face.subtypes})
        return self.parse_types().subtypes

    @property
    def races(self) -> list[str]:
        if self.is_multiface:
            return sorted({t for face in self.card_faces for t in face.races})
        return self.parse_types().races

    @property
    def classes(self) -> list[str]:
        if self.is_multiface:
            return sorted({t for face in self.card_faces for t in face.classes})
        return self.parse_types().classes

    @property
    def is_permanent(self) -> bool:
        if self.is_multiface:
            return all(face.parse_types().is_permanent for face in self.card_faces)
        return self.parse_types().is_permanent

    @property
    def is_nonpermanent(self) -> bool:
        if self.is_multiface:
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
        if not self.is_multiface:
            return find_by_name(self.name[2:])
        # is multiface
        first_part_name, *_ = self.name.split(MULTIFACE_SEPARATOR)
        original_name = first_part_name[2:]
        original = from_iterable(
            self.json["all_parts"],
            lambda p: original_name in p["name"] and not p["name"].startswith(
                ALCHEMY_REBALANCE_INDICATOR)
        )
        if original:
            return find_by_name(original["name"])
        return None

    @property
    def has_alchemy_rebalance(self) -> bool:
        return self.alchemy_rebalance is not None

    @property
    def is_companion(self) -> bool:
        return "Companion" in self.keywords

    @staticmethod
    def parse_lord_sentences(oracle_text: str) -> list[LordSentence]:
        if not oracle_text:
            return []
        lord_sentences = []
        for sentence in oracle_text.split("."):
            lord_sentence = LordSentence(sentence)
            if lord_sentence.is_valid:
                lord_sentences.append(lord_sentence)
        return lord_sentences

    @cached_property
    def lord_sentences(self) -> list[LordSentence]:
        sentences = []
        if self.is_multiface:
            for face in self.card_faces:
                sentences += face.lord_sentences
            return sentences
        return self.parse_lord_sentences(self.oracle_text)

    @property
    def allowed_multiples(self) -> int | EllipsisType | None:
        if not self.oracle_text:
            return None
        if "deck can have any number of cards named" in self.oracle_text:
            return Ellipsis
        if "deck can have up to one" in self.oracle_text:
            return 1
        if "deck can have up to two" in self.oracle_text:
            return 2
        if "deck can have up to three" in self.oracle_text:
            return 3
        if "deck can have up to four" in self.oracle_text:
            return 4
        if "deck can have up to five" in self.oracle_text:
            return 5
        if "deck can have up to six" in self.oracle_text:
            return 6
        if "deck can have up to seven" in self.oracle_text:  # Seven Dwarves
            return 7
        if "deck can have up to eight" in self.oracle_text:
            return 8
        if "deck can have up to nine" in self.oracle_text:  # Nazgul
            return 9
        if "deck can have up to ten" in self.oracle_text:
            return 10
        if "deck can have up to eleven" in self.oracle_text:
            return 11
        if "deck can have up to twelve" in self.oracle_text:
            return 12
        return None


@dataclass(frozen=True)
class SetData:
    """Thin wrapper on Scryfall JSON data for a MtG card set.

    Provides convenience access to the most important data pieces.
    """
    json: Json

    def __eq__(self, other: "SetData") -> bool:
        if not isinstance(other, SetData):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __str__(self) -> str:
        text = f"{self.name} ({self.code})"

    def __repr__(self) -> str:
        reprs = [
            ("name", self.name), ("code", self.code), ("released_at", str(self.released_at)),
            ("set_type", self.set_type), ("card_count", self.card_count)]
        if self.block:
            reprs.append(("block", self.block))
        return getrepr(self.__class__, *reprs)

    @property
    def name(self) -> str:
        return self.json["name"]

    @property
    def id(self) -> str:
        return self.json["id"]

    @property
    def code(self) -> str:
        return self.json["code"]

    @property
    def released_at(self) -> date:
        return date.fromisoformat(self.json["released_at"])

    @property
    def set_type(self) -> str:
        return self.json["set_type"]

    @property
    def card_count(self) -> int:
        return self.json["card_count"]

    @property
    def is_digital(self) -> bool:
        return self.json["digital"]

    @property
    def block(self) -> str | None:
        return self.json.get("block")

    @property
    def is_official(self) -> bool:
        return len(self.code) == 3

    @property
    def is_expansion(self) -> bool:
        return self.set_type == "expansion"

    @property
    def is_core(self) -> bool:
        return self.set_type == "core"

    @property
    def is_alchemy(self) -> bool:
        return self.set_type == "alchemy"


@lru_cache
def sets() -> set[SetData]:
    """Return Scryfall JSON set data as set of CardSet objects
    """
    source = getdir(DATA_DIR) / SETS_FILENAME
    if not source.exists():
        raise FileNotFoundError(f"Scryfall sets data file is missing at: '{source}'")

    with source.open() as f:
        data = json.load(f)

    return {SetData(set_data) for set_data in data}


def find_sets(
        predicate: Callable[[SetData], bool],
        data: Iterable[SetData] | None = None) -> set[SetData]:
    """Return MtG sets from ``data`` that satisfy ``predicate``.
    """
    data = data or sets()
    return {card_set for card_set in data if predicate(card_set)}


def find_set(
        predicate: Callable[[SetData], bool],
        data: Iterable[SetData] | None = None) -> SetData | None:
    """Return a MtG set from ``data`` that satisfies ``predicate`` or `None`.
    """
    data = data or sets()
    return from_iterable(data, predicate)


def find_set_by_code(*set_codes: str, data: Iterable[SetData] | None = None) -> SetData | None:
    """Return a MtG set designated by provided code or `None`.
    """
    data = data or sets()
    return find_set(lambda s: s.set_code in {sc.lower() for sc in set_codes}, data)


# MtG sets with all cards not being legal anywhere
ILLEGAL = {
    'dsc', 'dsk', 'f12', 'f17', 'f18', 'h17', 'hho', 'l16', 'l17', 'p03', 'ptg', 'q07', 'ugl',
    'und', 'unh', 'ust'}


@lru_cache
def bulk_data(official_only=True, legal_only=True) -> set[Card]:
    """Return Scryfall JSON card data as set of Card objects.

    Note:
        According to: https://scryfall.com/docs/api/sets all sets with set codes three-letter
        long are consider official. This strict metric excludes Alchemy cards though, so
        this function takes care to consider Alchemy sets as official even if Scryfall doesn't.

    Args:
        official_only: return only cards from official sets, defaults to ``True``
        legal_only: return only cards from legal sets, defaults to ``True``

    Returns:
        set of Card objects
    """
    source = getdir(DATA_DIR) / CARDS_FILENAME
    if not source.exists():
        download_scryfall_bulk_data()

    with source.open() as f:
        data = json.load(f)

    cards = {Card(card_data) for card_data in data}

    if official_only:
        official_sets = {s.code for s in sets() if s.is_official or s.is_alchemy}
        if legal_only:
            return {c for c in cards if c.set in official_sets and c.set not in ILLEGAL}
        return {c for c in cards if c.set in official_sets}

    if legal_only:
        return {c for c in cards if c.set not in ILLEGAL}

    return cards


def games(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of string designations for games that can be played with cards in Scryfall data.
    """
    data = data or bulk_data()
    result = set()
    for card in data:
        result.update(card.games)

    return sorted(result)


def colors(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of string designations for MtG colors in Scryfall data.
    """
    data = data or bulk_data()
    result = set()
    for card in data:
        result.update(card.colors)
    return sorted(result)


def set_codes(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of string codes for MtG sets in Scryfall data (e.g. 'bro' for The Brothers'
    War).
    """
    data = data or bulk_data()
    return sorted({card.set for card in data})


def formats(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of string designations for MtG formats that are legal for cards in the data
    specified.
    """
    data = data or bulk_data()
    return sorted({*itertools.chain(*[c.legal_formats for c in data])})


@lru_cache
def all_set_codes() -> list[str]:
    """Return list of all string designations for MtG formats in Scryfall data.
    """
    return set_codes()


@lru_cache
def all_formats() -> list[str]:
    """Return list of all string designations for MtG formats in Scryfall data.
    """
    return next(iter(bulk_data())).formats


def arena_formats() -> list[str]:
    """Return list of all string designations for MtG formats that can be played on MTG Arena.
    """
    return ["alchemy", "brawl", "explorer", "historic", "standard", "standardbrawl", "timeless"]


def layouts(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of Scryfall string designations for card layouts in ``data``.
    """
    data = data or bulk_data()
    return sorted({card.layout for card in data})


def set_names(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of MtG set names in Scryfall data.
    """
    data = data or bulk_data()
    return sorted({card.set_name for card in data})


def rarities(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of MtG card rarities in Scryfall data.
    """
    data = data or bulk_data()
    return sorted({card.rarity.value for card in data})


def keywords(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of MtG card keywords in Scryfall data.
    """
    data = data or bulk_data()
    result = set()
    for card in data:
        result.update(card.keywords)
    return sorted(result)


def find_cards(
        predicate: Callable[[Card], bool], data: Iterable[Card] | None = None) -> set[Card]:
    """Return card data from ``data`` that satisfy ``predicate``.
    """
    data = data or bulk_data()
    return {card for card in data if predicate(card)}


def set_cards(*set_codes: str, data: Iterable[Card] | None = None) -> set[Card]:
    """Return card data for sets designated by ``set_codes``.

    Run all_sets() to see available set codes.
    """
    set_codes = [code.lower() for code in set_codes]
    available = set(all_set_codes())
    for code in set_codes:
        if code not in available:
            raise ValueError(f"Invalid set code: {code!r}. Can be only one of: '{all_set_codes()}'")
    return find_cards(lambda c: c.set in [code.lower() for code in set_codes], data)


@lru_cache
def arena_cards() -> set[Card]:
    """Return Scryfall bulk data filtered for only cards available on Arena.
    """
    return find_cards(lambda c: "arena" in c.games)


@lru_cache
def format_cards(fmt: str, data: Iterable[Card] | None = None) -> set[Card]:
    """Return card data for MtG format designated by ``fmt``.

    Run all_formats() to see available format designations.
    """
    fmt = fmt.lower()
    available = set(all_formats())
    if fmt not in available:
        raise ValueError(f"Invalid format: {fmt!r}. Can be only one of: '{all_formats()}'")
    return find_cards(lambda c: c.is_legal_in(fmt), data)


def find_card(
        predicate: Callable[[Card], bool], data: Iterable[Card] | None = None) -> Card | None:
    """Return a card from ``data`` that satisfies ``predicate`` or `None`.
    """
    data = data or bulk_data()
    return from_iterable(data, predicate)


def find_by_name(card_name: str, data: Iterable[Card] | None = None) -> Card | None:
    """Return a card designated by provided name or `None`.
    """
    data = data or bulk_data()
    if card := find_card(
        lambda c: unidecode(c.name) == unidecode(card_name), data):
        return card
    return find_card(
        lambda c: unidecode(c.main_name) == unidecode(card_name), data)


def find_by_parts(
        name_parts: Iterable[str], data: Iterable[Card] | None = None) -> Card | None:
    """Return a card designated by provided ``name_parts`` or `None`.
    """
    if isinstance(name_parts, str):
        name_parts = name_parts.split()
    data = data or bulk_data()
    return find_card(lambda c: all(part.lower() in c.name.lower() for part in name_parts), data)


def find_by_collector_number(collector_number: str | int, set_code: str) -> Card | None:
    """Return a card designated by provided ``collector_number`` or `None` if it cannot be
    found.

    It tries to match by Card's `collector_number_int` if specified collector number is an integer
    and by `collector_number` if it's a string.
    """
    data = set_cards(set_code)
    if isinstance(collector_number, int):
        data = {card for card in data if card.collector_number_int is not None}
        return find_card(lambda c: c.collector_number_int == collector_number, data)
    return find_card(lambda c: c.collector_number == collector_number, data)


def find_by_id(scryfall_id: str, data: Iterable[Card] | None = None) -> Card | None:
    """Return a card designated provided ``scryfall_id`` or `None`.
    """
    data = data or bulk_data()
    return from_iterable(data, lambda c: c.id == scryfall_id)


class ColorIdentityDistribution:
    """Distribution of `color_identity` in card data.
    """

    @property
    def colorsmap(self) -> defaultdict[Color, list[Card]]:
        """Return mapping of cards to colors.
        """
        return self._colorsmap

    @property
    def colors(self) -> list[tuple[Color, list[Card]]]:
        """Return list of (color, cards) tuples sorted by color.
        """
        return self._colors

    def __init__(self, data: Iterable[Card] | None = None) -> None:
        self._data = bulk_data() if not data else data
        self._colorsmap = defaultdict(list)
        # for card in self._data:
        #     self._colorsmap[Color(tuple(card.color_identity))].append(card)
        for card in self._data:
            self._colorsmap[card.color_identity].append(card)
        self._colors = sorted(
            [(k, v) for k, v in self._colorsmap.items()],
            key=lambda p: (len(p[0].value), p[0].value))
        Triple = namedtuple("Triple", "color quantity percentage")
        self._triples = [
            Triple(c[0], len(c[1]), len(c[1]) / len(bulk_data())) for c in self.colors]
        self._triples.sort(key=lambda t: t[1], reverse=True)

    def print(self) -> None:
        """Print this color distribution.
        """
        triples_str = [
            (str(t.color), f"quantity={t.quantity}", f"percentage={t.percentage:.4f}%")
            for t in self._triples]
        pprint(triples_str)

    def color(self, color: Color) -> tuple[Color, list[Card]] | None:
        return from_iterable(self.colors, lambda c: c[0] is color)


def print_color_identity_distribution(data: Iterable[Card] | None = None) -> None:
    dist = ColorIdentityDistribution(data)
    dist.print()


