"""

    mtgcards.limited.py
    ~~~~~~~~~~~~~~~~~~~
    Limited calculations.

    @author: z33k

"""
import csv
from bisect import bisect
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, EnumMeta
from pathlib import Path
from typing import Optional, Union

import numpy as np

from mtgcards.const import DATA_DIR, OUTPUT_DIR
from mtgcards.archive.goldfish.cards import Mana
from mtgcards.archive.goldfish.sets import MtgSet
from mtgcards.utils.files import getfile

CSV_MAP = {
    MtgSet.ZENDIKAR_RISING: getfile(f"{DATA_DIR}/17lands/zendikar_rising.csv"),
    MtgSet.KALDHEIM: getfile(f"{DATA_DIR}/17lands/kaldheim.csv"),
    MtgSet.STRIXHAVEN_SCHOOL_OF_MAGES: getfile(f"{DATA_DIR}/17lands/strixhaven.csv"),
    MtgSet.ADVENTURES_IN_THE_FORGOTTEN_REALMS: getfile(
        f"{DATA_DIR}/17lands/adventures_forgotten_realms.csv"),
    MtgSet.INNISTRAD_MIDNIGHT_HUNT: getfile(f"{DATA_DIR}/17lands/midnight_hunt.csv"),
    MtgSet.INNISTRAD_CRIMSON_VOW: getfile(f"{DATA_DIR}/17lands/crimson_vow.csv"),
    MtgSet.KAMIGAWA_NEON_DYNASTY: getfile(f"{DATA_DIR}/17lands/neon_dynasty.csv"),
    MtgSet.STREETS_OF_NEW_CAPENNA: getfile(f"{DATA_DIR}/17lands/streets_new_capenna.csv"),
}


class Color(Enum):
    """Enumeration of MtG deck colors played in Limited as classified in 17lands.com data.
    """
    MONO_WHITE = "Mono-White"
    MONO_BLUE = "Mono-Blue"
    MONO_BLACK = "Mono-Black"
    MONO_RED = "Mono-Red"
    MONO_GREEN = "Mono-Green"
    MONO_WHITE_WITH_SPLASH = "Mono-White + Splash"
    MONO_BLUE_WITH_SPLASH = "Mono-Blue + Splash"
    MONO_BLACK_WITH_SPLASH = "Mono-Black + Splash"
    MONO_RED_WITH_SPLASH = "Mono-Red + Splash"
    MONO_GREEN_WITH_SPLASH = "Mono-Green + Splash"
    AZORIUS = "Azorius (WU)"
    DIMIR = "Dimir (UB)"
    RAKDOS = "Rakdos (BR)"
    GRUUL = "Gruul (RG)"
    SELESNYA = "Selesnya (GW)"
    ORZHOV = "Orzhov (WB)"
    GOLGARI = "Golgari (BG)"
    SIMIC = "Simic (GU)"
    IZZET = "Izzet (UR)"
    BOROS = "Boros (RW)"
    AZORIUS_WITH_SPLASH = "Azorius (WU) + Splash"
    DIMIR_WITH_SPLASH = "Dimir (UB) + Splash"
    RAKDOS_WITH_SPLASH = "Rakdos (BR) + Splash"
    GRUUL_WITH_SPLASH = "Gruul (RG) + Splash"
    SELESNYA_WITH_SPLASH = "Selesnya (GW) + Splash"
    ORZHOV_WITH_SPLASH = "Orzhov (WB) + Splash"
    GOLGARI_WITH_SPLASH = "Golgari (BG) + Splash"
    SIMIC_WITH_SPLASH = "Simic (GU) + Splash"
    IZZET_WITH_SPLASH = "Izzet (UR) + Splash"
    BOROS_WITH_SPLASH = "Boros (RW) + Splash"
    JESKAI = "Jeskai (WUR)"
    SULTAI = "Sultai (UBG)"
    MARDU = "Mardu (BRW)"
    TEMUR = "Temur (RGU)"
    ABZAN = "Abzan (GWB)"
    ESPER = "Esper (WUB)"
    GRIXIS = "Grixis (UBR)"
    JUND = "Jund (BRG)"
    NAYA = "Naya (RGW)"
    BANT = "Bant (GWU)"
    JESKAI_WITH_SPLASH = "Jeskai (WUR) + Splash"
    SULTAI_WITH_SPLASH = "Sultai (UBG) + Splash"
    MARDU_WITH_SPLASH = "Mardu (BRW) + Splash"
    TEMUR_WITH_SPLASH = "Temur (RGU) + Splash"
    ABZAN_WITH_SPLASH = "Abzan (GWB) + Splash"
    ESPER_WITH_SPLASH = "Esper (WUB) + Splash"
    GRIXIS_WITH_SPLASH = "Grixis (UBR) + Splash"
    JUND_WITH_SPLASH = "Jund (BRG) + Splash"
    NAYA_WITH_SPLASH = "Naya (RGW) + Splash"
    BANT_WITH_SPLASH = "Bant (GWU) + Splash"

    @classmethod
    def to_mana(cls, color: "Color") -> tuple[Mana, ...]:
        if color is cls.MONO_WHITE:
            return Mana.WHITE,
        elif color is cls.MONO_BLUE:
            return Mana.BLUE,
        elif color is cls.MONO_BLACK:
            return Mana.BLACK,
        elif color is cls.MONO_RED:
            return Mana.RED,
        elif color is cls.MONO_GREEN:
            return Mana.GREEN,
        elif color is cls.MONO_WHITE_WITH_SPLASH:
            return Mana.WHITE, Mana.COLORLESS
        elif color is cls.MONO_BLUE_WITH_SPLASH:
            return Mana.BLUE, Mana.COLORLESS
        elif color is cls.MONO_BLACK_WITH_SPLASH:
            return Mana.BLACK, Mana.COLORLESS
        elif color is cls.MONO_RED_WITH_SPLASH:
            return Mana.RED, Mana.COLORLESS
        elif color is cls.MONO_GREEN_WITH_SPLASH:
            return Mana.GREEN, Mana.COLORLESS
        elif color is cls.AZORIUS:
            return Mana.WHITE, Mana.BLUE
        elif color is cls.DIMIR:
            return Mana.BLUE, Mana.BLACK
        elif color is cls.RAKDOS:
            return Mana.BLACK, Mana.RED
        elif color is cls.GRUUL:
            return Mana.RED, Mana.GREEN
        elif color is cls.SELESNYA:
            return Mana.GREEN, Mana.WHITE
        elif color is cls.ORZHOV:
            return Mana.WHITE, Mana.BLACK
        elif color is cls.GOLGARI:
            return Mana.BLACK, Mana.GREEN
        elif color is cls.SIMIC:
            return Mana.GREEN, Mana.BLUE
        elif color is cls.IZZET:
            return Mana.BLUE, Mana.RED
        elif color is cls.BOROS:
            return Mana.RED, Mana.WHITE
        elif color is cls.AZORIUS_WITH_SPLASH:
            return Mana.WHITE, Mana.BLUE, Mana.COLORLESS
        elif color is cls.DIMIR_WITH_SPLASH:
            return Mana.BLUE, Mana.BLACK, Mana.COLORLESS
        elif color is cls.RAKDOS_WITH_SPLASH:
            return Mana.BLACK, Mana.RED, Mana.COLORLESS
        elif color is cls.GRUUL_WITH_SPLASH:
            return Mana.RED, Mana.GREEN, Mana.COLORLESS
        elif color is cls.SELESNYA_WITH_SPLASH:
            return Mana.GREEN, Mana.WHITE, Mana.COLORLESS
        elif color is cls.ORZHOV_WITH_SPLASH:
            return Mana.WHITE, Mana.BLACK, Mana.COLORLESS
        elif color is cls.GOLGARI_WITH_SPLASH:
            return Mana.BLACK, Mana.GREEN, Mana.COLORLESS
        elif color is cls.SIMIC_WITH_SPLASH:
            return Mana.GREEN, Mana.BLUE, Mana.COLORLESS
        elif color is cls.IZZET_WITH_SPLASH:
            return Mana.BLUE, Mana.RED, Mana.COLORLESS
        elif color is cls.BOROS_WITH_SPLASH:
            return Mana.RED, Mana.WHITE, Mana.COLORLESS
        elif color is cls.JESKAI:
            return Mana.BLUE, Mana.RED, Mana.WHITE
        elif color is cls.SULTAI:
            return Mana.BLACK, Mana.GREEN, Mana.BLUE
        elif color is cls.MARDU:
            return Mana.RED, Mana.WHITE, Mana.BLACK
        elif color is cls.TEMUR:
            return Mana.GREEN, Mana.BLUE, Mana.RED
        elif color is cls.ABZAN:
            return Mana.WHITE, Mana.BLACK, Mana.GREEN
        elif color is cls.ESPER:
            return Mana.WHITE, Mana.BLUE, Mana.BLACK
        elif color is cls.GRIXIS:
            return Mana.BLUE, Mana.BLACK, Mana.RED
        elif color is cls.JUND:
            return Mana.BLACK, Mana.RED, Mana.GREEN
        elif color is cls.NAYA:
            return Mana.RED, Mana.GREEN, Mana.WHITE
        elif color is cls.BANT:
            return Mana.GREEN, Mana.WHITE, Mana.BLUE
        elif color is cls.JESKAI_WITH_SPLASH:
            return Mana.BLUE, Mana.RED, Mana.WHITE, Mana.COLORLESS
        elif color is cls.SULTAI_WITH_SPLASH:
            return Mana.BLACK, Mana.GREEN, Mana.BLUE, Mana.COLORLESS
        elif color is cls.MARDU_WITH_SPLASH:
            return Mana.RED, Mana.WHITE, Mana.BLACK, Mana.COLORLESS
        elif color is cls.TEMUR_WITH_SPLASH:
            return Mana.GREEN, Mana.BLUE, Mana.RED, Mana.COLORLESS
        elif color is cls.ABZAN_WITH_SPLASH:
            return Mana.WHITE, Mana.BLACK, Mana.GREEN, Mana.COLORLESS
        elif color is cls.ESPER_WITH_SPLASH:
            return Mana.WHITE, Mana.BLUE, Mana.BLACK, Mana.COLORLESS
        elif color is cls.GRIXIS_WITH_SPLASH:
            return Mana.BLUE, Mana.BLACK, Mana.RED, Mana.COLORLESS
        elif color is cls.JUND_WITH_SPLASH:
            return Mana.BLACK, Mana.RED, Mana.GREEN, Mana.COLORLESS
        elif color is cls.NAYA_WITH_SPLASH:
            return Mana.RED, Mana.GREEN, Mana.WHITE, Mana.COLORLESS
        elif color is cls.BANT_WITH_SPLASH:
            return Mana.GREEN, Mana.WHITE, Mana.BLUE, Mana.COLORLESS
        else:
            raise ValueError(f"Invalid color: {color}.")


MONO_COLORS = [color for color in Color if len(Color.to_mana(color)) == 1]
MONO_COLORS_WITH_SPLASH = [color for color in Color if len(Color.to_mana(color)) == 2
                           and Mana.COLORLESS in Color.to_mana(color)]
TWO_COLORS = [color for color in Color if len(Color.to_mana(color)) == 2
              and Mana.COLORLESS not in Color.to_mana(color)]
TWO_COLORS_WITH_SPLASH = [color for color in Color if len(Color.to_mana(color)) == 3
                          and Mana.COLORLESS in Color.to_mana(color)]
THREE_COLORS = [color for color in Color if len(Color.to_mana(color)) == 3
                and Mana.COLORLESS not in Color.to_mana(color)]
THREE_COLORS_WITH_SPLASH = [color for color in Color if len(Color.to_mana(color)) == 4
                            and Mana.COLORLESS in Color.to_mana(color)]


class Grade(Enum):
    """Enumeration of deck color grades.
    """
    F = "F"
    D_MINUS = "D-"
    D = "D"
    D_PLUS = "D+"
    C_MINUS = "C-"
    C = "C"
    C_PLUS = "C+"
    B_MINUS = "B-"
    B = "B"
    B_PLUS = "B+"
    A_MINUS = "A-"
    A = "A"
    A_PLUS = "A+"


DEFAULT_GRADESPAN_START = 50
DEFAULT_GRADESPAN_STOP = 60


def breakpoints(start: float = DEFAULT_GRADESPAN_START, stop: float = DEFAULT_GRADESPAN_STOP,
                count: int = len(Grade) - 1) -> list[float]:
    return [*np.linspace(start, stop, count)]


BREAKPOINTS = breakpoints()


def grade(score: float, breakpoints: Optional[list[float]] = None,
          grades: str | EnumMeta = Grade) -> str | EnumMeta:
    """Return a grade from supplied ``grades`` based on ``score`` and ``breakpoints``.

    Breakpoints are understood as a sequence of ordered floats corresponding to a score value that
    exactly merits one of the grades.
    """
    breakpoints = breakpoints or BREAKPOINTS
    if len(grades) != len(breakpoints) + 1:
        raise ValueError(f"Number of breakpoints must be one less than grades: "
                         f"{len(grades)} != {len(breakpoints)} + 1")
    i = bisect(breakpoints, score)
    return [*grades][i]


@dataclass()
class Performance:
    """Draft deck color performance according to 17lands.com data.
    """
    wins: int
    games: int
    color: Union[Color, Mana, None] = None
    mtgset: MtgSet | None = None
    grade_start: float | None = DEFAULT_GRADESPAN_START
    grade_stop: float | None = DEFAULT_GRADESPAN_STOP

    @property
    def winrate(self) -> float:
        return self.wins * 100 / self.games if self.games else 0.0

    @property
    def winrate_str(self) -> str:
        return f"{self.winrate:.2f}%"

    def __repr__(self) -> str:  # override
        if self.color:
            return f"{self.__class__.__name__}({self.color}, winrate={self.winrate_str}, " \
                   f"{self.grade})"
        return f"{self.__class__.__name__}(winrate={self.winrate_str}, {self.grade})"

    @property
    def grade(self) -> Grade:
        points = breakpoints(self.grade_start, self.grade_stop)
        return grade(self.winrate, points)

    @staticmethod
    def aggregate_performance(*performances: "Performance") -> "Performance":
        wins = sum(perf.wins for perf in performances)
        games = sum(perf.games for perf in performances)
        colors = {perf.color for perf in performances}
        color = [c for c in colors][0] if len(colors) == 1 else None
        mtgsets = {perf.mtgset for perf in performances}
        mgtset = [s for s in mtgsets][0] if len(colors) == 1 else None
        return Performance(wins, games, color, mgtset)


DECK_SIZE = 40
LAND_COUNT = 17
SPLASH_PERCENT = 3 * 100 / (DECK_SIZE - LAND_COUNT)  # splash is considered to be 3 cards
TWO_COLOR_WITH_SPLASH_PERCENT = (100 - SPLASH_PERCENT) / 2
THREE_COLOR_WITH_SPLASH_PERCENT = (100 - SPLASH_PERCENT) / 3


class SetParser:
    """Parser of set performance 17lands.com data.
    """
    def __init__(self, mtgset: MtgSet, csv_path: Path) -> None:
        self._mtgset, self._csv_path = mtgset, csv_path
        self._performances = self._parse()
        self._aggregate_performances = self._get_aggregate_performances()
        self._recalibrate_aggr_perfs()

    @property
    def mtgset(self) -> MtgSet:
        return self._mtgset

    @property
    def csv_path(self) -> Path:
        return self._csv_path

    def _parse(self) -> list[Performance]:
        perfs = []
        with self.csv_path.open(newline="") as f:
            for row in [r for r in csv.reader(f)][1:]:
                # parse only PremierDraft data
                perfs.append(Performance(int(row[3]), int(row[4]), Color(row[0])))
        return perfs

    @property
    def performances(self) -> list[Performance]:
        return self._performances

    @property
    def sorted_performances(self) -> list[Performance]:
        return sorted(self.performances, key=lambda p: p.winrate, reverse=True)

    @staticmethod
    def mana_weight(perf: Performance) -> float:
        if perf.color in MONO_COLORS:
            return 1.0
        elif perf.color in MONO_COLORS_WITH_SPLASH:
            return (100 - SPLASH_PERCENT) / 100
        elif perf.color in TWO_COLORS:
            return 0.5
        elif perf.color in TWO_COLORS_WITH_SPLASH:
            return TWO_COLOR_WITH_SPLASH_PERCENT / 100
        elif perf.color in THREE_COLORS:
            return 1 / 3
        elif perf.color in THREE_COLORS_WITH_SPLASH:
            return THREE_COLOR_WITH_SPLASH_PERCENT / 100
        else:
            raise ValueError(f"Invalid performance: {perf}.")

    def _get_aggregate_performances(self) -> dict[Mana, Performance]:
        aggregator = defaultdict(list)
        for perf in self.performances:
            manas = [mana for mana in Color.to_mana(perf.color) if mana is not Mana.COLORLESS]
            for mana in manas:
                ratio = self.mana_weight(perf)
                subperf = Performance(int(ratio * perf.wins), int(ratio * perf.games), mana)
                aggregator[mana].append(subperf)

        aggregate_perfs = {}
        for mana, subperfs in aggregator.items():
            aggregate_perfs.update({mana: Performance.aggregate_performance(*subperfs)})

        return aggregate_perfs

    def _recalibrate_aggr_perfs(self) -> None:
        # TODO: the worst performance can never get the worst grade, because bisect_right is
        #  used in grade() function
        min_ = min(perf.winrate for perf in self.aggregate_performances.values())
        max_ = max(perf.winrate for perf in self.aggregate_performances.values())
        for perf in self.aggregate_performances.values():
            perf.grade_start, perf.grade_stop = min_, max_

    @property
    def aggregate_performances(self) -> dict[Mana, Performance]:
        return self._aggregate_performances

    def _build_perf_text(self) -> str:
        title = self.mtgset.value.name.upper()
        lines = [title, "=" * len(title), ""]
        title = "DECK COLOR PERFORMANCE"
        lines.append(title)
        lines.append("=" * len(title))
        color_width = max(len(perf.color.value) for perf in self.performances) + 5
        grade_width = max(len(perf.grade.value) for perf in self.performances) + 2
        for perf in self.performances:
            lines.append(f"{perf.color.value.ljust(color_width)}"
                         f"{perf.grade.value.ljust(grade_width)} ({perf.winrate_str})")
        lines.append("")

        title = "AGGREGATE COLOR PERFORMANCE"
        lines.append(title)
        lines.append("=" * len(title))
        mana_width = max(len(mana.value) for mana in self.aggregate_performances) + 5
        grade_width = max(len(perf.grade.value)
                          for perf in self.aggregate_performances.values()) + 2
        for mana, perf in self.aggregate_performances.items():
            lines.append(f"{mana.value.ljust(mana_width)}"
                         f"{perf.grade.value.ljust(grade_width)} ({perf.winrate_str})")

        return "\n".join(lines)

    def to_file(self) -> None:
        filename = self.mtgset.value.code.lower() + "_17lands.txt"
        dest = Path(OUTPUT_DIR) / filename
        with dest.open("w", encoding="utf8") as f:
            f.write(self._build_perf_text())

        if dest.exists():
            print(f"{dest} has been written successfully.")


def dump_summary() -> None:
    for mtgset, csvfile in CSV_MAP.items():
        parser = SetParser(mtgset, csvfile)
        parser.to_file()



