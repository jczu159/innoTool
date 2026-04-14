"""
RedTiger megaxcess_game_type_mapping 生成器 (REDTIGER, provider=42)
- 從 PDF 動態抽取 EGLD-approved 遊戲清單 (game_id, game_name)
- 從 slot_game_setting_i18n 撈出 provider=42 的所有 DISTINCT game_code
- game_code 直接比對 PDF game_id (CODE_EXACT)
- 不在 PDF 的 DB 遊戲：仍歸 EGAMES/SLOT，標示為 NOT_IN_PDF
- 所有 REDTIGER 遊戲：game_type='SLOT', game_offering='EGAMES'

REDTIGER PDF: EVO REDTIGER.pdf (8 頁，312 款，全部 eCASINO GAMES / SLOT)
"""

import re
import pdfplumber
import mysql.connector

# ── 設定 ──────────────────────────────────────────────────────────
DB_CONFIG = dict(
    host     = 'tiger-dev-rds.servicelab.sh',
    port     = 3306,
    user     = 'inno_rd',
    password = '29SU5Rkt',
    database = 'tiger_thirdparty',
    charset  = 'utf8mb4',
)
PDF_PATH  = r'C:\Users\user\Downloads\LINE WORKS\GAME LIST\EVO REDTIGER.pdf'
PROVIDER  = 42
GAME_TYPE = 'SLOT'
GAME_OFFERING = 'EGAMES'   # 全部 eCASINO GAMES -> EGAMES


def extract_pdf_games(pdf_path: str) -> dict:
    """從 PDF 抽取 {game_id: game_name}"""
    result = {}
    pattern = re.compile(
        r'\s*\d+\.\s+eCASINO\s+G\s*AMES\s+(.+?)\s+([a-z0-9]+)\s+-\s+[\d.]+\s+SLOT'
    )
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                m = pattern.match(line)
                if m:
                    name = m.group(1).strip()
                    gid  = m.group(2).strip()
                    result[gid] = name
    return result


def escape_sql(s: str) -> str:
    return s.replace("'", "''")


def normalized_name(s: str) -> str:
    s = re.sub(r"[^A-Z0-9]", "_", s.upper())
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def build_insert_row(code, name, note=''):
    norm = normalized_name(name)
    prefix = f"    -- {note}\n" if note else ""
    return (
        f"{prefix}"
        f"    ({PROVIDER}, '{escape_sql(str(code))}', '{escape_sql(name)}', "
        f"'{norm}', '{GAME_TYPE}', '{GAME_OFFERING}')"
    )


def main():
    # 1. 抽 PDF
    print("Parsing PDF ...")
    pdf_map = extract_pdf_games(PDF_PATH)   # {game_id: game_name}
    print(f"  PDF games: {len(pdf_map)}")

    # 2. 撈 DB
    print("Connecting to DB ...")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT code, MAX(name) as name
        FROM tiger_thirdparty.slot_game_setting_i18n
        WHERE provider = %s AND language = 2
        GROUP BY code
        ORDER BY code
    """, (PROVIDER,))
    db_rows = {code: name for code, name in cursor.fetchall()}
    cursor.close()
    conn.close()
    print(f"  DB games (distinct code): {len(db_rows)}")

    # 3. 分類
    matched_rows   = []   # code in PDF → 用 PDF name
    not_in_pdf_rows = []  # code in DB only → 用 DB name，仍是 EGAMES

    for code, db_name in sorted(db_rows.items()):
        if code in pdf_map:
            pdf_name = pdf_map[code]
            matched_rows.append((code, pdf_name, f'PDF: "{pdf_name}"'))
        else:
            matched_rows   # keep separate
            not_in_pdf_rows.append((code, db_name or code, f'NOT_IN_PDF  DB: "{db_name}"'))

    pdf_not_in_db = [(gid, name) for gid, name in pdf_map.items() if gid not in db_rows]

    # 4. 輸出 SQL
    out = []
    out.append("-- ============================================================")
    out.append(f"-- REDTIGER (provider={PROVIDER}) megaxcess_game_type_mapping")
    out.append(f"-- game_type='{GAME_TYPE}', game_offering='{GAME_OFFERING}' (全部 eCASINO GAMES)")
    out.append(f"-- PDF games : {len(pdf_map)}")
    out.append(f"-- DB games  : {len(db_rows)}")
    out.append(f"-- CODE_EXACT: {len(db_rows) - len(not_in_pdf_rows)}")
    out.append(f"-- NOT_IN_PDF: {len(not_in_pdf_rows)}  (DB 有但 PDF 無，仍歸 EGAMES)")
    out.append(f"-- PDF_NOT_DB: {len(pdf_not_in_db)}  (PDF 有但 DB 無，忽略)")
    out.append("-- ============================================================\n")

    # CODE_EXACT section
    out.append(f"-- ── CODE_EXACT ({len(db_rows) - len(not_in_pdf_rows)} 筆) ──────────────────────────")
    out.append(
        "INSERT INTO tiger_thirdparty.megaxcess_game_type_mapping\n"
        "    (provider, game_code, game_name, normalized_name, game_type, game_offering)\nVALUES"
    )
    exact_rows = [(c, n, note) for c, n, note in
                  [(code, pdf_map[code], f'PDF: "{pdf_map[code]}"')
                   for code in sorted(db_rows) if code in pdf_map]]
    out.append(",\n".join(build_insert_row(c, n, note) for c, n, note in exact_rows))
    out.append(
        "ON DUPLICATE KEY UPDATE\n"
        "    game_name       = VALUES(game_name),\n"
        "    normalized_name = VALUES(normalized_name),\n"
        "    game_type       = VALUES(game_type),\n"
        "    game_offering   = VALUES(game_offering);\n"
    )

    # NOT_IN_PDF section
    if not_in_pdf_rows:
        out.append(f"\n-- ── NOT_IN_PDF ({len(not_in_pdf_rows)} 筆，DB 有、PDF 無，仍歸 EGAMES) ──")
        out.append(
            "INSERT INTO tiger_thirdparty.megaxcess_game_type_mapping\n"
            "    (provider, game_code, game_name, normalized_name, game_type, game_offering)\nVALUES"
        )
        out.append(",\n".join(build_insert_row(c, n, note) for c, n, note in not_in_pdf_rows))
        out.append(
            "ON DUPLICATE KEY UPDATE\n"
            "    game_name       = VALUES(game_name),\n"
            "    normalized_name = VALUES(normalized_name),\n"
            "    game_type       = VALUES(game_type),\n"
            "    game_offering   = VALUES(game_offering);\n"
        )

    # PDF_NOT_DB section (reference only)
    if pdf_not_in_db:
        out.append(f"\n-- ── PDF_NOT_DB ({len(pdf_not_in_db)} 筆，PDF 有但 DB 無，僅供參考) ──")
        for gid, name in sorted(pdf_not_in_db):
            out.append(f"-- game_id={gid}  name=\"{name}\"")

    output_path = r'C:\Users\user\OneDrive\桌面\testpage\redtiger_mapping_output.sql'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))

    print(f"\nSQL written to {output_path}")
    print(f"  CODE_EXACT : {len(db_rows) - len(not_in_pdf_rows)}")
    print(f"  NOT_IN_PDF : {len(not_in_pdf_rows)}")
    print(f"  PDF_NOT_DB : {len(pdf_not_in_db)}")


if __name__ == '__main__':
    main()
