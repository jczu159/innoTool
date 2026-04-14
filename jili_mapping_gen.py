"""
JILI megaxcess_game_type_mapping 生成器
- 從 slot_game_setting_i18n 撈出 provider=38 的所有遊戲
- 對每一筆做模糊比對 PDF 名稱
- 信心度高 (>= 0.80) 且唯一  → 輸出 INSERT/UPDATE SQL
- 多個候選分數接近 (差 < 0.05) → 輸出到 AMBIGUOUS 區塊
- 完全比對不到                 → 輸出到 UNMATCHED 區塊
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

# ── PDF 完整清單 (game_name, game_type, game_offering) ────────────
PDF_GAMES = [
    # eBINGO GAMES
    ('BINGO ADVENTURE',               'eBINGO',      'EBINGO'),
    ('BINGO CARNAVAL',                'eBINGO',      'EBINGO'),
    ('CALACA BINGO',                  'eBINGO',      'EBINGO'),
    ('CANDYLAND BINGO',               'eBINGO',      'EBINGO'),
    ('FORTUNE BINGO',                 'eBINGO',      'EBINGO'),
    ('GO GOAL BINGO',                 'eBINGO',      'EBINGO'),
    ('IRICH BINGO',                   'eBINGO',      'EBINGO'),
    ('JACKPOT BINGO',                 'eBINGO',      'EBINGO'),
    ('LUCKY BINGO',                   'eBINGO',      'EBINGO'),
    ('MAGIC LAMP BINGO',              'eBINGO',      'EBINGO'),
    ('PEARLS OF BINGO',               'eBINGO',      'EBINGO'),
    ('SUPER BINGO',                   'eBINGO',      'EBINGO'),
    ('WEST HUNTER BINGO',             'eBINGO',      'EBINGO'),
    # eCASINO - SLOT
    ('10 SPARKLING CROWN',            'SLOT',        'ECASINO'),
    ('3 CHARGE BUFFALO',              'SLOT',        'ECASINO'),
    ('3 COIN TREASURES',              'SLOT',        'ECASINO'),
    ('3 COIN TREASURES 2',            'SLOT',        'ECASINO'),
    ('3 COIN WILD HORSE',             'SLOT',        'ECASINO'),
    ('3 LUCKY LIONS',                 'SLOT',        'ECASINO'),
    ('3 LUCKY PIGGY',                 'SLOT',        'ECASINO'),
    ('3 POTS DRAGONS',                'SLOT',        'ECASINO'),
    ('AGENT ACE',                     'SLOT',        'ECASINO'),
    ('ALI BABA',                      'SLOT',        'ECASINO'),
    ('ARENA FIGHTER',                 'SLOT',        'ECASINO'),
    ('AZTEC PRIESTESS',               'SLOT',        'ECASINO'),
    ('BANGLA BEAUTY',                 'SLOT',        'ECASINO'),
    ('BAO BOON CHIN',                 'SLOT',        'ECASINO'),
    ('BIKINI LADY',                   'SLOT',        'ECASINO'),
    ('BONE FORTUNE',                  'SLOT',        'ECASINO'),
    ('BONUS HUNTER',                  'SLOT',        'ECASINO'),
    ('BOOK OF GOLD',                  'SLOT',        'ECASINO'),
    ('BOXING KING',                   'SLOT',        'ECASINO'),
    ('BUBBLE BEAUTY',                 'SLOT',        'ECASINO'),
    ('CANDY BABY',                    'SLOT',        'ECASINO'),
    ('CHARGE BUFFALO',                'SLOT',        'ECASINO'),
    ('CHARGE BUFFALO ASCENT',         'SLOT',        'ECASINO'),
    ('CHIN SHI HUANG',                'SLOT',        'ECASINO'),
    ('CIRCUS JOKER 4096',             'SLOT',        'ECASINO'),
    ('COIN TREE',                     'SLOT',        'ECASINO'),
    ('CRAZY 777',                     'SLOT',        'ECASINO'),
    ('CRAZY FAFAFA',                  'SLOT',        'ECASINO'),
    ('CRICKET KING 18',               'SLOT',        'ECASINO'),
    ('CRICKET SAH 75',                'SLOT',        'ECASINO'),
    ('DABANGGG',                      'SLOT',        'ECASINO'),
    ('DEVIL FIRE',                    'SLOT',        'ECASINO'),
    ('DEVIL FIRE 2',                  'SLOT',        'ECASINO'),
    ('DIAMOND PARTY',                 'SLOT',        'ECASINO'),
    ('DRAGON TREASURE',               'SLOT',        'ECASINO'),
    ("EGYPT'S GLOW",                  'SLOT',        'ECASINO'),
    ('ELF BINGO',                     'SLOT',        'ECASINO'),
    ('FA FA FA',                      'SLOT',        'ECASINO'),
    ('FENG SHEN',                     'SLOT',        'ECASINO'),
    ('FORTUNE COINS (LOCK AND RESPIN)','SLOT',        'ECASINO'),
    ('FORTUNE COINS 2 (HIT THE CASH)','SLOT',        'ECASINO'),
    ('FORTUNE GEMS',                  'SLOT',        'ECASINO'),
    ('FORTUNE GEMS 2',                'SLOT',        'ECASINO'),
    ('FORTUNE GEMS 3',                'SLOT',        'ECASINO'),
    ('FORTUNE GEMS 500',              'SLOT',        'ECASINO'),
    ('FORTUNE HOOK',                  'SLOT',        'ECASINO'),
    ('FORTUNE MONKEY',                'SLOT',        'ECASINO'),
    ('FORTUNE PIG',                   'SLOT',        'ECASINO'),
    ('FORTUNE TREE',                  'SLOT',        'ECASINO'),
    ('FRUITY WHEEL',                  'SLOT',        'ECASINO'),
    ('GOD OF MARTIAL',                'SLOT',        'ECASINO'),
    ('GOLD RUSH',                     'SLOT',        'ECASINO'),
    ('GOLDEN BANK',                   'SLOT',        'ECASINO'),
    ('GOLDEN BANK 2',                 'SLOT',        'ECASINO'),
    ('GOLDEN EMPIRE',                 'SLOT',        'ECASINO'),
    ('GOLDEN EMPIRE 2',               'SLOT',        'ECASINO'),
    ('GOLDEN JOKER',                  'SLOT',        'ECASINO'),
    ('GOLDEN QUEEN',                  'SLOT',        'ECASINO'),
    ('GOLDEN TEMPLE',                 'SLOT',        'ECASINO'),
    ('HAPPY TAXI',                    'SLOT',        'ECASINO'),
    ('HAWAII BEAUTY',                 'SLOT',        'ECASINO'),
    ('HOT CHILI',                     'SLOT',        'ECASINO'),
    ('HYPER BURST',                   'SLOT',        'ECASINO'),
    ('JACKPOT JOKER',                 'SLOT',        'ECASINO'),
    ('JILI CAISHEN',                  'SLOT',        'ECASINO'),
    ('JOURNEY WEST M',                'SLOT',        'ECASINO'),
    ('JUNGLE KING',                   'SLOT',        'ECASINO'),
    ('KING ARTHUR',                   'SLOT',        'ECASINO'),
    ('LEGACY OF EGYPT',               'SLOT',        'ECASINO'),
    ('LUCKY BALL',                    'SLOT',        'ECASINO'),
    ('LUCKY COMING',                  'SLOT',        'ECASINO'),
    ('LUCKY DOGGY',                   'SLOT',        'ECASINO'),
    ('LUCKY GOLD BRICKS',             'SLOT',        'ECASINO'),
    ('LUCKY JAGUAR',                  'SLOT',        'ECASINO'),
    ('MAGIC LAMP',                    'SLOT',        'ECASINO'),
    ('MASTER TIGER',                  'SLOT',        'ECASINO'),
    ('MAYAN EMPIRE',                  'SLOT',        'ECASINO'),
    ('MEDUSA',                        'SLOT',        'ECASINO'),
    ('MEGA ACE',                      'SLOT',        'ECASINO'),
    ('MONEY COMING',                  'SLOT',        'ECASINO'),
    ('MONEY COMING 2',                'SLOT',        'ECASINO'),
    ('MONEY COMING EXPAND BETS',      'SLOT',        'ECASINO'),
    ('MONEY POT',                     'SLOT',        'ECASINO'),
    ('NEKO FORTUNE',                  'SLOT',        'ECASINO'),
    ('NIGHT CITY',                    'SLOT',        'ECASINO'),
    ('NIGHTFALL HUNTING',             'SLOT',        'ECASINO'),
    ('PARTY NIGHT',                   'SLOT',        'ECASINO'),
    ('PARTY STAR',                    'SLOT',        'ECASINO'),
    ('PHARAOH TREASURE',              'SLOT',        'ECASINO'),
    ('PIRATE QUEEN',                  'SLOT',        'ECASINO'),
    ('PIRATE QUEEN 2',                'SLOT',        'ECASINO'),
    ('POSEIDON',                      'SLOT',        'ECASINO'),
    ('POTION WIZARD',                 'SLOT',        'ECASINO'),
    ('RAPID GEMS 777',                'SLOT',        'ECASINO'),
    ('ROMA X',                        'SLOT',        'ECASINO'),
    ('ROMA X DELUXE',                 'SLOT',        'ECASINO'),
    ('SAFARI MYSTERY',                'SLOT',        'ECASINO'),
    ('SAMBA',                         'SLOT',        'ECASINO'),
    ('SEVEN SEVEN SEVEN',             'SLOT',        'ECASINO'),
    ('SHANGHAI BEAUTY',               'SLOT',        'ECASINO'),
    ('SHOGUN',                        'SLOT',        'ECASINO'),
    ('SIN CITY',                      'SLOT',        'ECASINO'),
    ('SUPER ACE',                     'SLOT',        'ECASINO'),
    ('SUPER ACE 2',                   'SLOT',        'ECASINO'),
    ('SUPER ACE DELUXE',              'SLOT',        'ECASINO'),
    ('SUPER ACE JOKER',               'SLOT',        'ECASINO'),
    ('SUPER RICH',                    'SLOT',        'ECASINO'),
    ('SWEET LAND',                    'SLOT',        'ECASINO'),
    ('THE PIG HOUSE',                 'SLOT',        'ECASINO'),
    ('THOR X',                        'SLOT',        'ECASINO'),
    ('TREASURE QUEST',                'SLOT',        'ECASINO'),
    ('TRIAL OF PHOENIX',              'SLOT',        'ECASINO'),
    ('TWIN WINS',                     'SLOT',        'ECASINO'),
    ('WAR OF DRAGONS',                'SLOT',        'ECASINO'),
    ('WILD ACE',                      'SLOT',        'ECASINO'),
    ('WILD RACER',                    'SLOT',        'ECASINO'),
    ('WITCHES NIGHT',                 'SLOT',        'ECASINO'),
    ('WORLD CUP',                     'SLOT',        'ECASINO'),
    ('XIYANGYANG',                    'SLOT',        'ECASINO'),
    ('ZEUS',                          'SLOT',        'ECASINO'),
    # eCASINO - TABLE
    ('7 UP 7 DOWN (EXTRA PAY)',        'TABLE',       'ECASINO'),
    ('AK47',                          'TABLE',       'ECASINO'),
    ('ANDAR BAHAR',                   'TABLE',       'ECASINO'),
    ('BACCARAT',                      'TABLE',       'ECASINO'),
    ('BIG SMALL',                     'TABLE',       'ECASINO'),
    ('BLACKJACK',                     'TABLE',       'ECASINO'),
    ('BLACKJACK LUCKY LADIES',        'TABLE',       'ECASINO'),
    ('CALLBREAK',                     'TABLE',       'ECASINO'),
    ('CALLBREAK QUICK',               'TABLE',       'ECASINO'),
    ('CARIBBEAN STUD POKER',          'TABLE',       'ECASINO'),
    ('COLOR GAME',                    'TABLE',       'ECASINO'),
    ('COLOR GAME EXTREME',            'TABLE',       'ECASINO'),
    ('COLOR PREDICTION',              'TABLE',       'ECASINO'),
    ('CRICKET ROULETTE',              'TABLE',       'ECASINO'),
    ('CRICKET WAR',                   'TABLE',       'ECASINO'),
    ('DOMINO GO',                     'TABLE',       'ECASINO'),
    ('DRAGON & TIGER (EXTRA PAY)',     'TABLE',       'ECASINO'),
    ('EUROPEAN ROULETTE',             'TABLE',       'ECASINO'),
    ('FORTUNE ROULETTE',              'TABLE',       'ECASINO'),
    ('GOLDEN LAND',                   'TABLE',       'ECASINO'),
    ('GOLDEN TREASURE',               'TABLE',       'ECASINO'),
    ('HILO',                          'TABLE',       'ECASINO'),
    ('JHANDI MUNDA',                  'TABLE',       'ECASINO'),
    ('MINI FLUSH',                    'TABLE',       'ECASINO'),
    ('POKER KING',                    'TABLE',       'ECASINO'),
    ('POOL RUMMY',                    'TABLE',       'ECASINO'),
    ('PUSOY GO',                      'TABLE',       'ECASINO'),
    ('RUMMY',                         'TABLE',       'ECASINO'),
    ('SIC BO (EXTRA PAY)',            'TABLE',       'ECASINO'),
    ('SPEED BACCARAT',                'TABLE',       'ECASINO'),
    ('TEEN PATTI',                    'TABLE',       'ECASINO'),
    ('TEEN PATTI 20-20',              'TABLE',       'ECASINO'),
    ('TEEN PATTI JOKER',              'TABLE',       'ECASINO'),
    ('THAI HILO',                     'TABLE',       'ECASINO'),
    ('TONGITS GO',                    'TABLE',       'ECASINO'),
    ('ULTIMATE TEXAS HOLDEM',         'TABLE',       'ECASINO'),
    ('VIDEO POKER',                   'TABLE',       'ECASINO'),
    ('WHEEL',                         'TABLE',       'ECASINO'),
    ('WIN DROP',                      'TABLE',       'ECASINO'),
    # eCASINO - ARCADE-TYPE
    ('ALL STAR FISHING',              'ARCADE-TYPE', 'ECASINO'),
    ('BOMBING FISHING',               'ARCADE-TYPE', 'ECASINO'),
    ('BOOM LEGEND',                   'ARCADE-TYPE', 'ECASINO'),
    ('CRASH BONUS',                   'ARCADE-TYPE', 'ECASINO'),
    ('CRASH CRICKET',                 'ARCADE-TYPE', 'ECASINO'),
    ('CRASH GOAL',                    'ARCADE-TYPE', 'ECASINO'),
    ('CRASH TOUCHDOWN',               'ARCADE-TYPE', 'ECASINO'),
    ('CRAZY HUNTER',                  'ARCADE-TYPE', 'ECASINO'),
    ('CRAZY HUNTER 2',                'ARCADE-TYPE', 'ECASINO'),
    ('CRAZY PUSHER',                  'ARCADE-TYPE', 'ECASINO'),
    ('DINOSAUR TYCOON',               'ARCADE-TYPE', 'ECASINO'),
    ('DINOSAUR TYCOON II',            'ARCADE-TYPE', 'ECASINO'),
    ('DRAGON FORTUNE',                'ARCADE-TYPE', 'ECASINO'),
    ('FISH PRAWN CRAB',               'ARCADE-TYPE', 'ECASINO'),
    ('FORTUNE GEMS SCRATCH',          'ARCADE-TYPE', 'ECASINO'),
    ('FORTUNE KING JACKPOT',          'ARCADE-TYPE', 'ECASINO'),
    ('FORTUNE ZOMBIE',                'ARCADE-TYPE', 'ECASINO'),
    ('GO RUSH',                       'ARCADE-TYPE', 'ECASINO'),
    ('HAPPY FISHING',                 'ARCADE-TYPE', 'ECASINO'),
    ('JACKPOT FISHING',               'ARCADE-TYPE', 'ECASINO'),
    ('JOGO DO BICHO',                 'ARCADE-TYPE', 'ECASINO'),
    ('LIMBO',                         'ARCADE-TYPE', 'ECASINO'),
    ('LUDO QUICK',                    'ARCADE-TYPE', 'ECASINO'),
    ('MEGA FISHING',                  'ARCADE-TYPE', 'ECASINO'),
    ('MINES',                         'ARCADE-TYPE', 'ECASINO'),
    ('MINES GOLD',                    'ARCADE-TYPE', 'ECASINO'),
    ('MINES GRAND',                   'ARCADE-TYPE', 'ECASINO'),
    ('OCEAN KING JACKPOT',            'ARCADE-TYPE', 'ECASINO'),
    ('PAPPU',                         'ARCADE-TYPE', 'ECASINO'),
    ('PENALTY KICKS',                 'ARCADE-TYPE', 'ECASINO'),
    ('PLINKO',                        'ARCADE-TYPE', 'ECASINO'),
    ('ROYAL FISHING',                 'ARCADE-TYPE', 'ECASINO'),
    ('SECRET TREASURE',               'ARCADE-TYPE', 'ECASINO'),
    ('SUPER ACE SCRATCH',             'ARCADE-TYPE', 'ECASINO'),
    ('TOWER',                         'ARCADE-TYPE', 'ECASINO'),
    # NUMERIC GAMES
    ('BOXING EXTRAVAGANZA',           'NUMERIC',     'NUMERIC'),
    ('GO FOR CHAMPION',               'NUMERIC',     'NUMERIC'),
    ('KENO',                          'NUMERIC',     'NUMERIC'),
    ('KENO BONUS NUMBER',             'NUMERIC',     'NUMERIC'),
    ('KENO EXTRA BET',                'NUMERIC',     'NUMERIC'),
    ('KENO SUPER CHANCE',             'NUMERIC',     'NUMERIC'),
    ('NUMBER KING',                   'NUMERIC',     'NUMERIC'),
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
        WHERE provider = 38
          AND language = 2
        GROUP BY code
        ORDER BY code
    """)
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
                ambiguous.append((code, db_name, tops[:3]))
            else:
                matched.append((code, db_name, top1[1], top1[2], top1[3], top1[0]))
        else:
            unmatched.append((code, db_name, top1[0], top1[1]))

    # ── 輸出 SQL ─────────────────────────────────────────────────
    out_lines = []

    out_lines.append("-- ============================================================")
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
            f"    (38, '{escape_sql(str(code))}', '{escape_sql(db_name)}', "
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
            f"-- (38, '{escape_sql(str(code))}', '{escape_sql(db_name)}', "
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

    out_path = r"C:\Users\user\OneDrive\桌面\testpage\jili_mapping_output.sql"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output_sql)

    print(f"Done.")
    print(f"  MATCHED   : {len(matched)}")
    print(f"  AMBIGUOUS : {len(ambiguous)}")
    print(f"  UNMATCHED : {len(unmatched)}")
    print(f"  Output    : {out_path}")


if __name__ == "__main__":
    main()
