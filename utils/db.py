import os
import sqlite3
from utils.logger import log

# 외장하드 SQLite DB 경로 (D:\pdeck-data\g2b-collector\g2b.db)
DB_PATH = os.environ.get(
    "G2B_DB_PATH",
    "D:/pdeck-data/g2b-collector/g2b.db"
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS contracts (
    unty_cntrct_no               TEXT PRIMARY KEY,
    bsns_div_nm                  TEXT,
    cntrct_nm                    TEXT,
    cntrct_cncls_date            TEXT,
    cntrct_prd                   TEXT,
    tot_cntrct_amt               INTEGER,
    thtm_cntrct_amt              INTEGER,
    cntrct_instt_cd              TEXT,
    cntrct_instt_nm              TEXT,
    cntrct_instt_jrsdctn_div_nm  TEXT,
    cntrct_cncls_mthd_nm         TEXT,
    pay_div_nm                   TEXT,
    ntce_no                      TEXT,
    corp_list                    TEXT,
    lngtrm_ctnu_div_nm           TEXT,
    cmmn_cntrct_yn               TEXT,
    rgst_dt                      TEXT,
    collected_year               INTEGER,
    collected_month              INTEGER
);
"""

CREATE_PROGRESS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS progress (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    current_job     TEXT NOT NULL DEFAULT '물품',
    current_year    INTEGER NOT NULL DEFAULT 2016,
    current_month   INTEGER NOT NULL DEFAULT 2,
    daily_api_calls INTEGER NOT NULL DEFAULT 0,
    total_collected INTEGER NOT NULL DEFAULT 0,
    last_run_date   TEXT NOT NULL DEFAULT ''
);
"""

CREATE_RUN_HISTORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS run_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date        TEXT NOT NULL,
    collected       INTEGER NOT NULL DEFAULT 0,
    api_calls       INTEGER NOT NULL DEFAULT 0,
    end_job         TEXT,
    end_year        INTEGER,
    end_month       INTEGER,
    created_at      TEXT DEFAULT (datetime('now'))
);
"""


def get_connection():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def create_table():
    """최초 실행 시 테이블 생성 (이미 있으면 무시)"""
    conn = get_connection()
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(CREATE_PROGRESS_TABLE_SQL)
    conn.execute(CREATE_RUN_HISTORY_TABLE_SQL)
    conn.commit()
    conn.close()
    log("✅ contracts / progress / run_history 테이블 준비 완료")


def load_progress() -> dict:
    """progress 테이블에서 진행 상태 로드. 없으면 기본값 반환."""
    conn = get_connection()
    cur = conn.execute(
        "SELECT current_job, current_year, current_month, "
        "daily_api_calls, total_collected, last_run_date "
        "FROM progress WHERE id = 1"
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "current_job":     row[0],
            "current_year":    row[1],
            "current_month":   row[2],
            "daily_api_calls": row[3],
            "total_collected": row[4],
            "last_run_date":   row[5],
        }
    return {
        "current_job":     "물품",
        "current_year":    2016,
        "current_month":   2,
        "daily_api_calls": 0,
        "total_collected": 0,
        "last_run_date":   "",
    }


def save_progress(progress: dict) -> None:
    """progress 테이블에 진행 상태 저장 (upsert)."""
    sql = """
        INSERT INTO progress
            (id, current_job, current_year, current_month,
             daily_api_calls, total_collected, last_run_date)
        VALUES (1, :current_job, :current_year, :current_month,
                :daily_api_calls, :total_collected, :last_run_date)
        ON CONFLICT (id) DO UPDATE SET
            current_job     = excluded.current_job,
            current_year    = excluded.current_year,
            current_month   = excluded.current_month,
            daily_api_calls = excluded.daily_api_calls,
            total_collected = excluded.total_collected,
            last_run_date   = excluded.last_run_date
    """
    conn = get_connection()
    conn.execute(sql, progress)
    conn.commit()
    conn.close()


def save_run_history(run_date: str, collected: int, api_calls: int,
                     end_job: str, end_year: int, end_month: int) -> None:
    """실행 결과를 run_history 테이블에 기록."""
    sql = """
        INSERT INTO run_history (run_date, collected, api_calls, end_job, end_year, end_month)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    conn = get_connection()
    conn.execute(sql, (run_date, collected, api_calls, end_job, end_year, end_month))
    conn.commit()
    conn.close()


def find_collection_gaps(start_year: int = 2016, start_month: int = 2) -> list:
    """
    DB에 수집된 구간과 있어야 할 전체 구간을 비교해서 누락된 구간을 반환.

    Returns:
        list of dict: [{"job": "물품", "year": 2025, "month": 6}, ...]
    """
    from datetime import datetime
    import pytz

    jobs = ["물품", "공사", "용역", "외자"]

    # 현재 달의 전달까지가 수집 범위
    tz = pytz.timezone("Asia/Seoul")
    now = datetime.now(tz)
    if now.month == 1:
        end_year, end_month = now.year - 1, 12
    else:
        end_year, end_month = now.year, now.month - 1

    # DB에서 실제 수집된 (job, year, month) 조합 조회
    conn = get_connection()
    cur = conn.execute("""
        SELECT bsns_div_nm, collected_year, collected_month, COUNT(*) as cnt
        FROM contracts
        GROUP BY bsns_div_nm, collected_year, collected_month
    """)
    collected = set()
    for row in cur.fetchall():
        job_name, yr, mo, cnt = row
        if cnt > 0:
            collected.add((job_name, yr, mo))
    conn.close()

    # 전체 기대 구간 생성
    gaps = []
    for job in jobs:
        yr, mo = start_year, start_month
        while yr < end_year or (yr == end_year and mo <= end_month):
            if (job, yr, mo) not in collected:
                gaps.append({"job": job, "year": yr, "month": mo})
            if mo < 12:
                mo += 1
            else:
                yr += 1
                mo = 1

    return gaps


def insert_contracts(rows: list) -> int:
    """
    계약 데이터 배치 insert.
    중복(unty_cntrct_no)은 INSERT OR IGNORE로 건너뜀.
    """
    if not rows:
        return 0

    cols = list(rows[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    sql = f"""
        INSERT OR IGNORE INTO contracts ({', '.join(cols)})
        VALUES ({placeholders})
    """

    values = [[r[c] for c in cols] for r in rows]
    conn = get_connection()
    cur = conn.executemany(sql, values)
    inserted = cur.rowcount if cur.rowcount >= 0 else len(values)
    conn.commit()
    conn.close()

    return inserted
