# mtgcards
Scrape data on MtG decks.

### Description

This is a hobby project.

It started as a card data scraping from `MTG Goldfish`. Then, some JumpIn! packets info scraping 
was added. Then, there was some play with Limited data from [17lands](https://www.17lands.com) when 
I thought I had to bear with utter boringness of that format (before the dawn of Golden Packs on 
Arena) [_This part has been deprecated and moved to `archive` package_]. Then, I discovered I 
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
* Scraping YT videos description's for decks:    
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
* Assessing the meta:
    * Scraping Goldfish and MGTAZone for meta-decks (others in plans)
    * Scraping a singular Untapped meta-deck decklist page
* Exporting decks into a [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* I compiled a list of over 900 YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format          | Count | Percentage |
|:---|:----------------|------:|-----------:|
| 1  | standard        | 4874 |    30.82 % |
| 2  | commander       | 3996 |    25.27 % |
| 3  | modern          | 1610 |    10.18 % |
| 4  | historic        |  697 |     4.41 % |
| 5  | pioneer         |  632 |     4.00 % |
| 6  | brawl           |  617 |     3.90 % |
| 7  | timeless        |  612 |     3.87 % |
| 8  | explorer        |  576 |     3.64 % |
| 9  | pauper          |  532 |     3.36 % |
| 10 | legacy          |  513 |     3.24 % |
| 11 | undefined       |  505 |     3.19 % |
| 12 | premodern       |  154 |     0.97 % |
| 13 | alchemy         |  124 |     0.78 % |
| 14 | penny           |   92 |     0.58 % |
| 15 | duel            |   90 |     0.57 % |
| 16 | standardbrawl   |   77 |     0.49 % |
| 17 | paupercommander |   40 |     0.25 % |
| 18 | vintage         |   37 |     0.23 % |
| 19 | oathbreaker     |   14 |     0.09 % |
| 20 | oldschool       |   12 |     0.08 % |
| 21 | future          |    7 |     0.04 % |
| 22 | gladiator       |    4 |     0.03 % |
|  | TOTAL           | 15815 | 100.00 %|

| No | Source                 | Count | Percentage |
|:---|:-----------------------|------:|-----------:|
| 1  | moxfield.com           | 5315 |    33.61 % |
| 2  | aetherhub.com          | 2952 |    18.67 % |
| 3  | arena.decklist         | 2202 |    13.92 % |
| 4  | mtggoldfish.com        | 1622 |    10.26 % |
| 5  | archidekt.com          |  620 |     3.92 % |
| 6  | streamdecker.com       |  519 |     3.28 % |
| 7  | mtga.untapped.gg       |  420 |     2.66 % |
| 8  | tappedout.net          |  364 |     2.30 % |
| 9  | tcgplayer.com          |  362 |     2.29 % |
| 10 | melee.gg               |  286 |     1.81 % |
| 11 | deckstats.net          |  196 |     1.24 % |
| 12 | mtgdecks.net           |  163 |     1.03 % |
| 13 | mtgazone.com           |  144 |     0.91 % |
| 14 | scryfall.com           |  129 |     0.82 % |
| 15 | hareruyamtg.com        |  118 |     0.75 % |
| 16 | flexslot.gg            |   68 |     0.43 % |
| 17 | pennydreadfulmagic.com |   66 |     0.42 % |
| 18 | mtgtop8.com            |   58 |     0.37 % |
| 19 | manatraders.com        |   49 |     0.31 % |
| 20 | topdecked.com          |   42 |     0.27 % |
| 21 | mtg.cardsrealm.com     |   39 |     0.25 % |
| 22 | manastack.com          |   36 |     0.23 % |
| 23 | mtgarena.pro           |   23 |     0.15 % |
| 24 | cardhoarder.com        |   20 |     0.13 % |
| 25 | old.starcitygames.com  |    1 |     0.01 % |
| 26 | mtgotraders.com        |    1 |     0.01 % |
|  | TOTAL                  | 15815 | 100.00 %|
