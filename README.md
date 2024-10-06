# mtg
Scrape data on MtG decks.

### Description

This is a hobby project.

It started as a card data scraping from `MTG Goldfish`. Then, some JumpIn! packets info scraping 
was added. Then, there was some play with Limited data from [17lands](https://www.17lands.com) when 
I thought I had to bear with utter boringness of that format (before the dawn of Golden Packs on 
Arena) [_This part has been deprecated and moved to [archive](https://github.com/z33kz33k/mtg/tree/2d5eb0c758953d38ac51840ed3e49c2c25b4fe91/mtgcards/archive) package_]. Then, I discovered I 
don't need to scrape anything because [Scryfall](https://scryfall.com).

Then, I quit (Arena).

Now, the main focus is `decks` package and `yt` module (parsing data on youtubers' decks from YT videos 
descriptions).

### What works

* Scryfall data management via downloading bulk data with 
  [scrython](https://github.com/NandaScott/Scrython) and wrapping it in convenient abstractions
* Scraping YT channels for videos with decklists in descriptions (using no less than three Python 
  libraries: [scrapetube](https://github.com/dermasmid/scrapetube), 
  [pytubefix](https://github.com/JuanBindez/pytubefix), and 
  [youtubesearchpython](https://github.com/alexmercerind/youtube-search-python) to avoid bothering 
  with Google APIs)
* Scraping YT videos' descriptions for decks:    
    * Text decklists in Arena/MTGO format pasted into video descriptions are parsed into Deck objects
    * Links to decklist services are scraped into Deck objects. 25 services are supported so far:
        * [Aetherhub](https://aetherhub.com)
        * [Archidekt](https://archidekt.com)
        * [Cardhoarder](https://www.cardhoarder.com)
        * [Cardsrealm](https://mtg.cardsrealm.com/en-us/)
        * [Deckstats.net](https://deckstats.net)
        * [Flexslot](https://flexslot.gg)
        * [Goldfish](https://www.mtggoldfish.com)
        * [Hareruya](https://www.hareruyamtg.com/en/)
        * [Manatraders](https://www.manatraders.com)
        * [ManaStack](https://manastack.com/home)
        * [Melee.gg](https://melee.gg)
        * [Moxfield](https://www.moxfield.com)
        * [MTGArena.Pro](https://mtgarena.pro)
        * [MTGAZone](https://mtgazone.com)
        * [MTGDecks.net](https://mtgdecks.net)
        * [MTGO Traders](https://www.mtgotraders.com/store/index.html)
        * [MTGTop8](https://mtgtop8.com/index)
        * [PennyDreadfulMagic](https://pennydreadfulmagic.com)
        * [Scryfall](https://scryfall.com)
        * [StarCityGames](https://starcitygames.com)
        * [Streamdecker](https://www.streamdecker.com/landing)
        * [TappedOut](https://tappedout.net)
        * [TCGPlayer](https://infinite.tcgplayer.com)
        * [TopDecked](https://www.topdecked.com)
        * [Untapped](https://mtga.untapped.gg) 
    * Other decklist services are in plans (but, it does seem like I've pretty much exhausted the 
      possibilities already :))
    * Both Untapped decklist types featured in YT videos are supported: regular deck and profile deck
    * Both old and new TCGPlayer sites are supported
    * Both international and Japanese Hareruya sites are supported 
    * Due to their dynamic nature, Untapped, TCGPlayer (new site), ManaStack, Flexslot and TopDecked 
      are scraped using [Selenium](https://github.com/SeleniumHQ/Selenium). It's also used to scrape MTGTop8, MTGDecks.net and 
      Cardhoarder, even though those are very much static sites. Selenium is still helpful here 
      (either to click a consent button or bypass anti-bot measures)
    * All those mentioned above work even if they are behind shortener links and need unshortening first
    * Text decklists in links to pastebin-like services (like [Amazonian](https://www.youtube.com/@Amazonian) does) work too
    * If nothing is found in the video's description, then the author's comments are parsed
    * Deck's name and format are derived if not readily available
* Assessing the meta:
    * Scraping Goldfish and MGTAZone for meta-decks (others in plans)
    * Scraping a singular Untapped meta-deck decklist page
* Exporting decks into a [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* I compiled a list of **over 1k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | standard        | 6188 |    31.00 % |
| 2  | commander       | 5432 |    27.21 % |
| 3  | modern          | 1936 |     9.70 % |
| 4  | historic        |  789 |     3.95 % |
| 5  | brawl           |  762 |     3.82 % |
| 6  | pioneer         |  729 |     3.65 % |
| 7  | timeless        |  703 |     3.52 % |
| 8  | explorer        |  686 |     3.44 % |
| 9  | legacy          |  676 |     3.39 % |
| 10 | undefined       |  600 |     3.01 % |
| 11 | pauper          |  572 |     2.87 % |
| 12 | premodern       |  219 |     1.10 % |
| 13 | alchemy         |  210 |     1.05 % |
| 14 | duel            |   99 |     0.50 % |
| 15 | penny           |   97 |     0.49 % |
| 16 | standardbrawl   |   95 |     0.48 % |
| 17 | paupercommander |   58 |     0.29 % |
| 18 | vintage         |   40 |     0.20 % |
| 19 | gladiator       |   17 |     0.09 % |
| 20 | oathbreaker     |   16 |     0.08 % |
| 21 | irregular       |   15 |     0.08 % |
| 22 | oldschool       |   14 |     0.07 % |
| 23 | future          |    7 |     0.04 % |
|  | TOTAL           | 19960 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 6816 |    34.15 % |
| 2  | aetherhub.com          | 3558 |    17.83 % |
| 3  | arena.decklist         | 3072 |    15.39 % |
| 4  | mtggoldfish.com        | 2015 |    10.10 % |
| 5  | archidekt.com          |  785 |     3.93 % |
| 6  | streamdecker.com       |  571 |     2.86 % |
| 7  | mtga.untapped.gg       |  546 |     2.74 % |
| 8  | tcgplayer.com          |  504 |     2.53 % |
| 9  | tappedout.net          |  470 |     2.35 % |
| 10 | melee.gg               |  290 |     1.45 % |
| 11 | deckstats.net          |  223 |     1.12 % |
| 12 | mtgdecks.net           |  212 |     1.06 % |
| 13 | mtgazone.com           |  156 |     0.78 % |
| 14 | scryfall.com           |  156 |     0.78 % |
| 15 | hareruyamtg.com        |  142 |     0.71 % |
| 16 | flexslot.gg            |   89 |     0.45 % |
| 17 | pennydreadfulmagic.com |   70 |     0.35 % |
| 18 | mtgtop8.com            |   60 |     0.30 % |
| 19 | topdecked.com          |   54 |     0.27 % |
| 20 | manatraders.com        |   49 |     0.25 % |
| 21 | mtg.cardsrealm.com     |   39 |     0.20 % |
| 22 | manastack.com          |   38 |     0.19 % |
| 23 | mtgarena.pro           |   23 |     0.12 % |
| 24 | cardhoarder.com        |   20 |     0.10 % |
| 25 | old.starcitygames.com  |    1 |     0.01 % |
| 26 | mtgotraders.com        |    1 |     0.01 % |
|  | TOTAL                  | 19960 | 100.00 %|
