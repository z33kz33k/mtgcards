"""

    mtgcards.yt.parsers.tcgplayer.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse TCG Player decklist page.

    @author: z33k

"""
from enum import Enum, auto
from typing import Optional, Set

from mtgcards.scryfall import Deck, Card
from mtgcards.yt.parsers import UrlParser


# html parsing


class TcgPlayerParser(UrlParser):
    """Parser of TCG Player decklist page.
    """
    def _parse(self) -> Optional[Deck]:
        pass
