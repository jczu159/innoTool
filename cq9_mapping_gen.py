"""
CQ9 megaxcess_game_type_mapping 生成器
- 從 slot_game_setting_i18n 撈出 provider=15 的所有遊戲
- 對每一筆做模糊比對 PDF 名稱
- 信心度高 (>= 0.80) 且唯一  → 輸出 INSERT/UPDATE SQL
- 多個候選分數接近 (差 < 0.05) → 輸出到 AMBIGUOUS 區塊
- 完全比對不到                 → 輸出到 UNMATCHED 區塊

CQ9 PDF: List of EGLD-approved Electronic Games as of February 19, 2026
全部 195 款都是 eCASINO GAMES (SLOT 189 款 + ARCADE-TYPE 6 款)
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

PROVIDER = 15  # CQ9_SLOT

# ── PDF 完整清單 (game_name, game_type, game_offering) ────────────
# 資料來源: CQ9 EGLD-approved list as of Feb 19, 2026
PDF_GAMES = [
    # eCASINO GAMES - SLOT
    ('777',                             'SLOT',        'ECASINO'),
    ('888',                             'SLOT',        'ECASINO'),
    ('5 BOXING',                        'SLOT',        'ECASINO'),
    ('5 GOD BEASTS',                    'SLOT',        'ECASINO'),
    ('6 TOROS',                         'SLOT',        'ECASINO'),
    ('888 CAI SHEN',                    'SLOT',        'ECASINO'),
    ('ACROBATICS',                      'SLOT',        'ECASINO'),
    ("ALADDIN'S LAMP",                  'SLOT',        'ECASINO'),
    ('ALL STAR TEAM',                   'SLOT',        'ECASINO'),
    ('ALL WILDS',                       'SLOT',        'ECASINO'),
    ('APOLLO',                          'SLOT',        'ECASINO'),
    ('APSARAS',                         'SLOT',        'ECASINO'),
    ('BASEBALL FEVER',                  'SLOT',        'ECASINO'),
    ('BIG WOLF',                        'SLOT',        'ECASINO'),
    ('BLACK WUKONG',                    'SLOT',        'ECASINO'),
    ('BURNING XI-YOU',                  'SLOT',        'ECASINO'),
    ('CHAMELEON',                       'SLOT',        'ECASINO'),
    ('CHICAGO II',                      'SLOT',        'ECASINO'),
    ('CHICKY PARM PARM',                'SLOT',        'ECASINO'),
    ('COIN SPINNER',                    'SLOT',        'ECASINO'),
    ('CRAZY CRAZY',                     'SLOT',        'ECASINO'),
    ('CRAZY CRAZY 2',                   'SLOT',        'ECASINO'),
    ('CRAZY CRAZY 3',                   'SLOT',        'ECASINO'),
    ('CRAZY NUOZHA',                    'SLOT',        'ECASINO'),
    ('CRICKET FEVER',                   'SLOT',        'ECASINO'),
    ('DA HONG ZHONG',                   'SLOT',        'ECASINO'),
    ('DETECTIVE DEE',                   'SLOT',        'ECASINO'),
    ('DETECTIVE DEE 2',                 'SLOT',        'ECASINO'),
    ('DIAMOND TREASURE',                'SLOT',        'ECASINO'),
    ('DISCO NIGHT',                     'SLOT',        'ECASINO'),
    ('DISCO NIGHT M',                   'SLOT',        'ECASINO'),
    ('DISCO PIGGY',                     'SLOT',        'ECASINO'),
    ('DOLLAR BOMB',                     'SLOT',        'ECASINO'),
    ('DOUBLE FLY',                      'SLOT',        'ECASINO'),
    ('DRAGON BALL',                     'SLOT',        'ECASINO'),
    ('DRAGON HEART',                    'SLOT',        'ECASINO'),
    ('DRAGON KOI',                      'SLOT',        'ECASINO'),
    ("DRAGON'S TREASURE",               'SLOT',        'ECASINO'),
    ('ECSTATIC CIRCUS',                 'SLOT',        'ECASINO'),
    ('FA CAI FU WA',                    'SLOT',        'ECASINO'),
    ('FA CAI SHEN',                     'SLOT',        'ECASINO'),
    ('FA CAI SHEN 2',                   'SLOT',        'ECASINO'),
    ('FA CAI SHEN M',                   'SLOT',        'ECASINO'),
    ('FIRE CHIBI',                      'SLOT',        'ECASINO'),
    ('FIRE CHIBI 2',                    'SLOT',        'ECASINO'),
    ('FIRE CHIBI M',                    'SLOT',        'ECASINO'),
    ('FIRE QUEEN',                      'SLOT',        'ECASINO'),
    ('FIRE QUEEN 2',                    'SLOT',        'ECASINO'),
    ('FIRE777',                         'SLOT',        'ECASINO'),
    ('FLOATING MARKET',                 'SLOT',        'ECASINO'),
    ('FLOWER FORTUNES',                 'SLOT',        'ECASINO'),
    ('FLY OUT',                         'SLOT',        'ECASINO'),
    ('FLYING CAI SHEN',                 'SLOT',        'ECASINO'),
    ('FOOTBALL BABY',                   'SLOT',        'ECASINO'),
    ('FOOTBALL BOOTS',                  'SLOT',        'ECASINO'),
    ('FOOTBALL FEVER',                  'SLOT',        'ECASINO'),
    ('FOOTBALL FEVER M',                'SLOT',        'ECASINO'),
    ('FORTUNE DRAGON',                  'SLOT',        'ECASINO'),
    ('FORTUNE TOTEM',                   'SLOT',        'ECASINO'),
    ('FRUIT KING',                      'SLOT',        'ECASINO'),
    ('FRUIT KING II',                   'SLOT',        'ECASINO'),
    ('FRUITY CARNIVAL',                 'SLOT',        'ECASINO'),
    ('FUNNY ALPACA',                    'SLOT',        'ECASINO'),
    ('GANESHA JR.',                     'SLOT',        'ECASINO'),
    ('GO FISHING',                      'SLOT',        'ECASINO'),
    ('GOD OF CHESS',                    'SLOT',        'ECASINO'),
    ('GOD OF WAR',                      'SLOT',        'ECASINO'),
    ('GOD OF WAR M',                    'SLOT',        'ECASINO'),
    ('GOLD STEALER',                    'SLOT',        'ECASINO'),
    ('GOLDEN EGGS',                     'SLOT',        'ECASINO'),
    ('GOOD FORTUNE',                    'SLOT',        'ECASINO'),
    ('GOOD FORTUNE M',                  'SLOT',        'ECASINO'),
    ('GOPHERS WAR',                     'SLOT',        'ECASINO'),
    ('GREAT LION',                      'SLOT',        'ECASINO'),
    ('GREEK GODS',                      'SLOT',        'ECASINO'),
    ('GU GU GU',                        'SLOT',        'ECASINO'),
    ('GU GU GU 2',                      'SLOT',        'ECASINO'),
    ('GU GU GU 2 M',                    'SLOT',        'ECASINO'),
    ('GU GU GU 3',                      'SLOT',        'ECASINO'),
    ('GU GU GU M',                      'SLOT',        'ECASINO'),
    ('HAPPY RICH YEAR',                 'SLOT',        'ECASINO'),
    ('HEPHAESTUS',                      'SLOT',        'ECASINO'),
    ('HERCULES',                        'SLOT',        'ECASINO'),
    ('HERO OF THE 3 KINGDOMS: CAO CAO', 'SLOT',        'ECASINO'),
    ('HONG KONG FLAVOR',                'SLOT',        'ECASINO'),
    ('HOT DJ',                          'SLOT',        'ECASINO'),
    ('HOT PINATAS',                     'SLOT',        'ECASINO'),
    ('HOT SPIN',                        'SLOT',        'ECASINO'),
    ('INVINCIBLE ELEPHANT',             'SLOT',        'ECASINO'),
    ('JEWEL LUXURY',                    'SLOT',        'ECASINO'),
    ('JUMP HIGH',                       'SLOT',        'ECASINO'),
    ('JUMP HIGH 2',                     'SLOT',        'ECASINO'),
    ('JUMP HIGHER',                     'SLOT',        'ECASINO'),
    ('JUMP HIGHER MOBILE',              'SLOT',        'ECASINO'),
    ('JUMPING MOBILE',                  'SLOT',        'ECASINO'),
    ('KING KONG SHAKE',                 'SLOT',        'ECASINO'),
    ('KING OF ATLANTIS',                'SLOT',        'ECASINO'),
    ('KRONOS',                          'SLOT',        'ECASINO'),
    ('LONELY PLANET',                   'SLOT',        'ECASINO'),
    ('LORD GANESHA',                    'SLOT',        'ECASINO'),
    ('LOY KRATHONG',                    'SLOT',        'ECASINO'),
    ('LUCKY BATS',                      'SLOT',        'ECASINO'),
    ('LUCKY BATS M',                    'SLOT',        'ECASINO'),
    ('LUCKY BOXES',                     'SLOT',        'ECASINO'),
    ('LUCKY TIGERS',                    'SLOT',        'ECASINO'),
    ('MAFIA',                           'SLOT',        'ECASINO'),
    ('MAGIC WORLD',                     'SLOT',        'ECASINO'),
    ('MAHJONG WILDS',                   'SLOT',        'ECASINO'),
    ('MAHJONG WILDS 2',                 'SLOT',        'ECASINO'),
    ('MEOW',                            'SLOT',        'ECASINO'),
    ('MIRROR MIRROR',                   'SLOT',        'ECASINO'),
    ('MONEY NARRA',                     'SLOT',        'ECASINO'),
    ('MONEY TREE',                      'SLOT',        'ECASINO'),
    ('MONKEY OFFICE LEGEND',            'SLOT',        'ECASINO'),
    ('MONSTER HUNTER',                  'SLOT',        'ECASINO'),
    ("MOVE N' JUMP",                    'SLOT',        'ECASINO'),
    ('MR. MISER',                       'SLOT',        'ECASINO'),
    ('MR. RICH',                        'SLOT',        'ECASINO'),
    ('MUAY THAI',                       'SLOT',        'ECASINO'),
    ('MYEONG-RYANG',                    'SLOT',        'ECASINO'),
    ('NE ZHA ADVENT',                   'SLOT',        'ECASINO'),
    ('NIGHT CITY',                      'SLOT',        'ECASINO'),
    ('NINJA RACCOON',                   'SLOT',        'ECASINO'),
    ('OO GA CHA KA',                    'SLOT',        'ECASINO'),
    ('ORIENTAL BEAUTY',                 'SLOT',        'ECASINO'),
    ('PARTY ISLAND',                    'SLOT',        'ECASINO'),
    ("PHARAOH'S GOLD",                  'SLOT',        'ECASINO'),
    ('POSEIDON',                        'SLOT',        'ECASINO'),
    ('PUB TYCOON',                      'SLOT',        'ECASINO'),
    ('PYRAMID RAIDER',                  'SLOT',        'ECASINO'),
    ('RAVE HIGH',                       'SLOT',        'ECASINO'),
    ('RAVE JUMP',                       'SLOT',        'ECASINO'),
    ('RAVE JUMP 2',                     'SLOT',        'ECASINO'),
    ('RAVE JUMP 2 M',                   'SLOT',        'ECASINO'),
    ('RAVE JUMP MOBILE',                'SLOT',        'ECASINO'),
    ('RED PHOENIX',                     'SLOT',        'ECASINO'),
    ('RUNNING ANIMALS',                 'SLOT',        'ECASINO'),
    ('RUNNING TORO',                    'SLOT',        'ECASINO'),
    ('SAKURA LEGEND',                   'SLOT',        'ECASINO'),
    ('SHERLOCK HOLMES',                 'SLOT',        'ECASINO'),
    ('SHOU-XIN',                        'SLOT',        'ECASINO'),
    ('SIX CANDY',                       'SLOT',        'ECASINO'),
    ('SIX GACHA',                       'SLOT',        'ECASINO'),
    ('SKRSKR',                          'SLOT',        'ECASINO'),
    ('SKY LANTERNS',                    'SLOT',        'ECASINO'),
    ('SNOW QUEEN',                      'SLOT',        'ECASINO'),
    ('SO SWEET',                        'SLOT',        'ECASINO'),
    ('SONGKRAN FESTIVAL',               'SLOT',        'ECASINO'),
    ('STRIKER WILD',                    'SLOT',        'ECASINO'),
    ('SUMMER MOOD',                     'SLOT',        'ECASINO'),
    ('SUNG WUKONG',                     'SLOT',        'ECASINO'),
    ('SUPER 5',                         'SLOT',        'ECASINO'),
    ('SUPER POWER BANK',                'SLOT',        'ECASINO'),
    ('SWEET POP',                       'SLOT',        'ECASINO'),
    ('THE BEAST WAR',                   'SLOT',        'ECASINO'),
    ('THE CHICKEN HOUSE',               'SLOT',        'ECASINO'),
    ('THE CUPIDS',                      'SLOT',        'ECASINO'),
    ('THOR',                            'SLOT',        'ECASINO'),
    ('THOR 2',                          'SLOT',        'ECASINO'),
    ('TOP ACE',                         'SLOT',        'ECASINO'),
    ('TREASURE BOWL',                   'SLOT',        'ECASINO'),
    ('TREASURE BOWL JP',                'SLOT',        'ECASINO'),
    ('TREASURE HOUSE',                  'SLOT',        'ECASINO'),
    ('TREASURE ISLAND',                 'SLOT',        'ECASINO'),
    ('TREASURE PIRATE',                 'SLOT',        'ECASINO'),
    ('UPROAR IN HEAVEN',                'SLOT',        'ECASINO'),
    ('VAMPIRE KISS',                    'SLOT',        'ECASINO'),
    ('WANBAO DINO',                     'SLOT',        'ECASINO'),
    ('WATAH MASTER',                    'SLOT',        'ECASINO'),
    ('WATAH MASTER 2',                  'SLOT',        'ECASINO'),
    ('WATAH MASTER TURBO',              'SLOT',        'ECASINO'),
    ('WATER MARGIN',                    'SLOT',        'ECASINO'),
    ('WATER WORLD',                     'SLOT',        'ECASINO'),
    ('WHEEL MONEY',                     'SLOT',        'ECASINO'),
    ('WILD DISCO NIGHT',                'SLOT',        'ECASINO'),
    ('WILD TARZAN',                     'SLOT',        'ECASINO'),
    ('WING CHUN',                       'SLOT',        'ECASINO'),
    ('WOLF DISCO',                      'SLOT',        'ECASINO'),
    ('WOLF MOON',                       'SLOT',        'ECASINO'),
    ('WON WON WON',                     'SLOT',        'ECASINO'),
    ('WONDERLAND',                      'SLOT',        'ECASINO'),
    ('WORLD CUP RUSSIA 2018',           'SLOT',        'ECASINO'),
    ('WUKONG & PEACHES',                'SLOT',        'ECASINO'),
    ('XMAS',                            'SLOT',        'ECASINO'),
    ('YUAN BAO',                        'SLOT',        'ECASINO'),
    ('ZEUS',                            'SLOT',        'ECASINO'),
    ('ZEUS M',                          'SLOT',        'ECASINO'),
    ('ZHONG KUI',                       'SLOT',        'ECASINO'),
    ('ZUMA WILD',                       'SLOT',        'ECASINO'),
    # eCASINO GAMES - ARCADE-TYPE
    ('HERO FISHING',                    'ARCADE-TYPE', 'ECASINO'),
    ('K.O. ISLAND',                     'ARCADE-TYPE', 'ECASINO'),
    ('LUCKY FISHING',                   'ARCADE-TYPE', 'ECASINO'),
    ("MUMMY'S TREASURE",                'ARCADE-TYPE', 'ECASINO'),
    ('ONESHOT FISHING',                 'ARCADE-TYPE', 'ECASINO'),
    ('PARADISE',                        'ARCADE-TYPE', 'ECASINO'),
]

CONFIDENCE_THRESHOLD = 0.80   # 視為確定比對
AMBIGUOUS_DELTA      = 0.05   # top1 與 top2 差距 < 此值 → 模糊


def normalize(s: str) -> str:
    """去除特殊字元、轉大寫、壓縮空白，用於模糊比對"""
    s = s.upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)   # 保留字母、數字、空白
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fuzzy_score(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def best_matches(db_name: str):
    """回傳 [(score, pdf_name, game_type, game_offering), ...] 依 score 降序"""
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

    matched   = []   # (code, db_name, pdf_name, game_type, game_offering, score)
    ambiguous = []   # (code, db_name, top_candidates)
    unmatched = []   # (code, db_name, top_score, top_pdf_name)

    for code, db_name in db_rows:
        tops = best_matches(db_name)
        top1 = tops[0]
        top2 = tops[1]

        if top1[0] >= CONFIDENCE_THRESHOLD:
            # 檢查是否模糊（top2 太接近 top1）
            if top1[0] - top2[0] < AMBIGUOUS_DELTA and top2[0] >= CONFIDENCE_THRESHOLD:
                # 若所有高分候選的 game_type + game_offering 完全一致，自動取最高分
                close_candidates = [(s, n, gt, go) for s, n, gt, go in tops if s >= CONFIDENCE_THRESHOLD]
                types = set((gt, go) for _, _, gt, go in close_candidates)
                if len(types) == 1:
                    # 全部相同，自動解決
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
    out_lines.append(f"-- CQ9 (provider={PROVIDER}) megaxcess_game_type_mapping")
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

    out_path = r"C:\Users\user\OneDrive\桌面\testpage\cq9_mapping_output.sql"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output_sql)

    print(f"Done.")
    print(f"  MATCHED   : {len(matched)}")
    print(f"  AMBIGUOUS : {len(ambiguous)}")
    print(f"  UNMATCHED : {len(unmatched)}")
    print(f"  Output    : {out_path}")


if __name__ == "__main__":
    main()
