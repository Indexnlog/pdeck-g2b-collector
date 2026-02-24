import os
import psycopg2
from psycopg2.extras import execute_values
from utils.logger import log

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS contracts (
    unty_cntrct_no               VARCHAR(50)  PRIMARY KEY,
    bsns_div_nm                  VARCHAR(10),
    cntrct_nm                    TEXT,
    cntrct_cncls_date            DATE,
    cntrct_prd                   VARCHAR(20),
    tot_cntrct_amt               BIGINT,
    thtm_cntrct_amt              BIGINT,
    cntrct_instt_cd              VARCHAR(20),
    cntrct_instt_nm              VARCHAR(200),
    cntrct_instt_jrsdctn_div_nm  VARCHAR(50),
    cntrct_cncls_mthd_nm         VARCHAR(50),
    pay_div_nm                   VARCHAR(50),
    ntce_no                      VARCHAR(50),
    corp_list                    TEXT,
    lngtrm_ctnu_div_nm           VARCHAR(20),
    cmmn_cntrct_yn               CHAR(1),
    rgst_dt                      TIMESTAMP,
    collected_year               SMALLINT,
    collected_month              SMALLINT
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
    log("✅ contracts 테이블 준비 완료")


def insert_contracts(rows: list) -> int:
    """
    계약 데이터 배치 insert.
    중복(unty_cntrct_no)은 ON CONFLICT DO NOTHING으로 건너뜀.
    실제 insert된 건수 반환.
    """
    if not rows:
        return 0

    cols = list(rows[0].keys())
    values = [[r[c] for c in cols] for r in rows]
    sql = f"""
        INSERT INTO contracts ({', '.join(cols)})
        VALUES %s
        ON CONFLICT (unty_cntrct_no) DO NOTHING
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, values, page_size=500)
            inserted = cur.rowcount if cur.rowcount >= 0 else len(values)
    return inserted
