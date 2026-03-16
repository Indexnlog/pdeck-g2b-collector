import os
import psycopg2
from psycopg2.extras import execute_values
from utils.logger import log

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS contracts (
    unty_cntrct_no               VARCHAR(50)  PRIMARY KEY,
    bsns_div_nm                  VARCHAR(100),
    cntrct_nm                    TEXT,
    cntrct_cncls_date            DATE,
    cntrct_prd                   TEXT,
    tot_cntrct_amt               BIGINT,
    thtm_cntrct_amt              BIGINT,
    cntrct_instt_cd              VARCHAR(50),
    cntrct_instt_nm              VARCHAR(500),
    cntrct_instt_jrsdctn_div_nm  VARCHAR(200),
    cntrct_cncls_mthd_nm         VARCHAR(200),
    pay_div_nm                   VARCHAR(200),
    ntce_no                      VARCHAR(100),
    corp_list                    TEXT,
    lngtrm_ctnu_div_nm           VARCHAR(100),
    cmmn_cntrct_yn               CHAR(1),
    rgst_dt                      TIMESTAMP,
    collected_year               SMALLINT,
    collected_month              SMALLINT
);
"""

CREATE_PROGRESS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS progress (
    id              INT         PRIMARY KEY DEFAULT 1,
    current_job     VARCHAR(20) NOT NULL DEFAULT '물품',
    current_year    SMALLINT    NOT NULL DEFAULT 2016,
    current_month   SMALLINT    NOT NULL DEFAULT 2,
    daily_api_calls INT         NOT NULL DEFAULT 0,
    total_collected BIGINT      NOT NULL DEFAULT 0,
    last_run_date   VARCHAR(10) NOT NULL DEFAULT ''
);
"""

CREATE_RUN_HISTORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS run_history (
    id              SERIAL      PRIMARY KEY,
    run_date        VARCHAR(10) NOT NULL,
    collected       INT         NOT NULL DEFAULT 0,
    api_calls       INT         NOT NULL DEFAULT 0,
    end_job         VARCHAR(20),
    end_year        SMALLINT,
    end_month       SMALLINT,
    created_at      TIMESTAMP   DEFAULT now()
);
"""


def get_connection():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise EnvironmentError("DATABASE_URL 환경변수가 설정되지 않았습니다")
    return psycopg2.connect(url)


def create_table():
    """최초 실행 시 테이블 생성 (이미 있으면 무시)"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            cur.execute(CREATE_PROGRESS_TABLE_SQL)
            cur.execute(CREATE_RUN_HISTORY_TABLE_SQL)
    log("✅ contracts / progress / run_history 테이블 준비 완료")


def load_progress() -> dict:
    """progress 테이블에서 진행 상태 로드. 없으면 기본값 반환."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_job, current_year, current_month, "
                "daily_api_calls, total_collected, last_run_date "
                "FROM progress WHERE id = 1"
            )
            row = cur.fetchone()
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
        VALUES (1, %(current_job)s, %(current_year)s, %(current_month)s,
                %(daily_api_calls)s, %(total_collected)s, %(last_run_date)s)
        ON CONFLICT (id) DO UPDATE SET
            current_job     = EXCLUDED.current_job,
            current_year    = EXCLUDED.current_year,
            current_month   = EXCLUDED.current_month,
            daily_api_calls = EXCLUDED.daily_api_calls,
            total_collected = EXCLUDED.total_collected,
            last_run_date   = EXCLUDED.last_run_date
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, progress)


def save_run_history(run_date: str, collected: int, api_calls: int,
                     end_job: str, end_year: int, end_month: int) -> None:
    """실행 결과를 run_history 테이블에 기록."""
    sql = """
        INSERT INTO run_history (run_date, collected, api_calls, end_job, end_year, end_month)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (run_date, collected, api_calls, end_job, end_year, end_month))


def insert_contracts(rows: list) -> int:
    """
    계약 데이터 배치 insert.
    중복(unty_cntrct_no)은 ON CONFLICT DO NOTHING으로 건너뜀.
    대량 데이터(6만 건+)도 5000건씩 나눠서 안정적으로 처리.
    """
    if not rows:
        return 0

    BATCH_SIZE = 5000  # CockroachDB 트랜잭션 크기 제한 대응
    cols = list(rows[0].keys())
    sql = f"""
        INSERT INTO contracts ({', '.join(cols)})
        VALUES %s
        ON CONFLICT (unty_cntrct_no) DO NOTHING
    """

    total_inserted = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        values = [[r[c] for c in cols] for r in batch]
        with get_connection() as conn:
            with conn.cursor() as cur:
                execute_values(cur, sql, values, page_size=500)
                inserted = cur.rowcount if cur.rowcount >= 0 else len(values)
                total_inserted += inserted

    return total_inserted
