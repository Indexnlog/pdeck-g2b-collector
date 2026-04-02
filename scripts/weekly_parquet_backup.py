"""
주간 Parquet 백업 스크립트
SQLite → Parquet 변환 → S3 업로드
Windows Task Scheduler에서 주 1회 실행
"""
import subprocess
import duckdb
from datetime import datetime

DB_PATH = "D:/pdeck-data/g2b-collector/g2b.db"
PARQUET_PATH = "D:/pdeck-data/g2b-collector/parquet/contracts.parquet"
S3_PATH = "s3://zigu-data-lake/backup/g2b/contracts.parquet"
AWS_CLI = r"C:\Program Files\Amazon\AWSCLIV2\aws.exe"

def main():
    print(f"[{datetime.now()}] Weekly Parquet backup started")

    # 1. SQLite → Parquet
    print("Converting SQLite to Parquet...")
    con = duckdb.connect()
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute("SET sqlite_all_varchar=true;")

    row_count = con.execute(
        f"SELECT count(*) FROM sqlite_scan('{DB_PATH}', 'contracts')"
    ).fetchone()[0]
    print(f"Total rows: {row_count:,}")

    con.execute(f"""
        COPY (SELECT * FROM sqlite_scan('{DB_PATH}', 'contracts'))
        TO '{PARQUET_PATH}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    con.close()
    print("Parquet conversion done")

    # 2. S3 업로드
    print("Uploading to S3...")
    result = subprocess.run(
        [AWS_CLI, "s3", "cp", PARQUET_PATH, S3_PATH, "--no-progress"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"[{datetime.now()}] S3 upload complete: {row_count:,} rows")
    else:
        print(f"[{datetime.now()}] S3 upload FAILED: {result.stderr}")

if __name__ == "__main__":
    main()
