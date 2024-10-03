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
    * If nothing is found in the video's description, the first comment is checked
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
| 1  | standard        | 6011 |    30.75 % |
| 2  | commander       | 5371 |    27.48 % |
| 3  | modern          | 1900 |     9.72 % |
| 4  | historic        |  773 |     3.95 % |
| 5  | brawl           |  740 |     3.79 % |
| 6  | pioneer         |  715 |     3.66 % |
| 7  | timeless        |  691 |     3.54 % |
| 8  | explorer        |  669 |     3.42 % |
| 9  | legacy          |  662 |     3.39 % |
| 10 | undefined       |  594 |     3.04 % |
| 11 | pauper          |  562 |     2.88 % |
| 12 | premodern       |  217 |     1.11 % |
| 13 | alchemy         |  205 |     1.05 % |
| 14 | duel            |   98 |     0.50 % |
| 15 | penny           |   95 |     0.49 % |
| 16 | standardbrawl   |   91 |     0.47 % |
| 17 | paupercommander |   57 |     0.29 % |
| 18 | vintage         |   40 |     0.20 % |
| 19 | oathbreaker     |   16 |     0.08 % |
| 20 | oldschool       |   14 |     0.07 % |
| 21 | irregular       |   13 |     0.07 % |
| 22 | future          |    7 |     0.04 % |
| 23 | gladiator       |    4 |     0.02 % |
|  | TOTAL           | 19545 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 6688 |    34.22 % |
| 2  | aetherhub.com          | 3482 |    17.82 % |
| 3  | arena.decklist         | 2969 |    15.19 % |
| 4  | mtggoldfish.com        | 1984 |    10.15 % |
| 5  | archidekt.com          |  774 |     3.96 % |
| 6  | streamdecker.com       |  562 |     2.88 % |
| 7  | mtga.untapped.gg       |  519 |     2.66 % |
| 8  | tcgplayer.com          |  500 |     2.56 % |
| 9  | tappedout.net          |  465 |     2.38 % |
| 10 | melee.gg               |  289 |     1.48 % |
| 11 | deckstats.net          |  223 |     1.14 % |
| 12 | mtgdecks.net           |  212 |     1.08 % |
| 13 | mtgazone.com           |  155 |     0.79 % |
| 14 | scryfall.com           |  154 |     0.79 % |
| 15 | hareruyamtg.com        |  132 |     0.68 % |
| 16 | flexslot.gg            |   86 |     0.44 % |
| 17 | pennydreadfulmagic.com |   68 |     0.35 % |
| 18 | mtgtop8.com            |   60 |     0.31 % |
| 19 | topdecked.com          |   52 |     0.27 % |
| 20 | manatraders.com        |   49 |     0.25 % |
| 21 | mtg.cardsrealm.com     |   39 |     0.20 % |
| 22 | manastack.com          |   38 |     0.19 % |
| 23 | mtgarena.pro           |   23 |     0.12 % |
| 24 | cardhoarder.com        |   20 |     0.10 % |
| 25 | old.starcitygames.com  |    1 |     0.01 % |
| 26 | mtgotraders.com        |    1 |     0.01 % |
|  | TOTAL                  | 19545 | 100.00 %|
