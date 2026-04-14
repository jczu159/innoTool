"""
JDB megaxcess_game_type_mapping 生成器 (JDB_SLOT, provider=18)
- 從 slot_game_setting_i18n 撈出 provider=18 的所有遊戲 (code 格式: 0_XXXX)
- 對每一筆做模糊比對 PDF 名稱
- 信心度高 (>= 0.80) 且唯一  → 輸出 INSERT/UPDATE SQL
- 多個候選分數接近 (差 < 0.05) → 若 game_type+offering 一致則自動取最高分，否則 AMBIGUOUS
- 完全比對不到                 → 輸出到 UNMATCHED 區塊

JDB PDF: List of EGLD-approved Electronic Games as of November 20, 2025
全部 105 款都是 eCASINO GAMES:
  SLOT: 75 款 (14xxx / 8xxx / 15xxx / 6xxx game IDs)
  ARCADE-TYPE: 18 款 (7xxx / 9xxx game IDs)
  TABLE: 8 款 (9xxx / 18xxx game IDs)

注意: ARCADE-TYPE 和 TABLE 的遊戲不在 slot_game_setting_i18n，
      那些由 JDBFishOrderPO 處理 (provider=24)，之後另外處理。
      本腳本只處理 SLOT 遊戲 (provider=18)。
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

PROVIDER = 18  # JDB_SLOT

# ── PDF 完整清單 (game_name, game_type, game_offering) ────────────
# 只列 SLOT 類型 (game_type=SLOT)，其餘 ARCADE-TYPE/TABLE 由 provider=24 另外處理
PDF_GAMES = [
    # eCASINO GAMES - SLOT
    ('BANANA SAGA',                     'SLOT', 'ECASINO'),
    ('BEAUTY AND THE KINGDOM',          'SLOT', 'ECASINO'),
    ('BIG THREE DRAGONS',               'SLOT', 'ECASINO'),
    ('BILLIONAIRE',                     'SLOT', 'ECASINO'),
    ('BING BING BONANZA COMBO',         'SLOT', 'ECASINO'),
    ('BIRDS PARTY',                     'SLOT', 'ECASINO'),
    ('BLOSSOM OF WEALTH',               'SLOT', 'ECASINO'),
    ('BOOK OF MYSTERY',                 'SLOT', 'ECASINO'),
    ('BULL TREASURE',                   'SLOT', 'ECASINO'),
    ('CAISHEN COMING',                  'SLOT', 'ECASINO'),
    ('COOCOO FARM',                     'SLOT', 'ECASINO'),
    ('DOUBLE WILDS',                    'SLOT', 'ECASINO'),
    ('DRAGON',                          'SLOT', 'ECASINO'),
    ('DRAGON SOAR - HYPER WILD',        'SLOT', 'ECASINO'),
    ('DRAGON WARRIOR',                  'SLOT', 'ECASINO'),
    ('DRAGONS GATE',                    'SLOT', 'ECASINO'),
    ('DRAGONS WORLD',                   'SLOT', 'ECASINO'),
    ('ELEMENTAL LINK FIRE',             'SLOT', 'ECASINO'),
    ('ELEMENTAL LINK WATER',            'SLOT', 'ECASINO'),
    ("FISHIN' FEVER X-HUGE",            'SLOT', 'ECASINO'),
    ('FLIRTING SCHOLAR TANG',           'SLOT', 'ECASINO'),
    ('FORMOSA BEAR',                    'SLOT', 'ECASINO'),
    ('FORTUNE HORSE',                   'SLOT', 'ECASINO'),
    ('FORTUNE JEWEL',                   'SLOT', 'ECASINO'),
    ('FORTUNE NEKO',                    'SLOT', 'ECASINO'),
    ('FORTUNE TREASURE',                'SLOT', 'ECASINO'),
    ('FOUR TREASURES',                  'SLOT', 'ECASINO'),
    ('FRUITY BONANZA',                  'SLOT', 'ECASINO'),
    ('FRUITY BONANZA COMBO',            'SLOT', 'ECASINO'),
    ('FUNKY KING KONG',                 'SLOT', 'ECASINO'),
    ('GLAMOROUS GIRL',                  'SLOT', 'ECASINO'),
    ('GOLAIFU',                         'SLOT', 'ECASINO'),
    ('GOLDEN DISCO',                    'SLOT', 'ECASINO'),
    ('KINGSMAN',                        'SLOT', 'ECASINO'),
    ('KOI TRIO',                        'SLOT', 'ECASINO'),
    ('KONG',                            'SLOT', 'ECASINO'),
    ('LANTERN WEALTH',                  'SLOT', 'ECASINO'),
    ('LEGENDARY 5',                     'SLOT', 'ECASINO'),
    ('LUCKY DIAMOND',                   'SLOT', 'ECASINO'),
    ('LUCKY DRAGONS',                   'SLOT', 'ECASINO'),
    ('LUCKY ELEPHANT X-HUGE',           'SLOT', 'ECASINO'),
    ('LUCKY SEVEN',                     'SLOT', 'ECASINO'),
    ('MAGIC ACE',                       'SLOT', 'ECASINO'),
    ('MAGIC ACE WILD LOCK',             'SLOT', 'ECASINO'),
    ('MAHJONG',                         'SLOT', 'ECASINO'),
    ('MARVELOUS IV',                    'SLOT', 'ECASINO'),
    ('MAYA GOLD CRAZY',                 'SLOT', 'ECASINO'),
    ('MINER BABE',                      'SLOT', 'ECASINO'),
    ('MJOLNIR',                         'SLOT', 'ECASINO'),
    ('MONEYBAGS MAN',                   'SLOT', 'ECASINO'),
    ('MONEYBAGS MAN 2',                 'SLOT', 'ECASINO'),
    ('MOONLIGHT TREASURE',              'SLOT', 'ECASINO'),
    ('NAPOLEON',                        'SLOT', 'ECASINO'),
    ('NEW YEAR',                        'SLOT', 'ECASINO'),
    ('OLYMPIAN TEMPLE',                 'SLOT', 'ECASINO'),
    ('OLYMPIG',                         'SLOT', 'ECASINO'),
    ('OPEN SESAME',                     'SLOT', 'ECASINO'),
    ('OPEN SESAME II',                  'SLOT', 'ECASINO'),
    ('OPEN SESAME MEGA',                'SLOT', 'ECASINO'),
    ('ORIENT ANIMALS',                  'SLOT', 'ECASINO'),
    ('PIGGY BANK',                      'SLOT', 'ECASINO'),
    ('POP POP CANDY',                   'SLOT', 'ECASINO'),
    ('POP POP CANDY 1000',              'SLOT', 'ECASINO'),
    ('PROSPERITY TIGER',                'SLOT', 'ECASINO'),
    ('RAGNAROK : THOR VS LOKI',         'SLOT', 'ECASINO'),
    ('ROOSTER IN LOVE',                 'SLOT', 'ECASINO'),
    ('SPINDRIFT',                       'SLOT', 'ECASINO'),
    ('SPINDRIFT 2',                     'SLOT', 'ECASINO'),
    ('SUPER NIUBI',                     'SLOT', 'ECASINO'),
    ('SUPER NIUBI DELUXE',              'SLOT', 'ECASINO'),
    ('THE LLAMA ADVENTURE',             'SLOT', 'ECASINO'),
    ('TREASURE BOWL',                   'SLOT', 'ECASINO'),
    ('TRIPLE KING KONG',                'SLOT', 'ECASINO'),
    ('TRUMP CARD',                      'SLOT', 'ECASINO'),
    ('WINNING MASK',                    'SLOT', 'ECASINO'),
    ('WINNING MASK II',                 'SLOT', 'ECASINO'),
    ('WONDER ELEPHANT',                 'SLOT', 'ECASINO'),
    ('WU KONG',                         'SLOT', 'ECASINO'),
    ('XIYANGYANG',                      'SLOT', 'ECASINO'),
    # eCASINO GAMES - ARCADE-TYPE (9_XXXX 格式，DB provider=18 裡有)
    ('CAISHEN PARTY',                   'ARCADE-TYPE', 'ECASINO'),
    ('DICE',                            'ARCADE-TYPE', 'ECASINO'),
    ('FIREWORK BURST',                  'ARCADE-TYPE', 'ECASINO'),
    ('GALAXY BURST',                    'ARCADE-TYPE', 'ECASINO'),
    ('GOAL',                            'ARCADE-TYPE', 'ECASINO'),
    ('MINES',                           'ARCADE-TYPE', 'ECASINO'),
    ('MINES 2',                         'ARCADE-TYPE', 'ECASINO'),
    ('PLINKO',                          'ARCADE-TYPE', 'ECASINO'),
    # eCASINO GAMES - TABLE (9_XXXX 格式，DB provider=18 裡有)
    ('HILO',                            'TABLE', 'ECASINO'),
    ('LUCKY COLOR GAME',                'TABLE', 'ECASINO'),
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
    out_lines.append(f"-- JDB (provider={PROVIDER}) megaxcess_game_type_mapping")
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

    out_path = r"C:\Users\user\OneDrive\桌面\testpage\jdb_mapping_output.sql"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output_sql)

    print(f"Done.")
    print(f"  MATCHED   : {len(matched)}")
    print(f"  AMBIGUOUS : {len(ambiguous)}")
    print(f"  UNMATCHED : {len(unmatched)}")
    print(f"  Output    : {out_path}")


if __name__ == "__main__":
    main()
