# api_debug.py
import os
import sqlite3
import logging
from fastapi import FastAPI, Depends, HTTPException
from typing import Generator, Dict, Any

# Настройка логирования в файл + консоль
LOGFILE = "api_debug.log"
logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(LOGFILE, encoding="utf-8"),
                              logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Путь к БД — абсолютный для надёжности
DB_FILENAME = "DataBase"
DB_PATH = os.path.abspath(DB_FILENAME)

app = FastAPI(title="Magnetic Storms API (debug)")

def get_db_conn() -> Generator[sqlite3.Connection, None, None]:
    """Открываем новое соединение для каждого запроса; настроено row_factory."""
    if not os.path.exists(DB_PATH):
        logger.warning("DB file not found: %s", DB_PATH)
    conn = sqlite3.connect(DB_PATH, timeout=30, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    # Включаем WAL (безопасно вызывать многократно)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception as e:
        logger.warning("PRAGMA WAL error: %s", e)
    try:
        yield conn
    finally:
        conn.close()

@app.get("/health")
def health():
    return {"status": "ok", "db_path": DB_PATH, "db_exists": os.path.exists(DB_PATH)}

@app.get("/dbinfo")
def dbinfo(conn: sqlite3.Connection = Depends(get_db_conn)):
    """Диагностический эндпоинт — покажет таблицы, счётчики и 5 последних записей."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        info: Dict[str, Any] = {"tables": tables}
        if "kp_index_data" in tables:
            cur.execute("SELECT COUNT(*) FROM kp_index_data")
            info["kp_index_count"] = cur.fetchone()[0]
            cur.execute("SELECT timestamp, kp_index FROM kp_index_data ORDER BY timestamp DESC LIMIT 5")
            info["kp_index_last5"] = [dict(timestamp=r[0], kp_index=r[1]) for r in cur.fetchall()]
        if "kp_forecasts_3day" in tables:
            cur.execute("SELECT COUNT(*) FROM kp_forecasts_3day")
            info["kp_forecast_count"] = cur.fetchone()[0]
            cur.execute("SELECT forecast_timestamp, kp_index, forecast_period FROM kp_forecasts_3day ORDER BY forecast_timestamp DESC LIMIT 5")
            info["kp_forecast_last5"] = [dict(forecast_timestamp=r[0], kp_index=r[1], forecast_period=r[2]) for r in cur.fetchall()]
        return info
    except Exception as e:
        logger.exception("Ошибка в /dbinfo")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def get_current_status(conn: sqlite3.Connection = Depends(get_db_conn)):
    try:
        cur = conn.cursor()
        cur.execute("SELECT timestamp, kp_index FROM kp_index_data ORDER BY timestamp DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return {"current_kp": None, "storm_level": "Нет данных"}
        # row — sqlite3.Row, можно обращаться как row["timestamp"]
        ts = row["timestamp"]
        kp = row["kp_index"]
        # Простейшая классификация
        storm_level = "Спокойное"
        if kp is not None:
            if kp >= 9.0: storm_level = "Экстремальная буря"
            elif kp >= 8.0: storm_level = "Очень сильная буря"
            elif kp >= 7.0: storm_level = "Сильная буря"
            elif kp >= 6.0: storm_level = "Умеренная буря"
            elif kp >= 5.0: storm_level = "Небольшая буря"
        return {"current_kp": {"timestamp": ts, "kp_index": kp}, "storm_level": storm_level}
    except Exception as e:
        logger.exception("Ошибка в /status")
        # Для локальной отладки возвращаем текст ошибки
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/forecast/3day")
def get_3day_forecast(conn: sqlite3.Connection = Depends(get_db_conn)):
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT forecast_timestamp, kp_index, forecast_period
            FROM kp_forecasts_3day
            WHERE forecast_timestamp >= datetime('now')
              AND forecast_timestamp <= datetime('now', '+3 days')
            ORDER BY forecast_timestamp
        """)
        rows = cur.fetchall()
        return {"count": len(rows), "items": [dict(forecast_timestamp=r[0], kp_index=r[1], forecast_period=r[2]) for r in rows]}
    except Exception as e:
        logger.exception("Ошибка в /forecast/3day")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/kp")
def list_kp(limit: int = 100, conn: sqlite3.Connection = Depends(get_db_conn)):
    try:
        cur = conn.cursor()
        cur.execute("SELECT timestamp, kp_index FROM kp_index_data ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return {"count": len(rows), "items": [dict(timestamp=r[0], kp_index=r[1]) for r in rows]}
    except Exception as e:
        logger.exception("Ошибка в /kp")
        raise HTTPException(status_code=500, detail=str(e))
