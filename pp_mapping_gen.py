"""
PP (Pragmatic Play) megaxcess_game_type_mapping 生成器 (PP_SLOT, provider=22)
- 從 slot_game_setting_i18n 撈出 provider=22 的所有遊戲
- 對每一筆做模糊比對 PDF 名稱
- 信心度 >= 0.80 且唯一  → 輸出 INSERT/UPDATE SQL
- 多個候選分數接近 (差 < 0.05) → 若 game_type+offering 一致則自動取最高分，否則 AMBIGUOUS
- 完全比對不到           → 輸出到 UNMATCHED 區塊

PP PDF: List of EGLD-approved Electronic Games as of November 20, 2025
全部 415 款都是 eCASINO GAMES:
  SLOT: 413 款
  ARCADE-TYPE: 2 款 (BIG BASS CRASH #38, SPACEMAN #319)
"""

import re
import difflib
import mysql.connector

# ── DB 設定 ──────────────────────────────────────────────────────
DB_CONFIG = dict(
    host     = 'tiger-dev-rds.servicelab.sh',
    port     = 3306,
    user     = 'inno_rd',
    password = '29SU5Rkt',
    database = 'tiger_thirdparty',
    charset  = 'utf8mb4',
)

PROVIDER = 22  # PP_SLOT

# ── PDF 完整清單 (game_name, game_type, game_offering) ────────────
# 全部 eCASINO GAMES；ARCADE-TYPE 僅 BIG BASS CRASH 和 SPACEMAN
PDF_GAMES = [
    ('3 BUZZING WILDS',                                          'SLOT',        'ECASINO'),
    ('3 DANCING MONKEYS',                                        'SLOT',        'ECASINO'),
    ('3 KINGDOMS - BATTLE OF RED CLIFFS',                        'SLOT',        'ECASINO'),
    ('5 FROZEN CHARMS MEGAWAYS',                                 'SLOT',        'ECASINO'),
    ('5 LIONS',                                                  'SLOT',        'ECASINO'),
    ('5 LIONS DANCE',                                            'SLOT',        'ECASINO'),
    ('5 LIONS GOLD',                                             'SLOT',        'ECASINO'),
    ('5 LIONS MEGAWAYS',                                         'SLOT',        'ECASINO'),
    ('6 JOKERS',                                                 'SLOT',        'ECASINO'),
    ('7 PIGGIES',                                                'SLOT',        'ECASINO'),
    ('8 GOLDEN DRAGON CHALLENGE',                                'SLOT',        'ECASINO'),
    ('AFRICAN ELEPHANT',                                         'SLOT',        'ECASINO'),
    ('ALADDIN AND THE SORCERER',                                 'SLOT',        'ECASINO'),
    ('AMAZING MONEY MACHINE',                                    'SLOT',        'ECASINO'),
    ('ANCIENT EGYPT',                                            'SLOT',        'ECASINO'),
    ('ANCIENT EGYPT CLASSIC',                                    'SLOT',        'ECASINO'),
    ('ANGEL VS SINNER',                                          'SLOT',        'ECASINO'),
    ('ASGARD',                                                   'SLOT',        'ECASINO'),
    ('AZTEC BLAZE',                                              'SLOT',        'ECASINO'),
    ('AZTEC BONANZA',                                            'SLOT',        'ECASINO'),
    ('AZTEC GEMS',                                               'SLOT',        'ECASINO'),
    ('AZTEC GEMS DELUXE',                                        'SLOT',        'ECASINO'),
    ('AZTEC POWERNUDGE',                                         'SLOT',        'ECASINO'),
    ('AZTEC TREASURE HUNT',                                      'SLOT',        'ECASINO'),
    ('BADGE BLITZ',                                              'SLOT',        'ECASINO'),
    ('BARN FESTIVAL',                                            'SLOT',        'ECASINO'),
    ('BARNYARD MEGAHAYS MEGAWAYS',                               'SLOT',        'ECASINO'),
    ('BEWARE THE DEEP MEGAWAYS',                                 'SLOT',        'ECASINO'),
    ('BIG BASS - HOLD & SPINNER',                                'SLOT',        'ECASINO'),
    ('BIG BASS - SECRETS OF THE GOLDEN LAKE',                    'SLOT',        'ECASINO'),
    ('BIG BASS AMAZON XTREME',                                   'SLOT',        'ECASINO'),
    ('BIG BASS BONANZA',                                         'SLOT',        'ECASINO'),
    ('BIG BASS BONANZA - KEEPING IT REEL',                       'SLOT',        'ECASINO'),
    ('BIG BASS BONANZA - REEL ACTION',                           'SLOT',        'ECASINO'),
    ('BIG BASS BONANZA MEGAWAYS',                                'SLOT',        'ECASINO'),
    ('BIG BASS CHRISTMAS BASH',                                  'SLOT',        'ECASINO'),
    ('BIG BASS CRASH',                                           'ARCADE-TYPE', 'ECASINO'),
    ('BIG BASS DAY AT THE RACES',                                'SLOT',        'ECASINO'),
    ('BIG BASS FLOATS MY BOAT',                                  'SLOT',        'ECASINO'),
    ('BIG BASS HALLOWEEN',                                       'SLOT',        'ECASINO'),
    ('BIG BASS HOLD & SPINNER MEGAWAYS',                         'SLOT',        'ECASINO'),
    ("BIG BASS MISSION FISHIN'",                                 'SLOT',        'ECASINO'),
    ('BIG BASS SPLASH',                                          'SLOT',        'ECASINO'),
    ('BIG BASS VEGAS DOUBLE DOWN DELUXE',                        'SLOT',        'ECASINO'),
    ('BIG BURGER LOAD IT UP WITH XTRA CHEESE',                   'SLOT',        'ECASINO'),
    ('BIG JUAN',                                                 'SLOT',        'ECASINO'),
    ('BIGGER BASS BLIZZARD - CHRISTMAS CATCH',                   'SLOT',        'ECASINO'),
    ('BIGGER BASS BONANZA',                                      'SLOT',        'ECASINO'),
    ('BLACK BULL',                                               'SLOT',        'ECASINO'),
    ('BLADE & FANGS',                                            'SLOT',        'ECASINO'),
    ('BLAZING WILDS MEGAWAYS',                                   'SLOT',        'ECASINO'),
    ('BOMB BONANZA',                                             'SLOT',        'ECASINO'),
    ('BOOK OF FALLEN',                                           'SLOT',        'ECASINO'),
    ('BOOK OF GOLDEN SANDS',                                     'SLOT',        'ECASINO'),
    ('BOOK OF KINGDOMS',                                         'SLOT',        'ECASINO'),
    ('BOOK OF TUT MEGAWAYS',                                     'SLOT',        'ECASINO'),
    ('BOOK OF VIKINGS',                                          'SLOT',        'ECASINO'),
    ('BOUNTY GOLD',                                              'SLOT',        'ECASINO'),
    ('BOW OF ARTEMIS',                                           'SLOT',        'ECASINO'),
    ('BUFFALO KING',                                             'SLOT',        'ECASINO'),
    ('BUFFALO KING MEGAWAYS',                                    'SLOT',        'ECASINO'),
    ('BUFFALO KING UNTAMED MEGAWAYS',                            'SLOT',        'ECASINO'),
    ("CAISHEN'S CASH",                                           'SLOT',        'ECASINO'),
    ("CAISHEN'S GOLD",                                           'SLOT',        'ECASINO'),
    ('CANDY BLITZ',                                              'SLOT',        'ECASINO'),
    ('CANDY BLITZ BOMBS',                                        'SLOT',        'ECASINO'),
    ('CANDY JAR CLUSTERS',                                       'SLOT',        'ECASINO'),
    ('CANDY STARS',                                              'SLOT',        'ECASINO'),
    ('CASH BONANZA',                                             'SLOT',        'ECASINO'),
    ('CASH BOX',                                                 'SLOT',        'ECASINO'),
    ('CASH CHIPS',                                               'SLOT',        'ECASINO'),
    ('CASH ELEVATOR',                                            'SLOT',        'ECASINO'),
    ('CASH PATROL',                                              'SLOT',        'ECASINO'),
    ('CASTLE OF FIRE',                                           'SLOT',        'ECASINO'),
    ('CHASE FOR GLORY',                                          'SLOT',        'ECASINO'),
    ('CHESTS OF CAI SHEN',                                       'SLOT',        'ECASINO'),
    ('CHICKEN CHASE',                                            'SLOT',        'ECASINO'),
    ('CHICKEN DROP',                                             'SLOT',        'ECASINO'),
    ('CHILLI HEAT',                                              'SLOT',        'ECASINO'),
    ('CHILLI HEAT MEGAWAYS',                                     'SLOT',        'ECASINO'),
    ('CHRISTMAS BIG BASS BONANZA',                               'SLOT',        'ECASINO'),
    ('CHRISTMAS CAROL MEGAWAYS',                                 'SLOT',        'ECASINO'),
    ('CLEOCATRA',                                                'SLOT',        'ECASINO'),
    ('CLOVER GOLD',                                              'SLOT',        'ECASINO'),
    ('CLUB TROPICANA',                                           'SLOT',        'ECASINO'),
    ('COLOSSAL CASH ZONE',                                       'SLOT',        'ECASINO'),
    ('CONGO CASH',                                               'SLOT',        'ECASINO'),
    ('CONGO CASH XL',                                            'SLOT',        'ECASINO'),
    ('COSMIC CASH',                                              'SLOT',        'ECASINO'),
    ('COUNTRY FARMING',                                          'SLOT',        'ECASINO'),
    ('COWBOY COINS',                                             'SLOT',        'ECASINO'),
    ('COWBOYS GOLD',                                             'SLOT',        'ECASINO'),
    ('CRANK IT UP',                                              'SLOT',        'ECASINO'),
    ('CROWN OF FIRE',                                            'SLOT',        'ECASINO'),
    ('CRYSTAL CAVERNS MEGAWAYS',                                 'SLOT',        'ECASINO'),
    ('CURSE OF THE WEREWOLF MEGAWAYS',                           'SLOT',        'ECASINO'),
    ('CYBER HEIST',                                              'SLOT',        'ECASINO'),
    ('CYCLOPS SMASH',                                            'SLOT',        'ECASINO'),
    ('DANCE PARTY',                                              'SLOT',        'ECASINO'),
    ('DAY OF DEAD',                                              'SLOT',        'ECASINO'),
    ('DEMON POTS',                                               'SLOT',        'ECASINO'),
    ('DEVILICIOUS',                                              'SLOT',        'ECASINO'),
    ('DIAMOND CASCADE',                                          'SLOT',        'ECASINO'),
    ('DIAMOND STRIKE',                                           'SLOT',        'ECASINO'),
    ('DIAMONDS OF EGYPT',                                        'SLOT',        'ECASINO'),
    ('DING DONG CHRISTMAS BELLS',                                'SLOT',        'ECASINO'),
    ('DOWN THE RAILS',                                           'SLOT',        'ECASINO'),
    ('DRAGO - JEWELS OF FORTUNE',                                'SLOT',        'ECASINO'),
    ('DRAGON GOLD 88',                                           'SLOT',        'ECASINO'),
    ('DRAGON HERO',                                              'SLOT',        'ECASINO'),
    ('DRAGON HOT HOLD AND SPIN',                                 'SLOT',        'ECASINO'),
    ('DRAGON KINGDOM - EYES OF FIRE',                            'SLOT',        'ECASINO'),
    ('DRILL THAT GOLD',                                          'SLOT',        'ECASINO'),
    ('DWARF & DRAGON',                                           'SLOT',        'ECASINO'),
    ('DYNAMITE DIGGIN DOUG',                                     'SLOT',        'ECASINO'),
    ('EGYPTIAN FORTUNES',                                        'SLOT',        'ECASINO'),
    ('ELEMENTAL GEMS MEGAWAYS',                                  'SLOT',        'ECASINO'),
    ('EMERALD KING',                                             'SLOT',        'ECASINO'),
    ('EMERALD KING RAINBOW ROAD',                                'SLOT',        'ECASINO'),
    ('EMPTY THE BANK',                                           'SLOT',        'ECASINO'),
    ('EXCALIBUR UNLEASHED',                                      'SLOT',        'ECASINO'),
    ('EXTRA JUICY',                                              'SLOT',        'ECASINO'),
    ('EXTRA JUICY MEGAWAYS',                                     'SLOT',        'ECASINO'),
    ('EYE OF CLEOPATRA',                                         'SLOT',        'ECASINO'),
    ('EYE OF THE STORM',                                         'SLOT',        'ECASINO'),
    ('FAIRYTALE FORTUNE',                                        'SLOT',        'ECASINO'),
    ('FAT PANDA',                                                'SLOT',        'ECASINO'),
    ('FIESTA FORTUNE',                                           'SLOT',        'ECASINO'),
    ('FIRE 88',                                                  'SLOT',        'ECASINO'),
    ('FIRE ARCHER',                                              'SLOT',        'ECASINO'),
    ('FIRE HOT 100',                                             'SLOT',        'ECASINO'),
    ('FIRE HOT 20',                                              'SLOT',        'ECASINO'),
    ('FIRE HOT 40',                                              'SLOT',        'ECASINO'),
    ('FIRE HOT 5',                                               'SLOT',        'ECASINO'),
    ('FIRE PORTALS',                                             'SLOT',        'ECASINO'),
    ('FIRE STAMPEDE',                                            'SLOT',        'ECASINO'),
    ('FIRE STRIKE',                                              'SLOT',        'ECASINO'),
    ('FIRE STRIKE 2',                                            'SLOT',        'ECASINO'),
    ('FIREBIRD SPIRIT - CONNECT & COLLECT',                      'SLOT',        'ECASINO'),
    ('FISH EYE',                                                 'SLOT',        'ECASINO'),
    ("FISHIN' REELS",                                            'SLOT',        'ECASINO'),
    ('FLOATING DRAGON - DRAGON BOAT FESTIVAL HOLD & SPIN',       'SLOT',        'ECASINO'),
    ('FLOATING DRAGON HOLD & SPIN',                              'SLOT',        'ECASINO'),
    ('FLOATING DRAGON MEGAWAYS HOLD & SPIN',                     'SLOT',        'ECASINO'),
    ('FLOATING DRAGON NEW YEAR FESTIVAL ULTRA MEGAWAYS HOLD & SPIN', 'SLOT',   'ECASINO'),
    ('FORGE OF OLYMPUS',                                         'SLOT',        'ECASINO'),
    ('FORGING WILDS',                                            'SLOT',        'ECASINO'),
    ("FORTUNE HIT'N ROLL",                                       'SLOT',        'ECASINO'),
    ('FORTUNE OF GIZA',                                          'SLOT',        'ECASINO'),
    ('FORTUNES OF THE AZTEC',                                    'SLOT',        'ECASINO'),
    ('FRONT RUNNER ODDS ON',                                     'SLOT',        'ECASINO'),
    ('FROZEN TROPICS',                                           'SLOT',        'ECASINO'),
    ('FRUIT PARTY',                                              'SLOT',        'ECASINO'),
    ('FRUIT PARTY 2',                                            'SLOT',        'ECASINO'),
    ('FRUIT RAINBOW',                                            'SLOT',        'ECASINO'),
    ('FRUITY TREATS',                                            'SLOT',        'ECASINO'),
    ('FURY OF ODIN MEGAWAYS',                                    'SLOT',        'ECASINO'),
    ('GATES OF GATOT KACA',                                      'SLOT',        'ECASINO'),
    ('GATES OF HADES',                                           'SLOT',        'ECASINO'),
    ('GATES OF OLYMPUS',                                         'SLOT',        'ECASINO'),
    ('GATES OF OLYMPUS 1000',                                    'SLOT',        'ECASINO'),
    ('GATES OF OLYMPUS SUPER SCATTER',                           'SLOT',        'ECASINO'),
    ('GATES OF OLYMPUS XMAS 1000',                               'SLOT',        'ECASINO'),
    ('GATES OF VALHALLA',                                        'SLOT',        'ECASINO'),
    ('GEARS OF HORUS',                                           'SLOT',        'ECASINO'),
    ('GEM ELEVATOR',                                             'SLOT',        'ECASINO'),
    ('GEMS BONANZA',                                             'SLOT',        'ECASINO'),
    ('GEMS OF SERENGETI',                                        'SLOT',        'ECASINO'),
    ('GOBLIN HEIST POWERNUDGE',                                  'SLOT',        'ECASINO'),
    ('GODS OF GIZA',                                             'SLOT',        'ECASINO'),
    ('GOLD OASIS',                                               'SLOT',        'ECASINO'),
    ('GOLD PARTY',                                               'SLOT',        'ECASINO'),
    ('GOLD RUSH',                                                'SLOT',        'ECASINO'),
    ('GOOD LUCK & GOOD FORTUNE',                                 'SLOT',        'ECASINO'),
    ('GORILLA MAYHEM',                                           'SLOT',        'ECASINO'),
    ('GRAVITY BONANZA',                                          'SLOT',        'ECASINO'),
    ('GREAT RHINO',                                              'SLOT',        'ECASINO'),
    ('GREAT RHINO DELUXE',                                       'SLOT',        'ECASINO'),
    ('GREAT RHINO MEGAWAYS',                                     'SLOT',        'ECASINO'),
    ('GREEDY WOLF',                                              'SLOT',        'ECASINO'),
    ('GREEK GODS',                                               'SLOT',        'ECASINO'),
    ('HAND OF MIDAS 2',                                          'SLOT',        'ECASINO'),
    ('HAPPY HOOVES',                                             'SLOT',        'ECASINO'),
    ('HEART OF CLEOPATRA',                                       'SLOT',        'ECASINO'),
    ('HEART OF RIO',                                             'SLOT',        'ECASINO'),
    ('HEIST FOR THE GOLDEN NUGGETS',                             'SLOT',        'ECASINO'),
    ('HELLVIS WILD',                                             'SLOT',        'ECASINO'),
    ('HERCULES AND PEGASUS',                                     'SLOT',        'ECASINO'),
    ('HEROIC SPINS',                                             'SLOT',        'ECASINO'),
    ('HONEY HONEY HONEY',                                        'SLOT',        'ECASINO'),
    ('HOT CHILLI',                                               'SLOT',        'ECASINO'),
    ('HOT FIESTA',                                               'SLOT',        'ECASINO'),
    ('HOT PEPPER',                                               'SLOT',        'ECASINO'),
    ('HOT TO BURN',                                              'SLOT',        'ECASINO'),
    ('HOT TO BURN 7 DEADLY FREE SPINS',                          'SLOT',        'ECASINO'),
    ('HOT TO BURN EXTREME',                                      'SLOT',        'ECASINO'),
    ('HOT TO BURN HOLD AND SPIN',                                'SLOT',        'ECASINO'),
    ('HOT TO BURN MULTIPLIER',                                   'SLOT',        'ECASINO'),
    ('ICE LOBSTER',                                              'SLOT',        'ECASINO'),
    ('INFECTIVE WILD',                                           'SLOT',        'ECASINO'),
    ('JACKPOT BLAZE',                                            'SLOT',        'ECASINO'),
    ('JACKPOT HUNTER',                                           'SLOT',        'ECASINO'),
    ('JADE BUTTERFLY',                                           'SLOT',        'ECASINO'),
    ('JANE HUNTER AND THE MASK OF MONTEZUMA',                    'SLOT',        'ECASINO'),
    ('JASMINE DREAMS',                                           'SLOT',        'ECASINO'),
    ('JEWEL RUSH',                                               'SLOT',        'ECASINO'),
    ('JOHN HUNTER AND THE AZTEC TREASURE',                       'SLOT',        'ECASINO'),
    ('JOHN HUNTER AND THE BOOK OF TUT',                          'SLOT',        'ECASINO'),
    ('JOHN HUNTER AND THE MAYAN GODS',                           'SLOT',        'ECASINO'),
    ('JOKER KING',                                               'SLOT',        'ECASINO'),
    ("JOKER'S JEWELS HOT",                                       'SLOT',        'ECASINO'),
    ("JOKER'S JEWELS WILD",                                      'SLOT',        'ECASINO'),
    ('JUICY FRUITS',                                             'SLOT',        'ECASINO'),
    ('JUICY FRUITS MULTIHOLD',                                   'SLOT',        'ECASINO'),
    ('JUNGLE GORILLA',                                           'SLOT',        'ECASINO'),
    ('KINGDOM OF THE DEAD',                                      'SLOT',        'ECASINO'),
    ('KNIGHT HOT SPOTZ',                                         'SLOT',        'ECASINO'),
    ('LAMP OF INFINITY',                                         'SLOT',        'ECASINO'),
    ('LEPRECHAUN CAROL',                                         'SLOT',        'ECASINO'),
    ('LEPRECHAUN SONG',                                          'SLOT',        'ECASINO'),
    ("LOBSTER BOB'S SEA FOOD AND WIN IT",                        'SLOT',        'ECASINO'),
    ("LOBSTER BOB'S CRAZY CRAB SHACK",                           'SLOT',        'ECASINO'),
    ("LOKI'S RICHES",                                            'SLOT',        'ECASINO'),
    ('LUCKY LIGHTNING',                                          'SLOT',        'ECASINO'),
    ('MADAME DESTINY',                                           'SLOT',        'ECASINO'),
    ('MADAME DESTINY MEGAWAYS',                                  'SLOT',        'ECASINO'),
    ('MAGIC JOURNEY',                                            'SLOT',        'ECASINO'),
    ('MAGIC MONEY MAZE',                                         'SLOT',        'ECASINO'),
    ("MAGICIAN'S SECRETS",                                       'SLOT',        'ECASINO'),
    ('MAHJONG WINS SUPER SCATTER',                               'SLOT',        'ECASINO'),
    ('MAMMOTH GOLD MEGAWAYS',                                    'SLOT',        'ECASINO'),
    ("MASTER CHEN'S FORTUNE",                                    'SLOT',        'ECASINO'),
    ('MASTER JOKER',                                             'SLOT',        'ECASINO'),
    ("MEDUSA'S STONE",                                           'SLOT',        'ECASINO'),
    ('MIGHT OF RA',                                              'SLOT',        'ECASINO'),
    ('MIGHTY MUNCHING MELONS',                                   'SLOT',        'ECASINO'),
    ('MOCHIMON',                                                 'SLOT',        'ECASINO'),
    ('MONEY MOUSE',                                              'SLOT',        'ECASINO'),
    ('MONEY STACKS',                                             'SLOT',        'ECASINO'),
    ('MONKEY MADNESS',                                           'SLOT',        'ECASINO'),
    ('MONKEY WARRIOR',                                           'SLOT',        'ECASINO'),
    ('MONSTER SUPERLANCHE',                                      'SLOT',        'ECASINO'),
    ('MUERTOS MULTIPLIER MEGAWAYS',                              'SLOT',        'ECASINO'),
    ('MUSTANG GOLD',                                             'SLOT',        'ECASINO'),
    ('MUSTANG GOLD MEGAWAYS',                                    'SLOT',        'ECASINO'),
    ('MUSTANG TRAIL',                                            'SLOT',        'ECASINO'),
    ('MYSTERIOUS',                                               'SLOT',        'ECASINO'),
    ('MYSTERIOUS EGYPT',                                         'SLOT',        'ECASINO'),
    ('MYSTERY MICE',                                             'SLOT',        'ECASINO'),
    ('MYSTERY OF THE ORIENT',                                    'SLOT',        'ECASINO'),
    ('MYSTIC CHIEF',                                             'SLOT',        'ECASINO'),
    ('NILE FORTUNE',                                             'SLOT',        'ECASINO'),
    ('NORTH GUARDIANS',                                          'SLOT',        'ECASINO'),
    ('OCTOBEER FORTUNES',                                        'SLOT',        'ECASINO'),
    ('OODLES OF NOODLES',                                        'SLOT',        'ECASINO'),
    ("PANDA'S FORTUNE",                                          'SLOT',        'ECASINO'),
    ("PANDA'S FORTUNE 2",                                        'SLOT',        'ECASINO'),
    ('PEAK POWER',                                               'SLOT',        'ECASINO'),
    ('PEKING LUCK',                                              'SLOT',        'ECASINO'),
    ('PHOENIX FORGE',                                            'SLOT',        'ECASINO'),
    ('PIGGY BANK BILLS',                                         'SLOT',        'ECASINO'),
    ('PIGGY BANKERS',                                            'SLOT',        'ECASINO'),
    ('PINUP GIRLS',                                              'SLOT',        'ECASINO'),
    ('PIRATE GOLD',                                              'SLOT',        'ECASINO'),
    ('PIRATE GOLD DELUXE',                                       'SLOT',        'ECASINO'),
    ('PIRATE GOLDEN AGE',                                        'SLOT',        'ECASINO'),
    ('PIRATES PUB',                                              'SLOT',        'ECASINO'),
    ('PIXIE WINGS',                                              'SLOT',        'ECASINO'),
    ('PIZZA! PIZZA? PIZZA!',                                     'SLOT',        'ECASINO'),
    ('POMPEII MEGAREELS MEGAWAYS',                               'SLOT',        'ECASINO'),
    ('POT OF FORTUNE',                                           'SLOT',        'ECASINO'),
    ('POWER OF MERLIN MEGAWAYS',                                 'SLOT',        'ECASINO'),
    ('POWER OF NINJA',                                           'SLOT',        'ECASINO'),
    ('POWER OF THOR MEGAWAYS',                                   'SLOT',        'ECASINO'),
    ('PUB KINGS',                                                'SLOT',        'ECASINO'),
    ('PYRAMID BONANZA',                                          'SLOT',        'ECASINO'),
    ('PYRAMID KING',                                             'SLOT',        'ECASINO'),
    ('QUEEN OF GODS',                                            'SLOT',        'ECASINO'),
    ('QUEENIE',                                                  'SLOT',        'ECASINO'),
    ('RABBIT GARDEN',                                            'SLOT',        'ECASINO'),
    ('RAINBOW GOLD',                                             'SLOT',        'ECASINO'),
    ('RAINBOW REELS',                                            'SLOT',        'ECASINO'),
    ('RED HOT LUCK',                                             'SLOT',        'ECASINO'),
    ('REEL BANKS',                                               'SLOT',        'ECASINO'),
    ('RELEASE THE BISON',                                        'SLOT',        'ECASINO'),
    ('RELEASE THE KRAKEN',                                       'SLOT',        'ECASINO'),
    ('RELEASE THE KRAKEN 2',                                     'SLOT',        'ECASINO'),
    ('RELEASE THE KRAKEN MEGAWAYS',                              'SLOT',        'ECASINO'),
    ('RETURN OF THE DEAD',                                       'SLOT',        'ECASINO'),
    ('REVENGE OF LOKI MEGAWAYS',                                 'SLOT',        'ECASINO'),
    ('RIPE REWARDS',                                             'SLOT',        'ECASINO'),
    ('RISE OF GIZA POWERNUDGE',                                  'SLOT',        'ECASINO'),
    ('RISE OF PYRAMIDS',                                         'SLOT',        'ECASINO'),
    ('RISE OF SAMURAI 4',                                        'SLOT',        'ECASINO'),
    ('ROCK VEGAS MEGA HOLD & SPIN',                              'SLOT',        'ECASINO'),
    ('ROCKET BLAST MEGAWAYS',                                    'SLOT',        'ECASINO'),
    ('RUJAK BONANZA',                                            'SLOT',        'ECASINO'),
    ('RUNNING SUSHI',                                            'SLOT',        'ECASINO'),
    ('SAFARI KING',                                              'SLOT',        'ECASINO'),
    ('SAIYAN MANIA',                                             'SLOT',        'ECASINO'),
    ('SAMURAI CODE',                                             'SLOT',        'ECASINO'),
    ('SANTA',                                                    'SLOT',        'ECASINO'),
    ("SANTA'S GREAT GIFTS",                                      'SLOT',        'ECASINO'),
    ("SANTA'S WONDERLAND",                                       'SLOT',        'ECASINO'),
    ('SECRET CITY GOLD',                                         'SLOT',        'ECASINO'),
    ('SHIELD OF SPARTA',                                         'SLOT',        'ECASINO'),
    ('SHINING HOT 100',                                          'SLOT',        'ECASINO'),
    ('SHINING HOT 20',                                           'SLOT',        'ECASINO'),
    ('SHINING HOT 40',                                           'SLOT',        'ECASINO'),
    ('SHINING HOT 5',                                            'SLOT',        'ECASINO'),
    ('SKY BOUNTY',                                               'SLOT',        'ECASINO'),
    ('SLEEPING DRAGON',                                          'SLOT',        'ECASINO'),
    ('SMUGGLERS COVE',                                           'SLOT',        'ECASINO'),
    ('SNAKES & LADDERS 2 - SNAKE EYES',                          'SLOT',        'ECASINO'),
    ('SNAKES AND LADDERS MEGADICE',                              'SLOT',        'ECASINO'),
    ('SPACEMAN',                                                 'ARCADE-TYPE', 'ECASINO'),
    ('SPARTAN KING',                                             'SLOT',        'ECASINO'),
    ('SPELLBINDING MYSTERY',                                     'SLOT',        'ECASINO'),
    ('SPIN & SCORE MEGAWAYS',                                    'SLOT',        'ECASINO'),
    ('SPIRIT OF ADVENTURE',                                      'SLOT',        'ECASINO'),
    ('STAR BOUNTY',                                              'SLOT',        'ECASINO'),
    ('STAR PIRATES CODE',                                        'SLOT',        'ECASINO'),
    ('STARLIGHT CHRISTMAS',                                      'SLOT',        'ECASINO'),
    ('STARLIGHT PRINCESS',                                       'SLOT',        'ECASINO'),
    ('STARLIGHT PRINCESS 1000',                                  'SLOT',        'ECASINO'),
    ('STARLIGHT PRINCESS PACHI',                                 'SLOT',        'ECASINO'),
    ('STARZ MEGAWAYS',                                           'SLOT',        'ECASINO'),
    ('STICKY BEES',                                              'SLOT',        'ECASINO'),
    ('STRAWBERRY COCKTAIL',                                      'SLOT',        'ECASINO'),
    ('STREET RACER',                                             'SLOT',        'ECASINO'),
    ('STRIKING HOT 5',                                           'SLOT',        'ECASINO'),
    ('SUGAR BINGBING 1000',                                      'SLOT',        'ECASINO'),
    ('SUGAR RUSH',                                               'SLOT',        'ECASINO'),
    ('SUGAR RUSH 1000',                                          'SLOT',        'ECASINO'),
    ('SUGAR RUSH XMAS',                                          'SLOT',        'ECASINO'),
    ('SUGAR SUPREME POWERNUDGE',                                 'SLOT',        'ECASINO'),
    ('SUMO SUPREME MEGAWAYS',                                    'SLOT',        'ECASINO'),
    ('SUPER 7S',                                                 'SLOT',        'ECASINO'),
    ('SUPER JOKER',                                              'SLOT',        'ECASINO'),
    ('SUPER X',                                                  'SLOT',        'ECASINO'),
    ('SWEET BONANZA',                                            'SLOT',        'ECASINO'),
    ('SWEET BONANZA 1000',                                       'SLOT',        'ECASINO'),
    ('SWEET BONANZA SUPER SCATTER',                              'SLOT',        'ECASINO'),
    ('SWEET BONANZA XMAS',                                       'SLOT',        'ECASINO'),
    ('SWEET KINGDOM',                                            'SLOT',        'ECASINO'),
    ('SWEET POWERNUDGE',                                         'SLOT',        'ECASINO'),
    ('SWORD OF ARES',                                            'SLOT',        'ECASINO'),
    ('TEMUJIN TREASURES',                                        'SLOT',        'ECASINO'),
    ('THE ALTER EGO',                                            'SLOT',        'ECASINO'),
    ('THE BIG DAWGS',                                            'SLOT',        'ECASINO'),
    ('THE DOG HOUSE',                                            'SLOT',        'ECASINO'),
    ('THE DOG HOUSE - DOG OR ALIVE',                             'SLOT',        'ECASINO'),
    ('THE DOG HOUSE - MUTTLEY CREW',                             'SLOT',        'ECASINO'),
    ('THE DOG HOUSE MEGAWAYS',                                   'SLOT',        'ECASINO'),
    ('THE DOG HOUSE MULTIHOLD',                                  'SLOT',        'ECASINO'),
    ('THE DRAGON TIGER',                                         'SLOT',        'ECASINO'),
    ('THE GREAT CHICKEN ESCAPE',                                 'SLOT',        'ECASINO'),
    ('THE GREAT STICK-UP',                                       'SLOT',        'ECASINO'),
    ('THE HAND OF MIDAS',                                        'SLOT',        'ECASINO'),
    ('THE KNIGHT KING',                                          'SLOT',        'ECASINO'),
    ('THE MAGIC CAULDRON - ENCHANTED BREW',                      'SLOT',        'ECASINO'),
    ('THE MONEY MEN MEGAWAYS',                                   'SLOT',        'ECASINO'),
    ('THE RED QUEEN',                                            'SLOT',        'ECASINO'),
    ('THE ULTIMATE 5',                                           'SLOT',        'ECASINO'),
    ('THE WILD GANG',                                            'SLOT',        'ECASINO'),
    ('THE WILD MACHINE',                                         'SLOT',        'ECASINO'),
    ('THREE STAR FORTUNE',                                       'SLOT',        'ECASINO'),
    ('TIC TAC TAKE',                                             'SLOT',        'ECASINO'),
    ('TIMBER STACKS',                                            'SLOT',        'ECASINO'),
    ('TOWERING FORTUNES',                                        'SLOT',        'ECASINO'),
    ('TREASURE HORSE',                                           'SLOT',        'ECASINO'),
    ('TREASURE WILD',                                            'SLOT',        'ECASINO'),
    ('TREE OF RICHES',                                           'SLOT',        'ECASINO'),
    ('TREES OF TREASURE',                                        'SLOT',        'ECASINO'),
    ('TRIPLE DRAGONS',                                           'SLOT',        'ECASINO'),
    ('TROPICAL TIKI',                                            'SLOT',        'ECASINO'),
    ("TUNDRA'S FORTUNE",                                         'SLOT',        'ECASINO'),
    ('TWILIGHT PRINCESS',                                        'SLOT',        'ECASINO'),
    ('ULTRA BURN',                                               'SLOT',        'ECASINO'),
    ('ULTRA HOLD AND SPIN',                                      'SLOT',        'ECASINO'),
    ('VAMPIRES VS WOLVES',                                       'SLOT',        'ECASINO'),
    ('VAMPY PARTY',                                              'SLOT',        'ECASINO'),
    ('VEGAS MAGIC',                                              'SLOT',        'ECASINO'),
    ('VEGAS NIGHTS',                                             'SLOT',        'ECASINO'),
    ('VIKING FORGE',                                             'SLOT',        'ECASINO'),
    ('VOODOO MAGIC',                                             'SLOT',        'ECASINO'),
    ("WHEEL O'GOLD",                                             'SLOT',        'ECASINO'),
    ('WILD BEACH PARTY',                                         'SLOT',        'ECASINO'),
    ('WILD BISON CHARGE',                                        'SLOT',        'ECASINO'),
    ('WILD BOOSTER',                                             'SLOT',        'ECASINO'),
    ('WILD CELEBRITY BUS MEGAWAYS',                              'SLOT',        'ECASINO'),
    ('WILD DEPTHS',                                              'SLOT',        'ECASINO'),
    ('WILD HOP & DROP',                                          'SLOT',        'ECASINO'),
    ('WILD PIXIES',                                              'SLOT',        'ECASINO'),
    ('WILD SPELLS',                                              'SLOT',        'ECASINO'),
    ('WILD WALKER',                                              'SLOT',        'ECASINO'),
    ('WILD WEST DUELS',                                          'SLOT',        'ECASINO'),
    ('WILD WEST GOLD',                                           'SLOT',        'ECASINO'),
    ('WILD WEST GOLD MEGAWAYS',                                  'SLOT',        'ECASINO'),
    ('WILD WILD BANANAS',                                        'SLOT',        'ECASINO'),
    ('WILD WILD RICHES',                                         'SLOT',        'ECASINO'),
    ('WILD WILD RICHES MEGAWAYS',                                'SLOT',        'ECASINO'),
    ('WILDIES',                                                  'SLOT',        'ECASINO'),
    ('WISDOM OF ATHENA',                                         'SLOT',        'ECASINO'),
    ('WISDOM OF ATHENA 1000',                                    'SLOT',        'ECASINO'),
    ('WOLF GOLD',                                                'SLOT',        'ECASINO'),
    ('YEAR OF THE DRAGON KING',                                  'SLOT',        'ECASINO'),
    ('YETI QUEST',                                               'SLOT',        'ECASINO'),
    ('YUM YUM POWERWAYS',                                        'SLOT',        'ECASINO'),
    ('ZEUS VS HADES - GODS OF WAR',                              'SLOT',        'ECASINO'),
    ('ZOMBIE CARNIVAL',                                          'SLOT',        'ECASINO'),
]

CONFIDENCE_THRESHOLD = 0.80
AMBIGUOUS_DELTA      = 0.05


def normalize(s: str) -> str:
    s = s.upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fuzzy_score(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def best_matches(db_name: str):
    scores = [
        (fuzzy_score(db_name, pdf_name), pdf_name, gt, go)
        for pdf_name, gt, go in PDF_GAMES
    ]
    scores.sort(key=lambda x: -x[0])
    return scores


def escape_sql(s: str) -> str:
    return s.replace("'", "''")


def normalized_name(s: str) -> str:
    s = re.sub(r"[^A-Z0-9]", "_", s.upper())
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def main():
    print("Connecting to DB …")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT code, name
        FROM slot_game_setting_i18n
        WHERE provider = %s
          AND language = 2
        GROUP BY code
        ORDER BY code
    """, (PROVIDER,))
    db_rows = cursor.fetchall()
    cursor.close()
    conn.close()
    print(f"Fetched {len(db_rows)} games from DB\n")

    matched   = []
    ambiguous = []
    unmatched = []

    for code, db_name in db_rows:
        tops = best_matches(db_name)
        top1 = tops[0]
        top2 = tops[1]

        if top1[0] >= CONFIDENCE_THRESHOLD:
            if top1[0] - top2[0] < AMBIGUOUS_DELTA and top2[0] >= CONFIDENCE_THRESHOLD:
                close_candidates = [(s, n, gt, go) for s, n, gt, go in tops if s >= CONFIDENCE_THRESHOLD]
                types = set((gt, go) for _, _, gt, go in close_candidates)
                if len(types) == 1:
                    matched.append((code, db_name, top1[1], top1[2], top1[3], top1[0]))
                else:
                    ambiguous.append((code, db_name, tops[:3]))
            else:
                matched.append((code, db_name, top1[1], top1[2], top1[3], top1[0]))
        else:
            unmatched.append((code, db_name, top1[0], top1[1]))

    # ── 輸出 SQL ─────────────────────────────────────────────────
    out_lines = []

    out_lines.append("-- ============================================================")
    out_lines.append(f"-- PP_SLOT (provider={PROVIDER}) megaxcess_game_type_mapping")
    out_lines.append(f"-- MATCHED ({len(matched)} 筆)  信心度 >= {CONFIDENCE_THRESHOLD}")
    out_lines.append("-- ============================================================")
    out_lines.append(
        "INSERT INTO tiger_thirdparty.megaxcess_game_type_mapping\n"
        "    (provider, game_code, game_name, normalized_name, game_type, game_offering)\nVALUES"
    )
    value_rows = []
    for code, db_name, pdf_name, game_type, game_offering, score in matched:
        norm = normalized_name(db_name)
        value_rows.append(
            f"    -- DB: \"{db_name}\"  PDF: \"{pdf_name}\"  score={score:.2f}\n"
            f"    ({PROVIDER}, '{escape_sql(str(code))}', '{escape_sql(db_name)}', "
            f"'{norm}', '{game_type}', '{game_offering}')"
        )
    out_lines.append(",\n".join(value_rows))
    out_lines.append(
        "ON DUPLICATE KEY UPDATE\n"
        "    game_name       = VALUES(game_name),\n"
        "    normalized_name = VALUES(normalized_name),\n"
        "    game_type       = VALUES(game_type),\n"
        "    game_offering   = VALUES(game_offering);\n"
    )

    out_lines.append("\n-- ============================================================")
    out_lines.append(f"-- AMBIGUOUS ({len(ambiguous)} 筆)  需人工確認")
    out_lines.append("-- ============================================================")
    for code, db_name, tops in ambiguous:
        out_lines.append(f"-- code={code}  DB name: \"{db_name}\"")
        for sc, pn, gt, go in tops:
            out_lines.append(f"--   score={sc:.2f}  PDF: \"{pn}\"  type={gt}  offering={go}")
        out_lines.append(
            f"-- ({PROVIDER}, '{escape_sql(str(code))}', '{escape_sql(db_name)}', "
            f"'???', '???', '???')  -- TODO: 請手動決定"
        )
        out_lines.append("")

    out_lines.append("\n-- ============================================================")
    out_lines.append(f"-- UNMATCHED ({len(unmatched)} 筆)  無對應 PDF 遊戲 (score < {CONFIDENCE_THRESHOLD})")
    out_lines.append("-- ============================================================")
    for code, db_name, top_score, top_pdf in unmatched:
        out_lines.append(
            f"-- code={code}  DB: \"{db_name}\"  "
            f"best_match=\"{top_pdf}\" score={top_score:.2f}"
        )

    output_sql = "\n".join(out_lines)

    out_path = r"C:\Users\user\OneDrive\桌面\testpage\pp_mapping_output.sql"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output_sql)

    print(f"Done.")
    print(f"  MATCHED   : {len(matched)}")
    print(f"  AMBIGUOUS : {len(ambiguous)}")
    print(f"  UNMATCHED : {len(unmatched)}")
    print(f"  Output    : {out_path}")


if __name__ == "__main__":
    main()
