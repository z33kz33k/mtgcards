"""

    mtgcards.decks.streamdecker.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Streamdecker decklist page.

    @author: z33k

"""

from mtgcards.const import Json
from mtgcards.decks import Deck, InvalidDeckError, DeckParser
from mtgcards.scryfall import Card
from mtgcards.utils import timed_request


class StreamdeckerParser(DeckParser):
    """Parser of Streamdecker deck page.
    """
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/deck/{}"

    def __init__(self, url: str, fmt="standard") -> None:
        super().__init__(url, fmt)
        *_, self._decklist_id = url.split("/")
        self._json_data = timed_request(self.API_URL_TEMPLATE.format(self._decklist_id),
                                        return_json=True)
        self._deck = self._get_deck()

    def _get_deck(self) -> Deck | None:
        mainboard, sideboard, commander = [], [], None
        # TODO: adapt to streamdecker JSON
        # for _, card in self._json_data["mainboard"].items():
        #     mainboard.extend(self._parse_card(card))
        # for _, card in self._json_data["sideboard"].items():
        #     sideboard.extend(self._parse_card(card))
        # if self._json_data["commanders"]:
        #     card = next(iter(self._json_data["commanders"].items()))[1]
        #     result = self._parse_card(card)
        #     if result:
        #         commander = result[0]

        try:
            return Deck(mainboard, sideboard, commander)
        except InvalidDeckError:
            return None

    def _parse_card(self, json_card: Json) -> list[Card]:
        # TODO: adapt to streamdecker JSON
        # quantity = json_card["quantity"]
        # set_code, name = json_card["card"]["set"], json_card["card"]["name"]
        # return self._get_playset(name, quantity, set_code)
        pass