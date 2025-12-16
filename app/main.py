from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import sqlite3
import os
import logging
from typing import Generator

# настройка логов
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Space Weather Forecast API",
    description="API для прогноза магнитных бурь на 3 дня",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# корс в фронтенде
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# подключение к БД 
DB_PATH = r"c:\project\space-weather\scripts\magnetic_data.db"

def get_db_conn() -> Generator[sqlite3.Connection, None, None]:
    """Подключение к БД"""
    logger.info(f"Подключение к БД: {DB_PATH}")
    logger.info(f"БД существует: {os.path.exists(DB_PATH)}")
    
    if not os.path.exists(DB_PATH):
        logger.error(f"Файл БД не найден: {DB_PATH}")
        raise HTTPException(status_code=500, detail=f"Database file not found: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Эндпоинты
@app.get("/health")
def health():
    db_exists = os.path.exists(DB_PATH)
    return {
        "status": "ok" if db_exists else "error",
        "db_path": DB_PATH,
        "db_exists": db_exists,
        "current_dir": os.getcwd()
    }

@app.get("/dbinfo")
def dbinfo(conn: sqlite3.Connection = Depends(get_db_conn)):
    """Диагностика БД"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        info = {
            "tables": tables,
            "current_time": datetime.now().isoformat()
        }
        
        if "kp_forecasts_3day" in tables:
            cur.execute("SELECT COUNT(*) FROM kp_forecasts_3day")
            info["kp_forecast_count"] = cur.fetchone()[0]
            
            cur.execute("SELECT forecast_timestamp, kp_index FROM kp_forecasts_3day ORDER BY forecast_timestamp DESC LIMIT 5")
            info["kp_forecast_last5"] = [dict(timestamp=r[0], kp_index=r[1]) for r in cur.fetchall()]
        else:
            info["error"] = "Таблица kp_forecasts_3day не найдена"
            
        return info
    except Exception as e:
        logger.exception("Ошибка в /dbinfo")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
def get_current_status(conn: sqlite3.Connection = Depends(get_db_conn)):
    """Текущий статус магнитной бури"""
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT forecast_timestamp, kp_index FROM kp_forecasts_3day ORDER BY forecast_timestamp DESC LIMIT 1")
        row = cur.fetchone()
        
        if not row:
            return {"current_kp": None, "storm_level": "Нет данных"}
        
        ts = row["forecast_timestamp"]
        kp = row["kp_index"]
        storm_level = "Спокойное"
        
        if kp is not None:
            if kp >= 9.0: storm_level = "Экстремальная буря"
            elif kp >= 8.0: storm_level = "Очень сильная буря"
            elif kp >= 7.0: storm_level = "Сильная буря"
            elif kp >= 6.0: storm_level = "Умеренная буря"
            elif kp >= 5.0: storm_level = "Небольшая буря"
            
        return {
            "current_kp": {
                "timestamp": ts, 
                "kp_index": kp
            }, 
            "storm_level": storm_level
        }
        
    except Exception as e:
        logger.exception("Ошибка в /api/status")
        return {"current_kp": None, "storm_level": f"Ошибка: {str(e)}"}

@app.get("/api/forecast")
def get_3day_forecast(conn: sqlite3.Connection = Depends(get_db_conn)):
    """Прогноз на 3 дня для фронтенда"""
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT forecast_timestamp, kp_index, forecast_period
            FROM kp_forecasts_3day
            WHERE forecast_timestamp >= datetime('now')
            ORDER BY forecast_timestamp
            LIMIT 48
        """)
        rows = cur.fetchall()
        
        if not rows:
            return get_fallback_forecast()
        
        # Обработка реальных данных
        return process_real_forecast_data(rows)
        
    except Exception as e:
        logger.exception("Ошибка в /api/forecast")
        return get_fallback_forecast()

def get_fallback_forecast():
    """Запасной вариант прогноза"""
    today = datetime.now().date()
    return {
        "location": "Москва",
        "currentStorm": "Слабая буря",
        "warning": "Данные обновляются",
        "days": [
            {
                "day": "Сегодня",
                "date": today.strftime("%d %B"),
                "stormLevel": "Слабая буря",
                "data": {
                    "values": [3, 4, 5, 4, 3, 4, 3, 4],
                    "times": ["06:00", "09:00", "12:00", "15:00", "18:00", "21:00", "00:00", "03:00"]
                }
            },
            {
                "day": "Завтра", 
                "date": (today + timedelta(days=1)).strftime("%d %B"),
                "stormLevel": "Слабая буря",
                "data": {
                    "values": [4, 3, 4, 5, 4, 3, 4, 3],
                    "times": ["06:00", "09:00", "12:00", "15:00", "18:00", "21:00", "00:00", "03:00"]
                }
            }
        ]
    }

def process_real_forecast_data(rows):
    """Обработка реальных данных прогноза"""
    forecasts_by_day = {}
    today = datetime.now().date()
    
    print(f"Обработка {len(rows)} записей из БД")
    
    for row in rows:
        timestamp_str = row["forecast_timestamp"]
        try:
            # парсим timestamp из базы данных
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            row_date = timestamp.date()
            
            # пропускаем прошедшие даты
            if row_date < today:
                continue
                
        except Exception as e:
            print(f"Ошибка парсинга времени {timestamp_str}: {e}")
            continue
            
        date_key = row_date.isoformat()
        time_str = timestamp.strftime("%H:%M")
        
        if date_key not in forecasts_by_day:
            day_name = get_day_name(row_date)
            forecasts_by_day[date_key] = {
                "day": day_name,
                "date": row_date.strftime("%d %B"),
                "stormLevel": "Спокойное",
                "data": {
                    "values": [],
                    "times": []
                }
            }
        
        kp_value = row["kp_index"]
        forecasts_by_day[date_key]["data"]["values"].append(kp_value)
        forecasts_by_day[date_key]["data"]["times"].append(time_str)
    
    # сортируем дни по дате
    sorted_days = sorted(forecasts_by_day.items(), key=lambda x: x[0])
    days_list = [day_data for _, day_data in sorted_days[:3]]
    
    # Определяем уровни бурь для каждого дня
    for day in days_list:
        if day["data"]["values"]:
            max_kp = max(day["data"]["values"])
            day["stormLevel"] = get_storm_level(max_kp)
        else:
            day["stormLevel"] = "Спокойное"
    
    # Определяем текущую бурю
    current_storm = "Спокойное"
    if days_list and days_list[0]["data"]["values"]:
        max_kp_today = max(days_list[0]["data"]["values"])
        current_storm = get_storm_level(max_kp_today)
    
    print(f"Сформирован прогноз на {len(days_list)} дней")
    
    result = {
        "location": "Москва",
        "currentStorm": current_storm,
        "warning": get_warning_message(current_storm),
        "days": days_list
    }
    
    # Логируем результат для отладки
    print("Отправляемый JSON:", result)
    return result
def get_day_name(date):
    """Получить название дня"""
    today = datetime.now().date()
    if date == today:
        return "Сегодня"
    elif date == today + timedelta(days=1):
        return "Завтра"
    else:
        days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        return days_ru[date.weekday()]

def get_storm_level(kp_index):
    """Определить уровень бури по Kp-индексу"""
    if kp_index >= 9.0: return "Экстремальная буря"
    elif kp_index >= 8.0: return "Очень сильная буря"
    elif kp_index >= 7.0: return "Сильная буря"
    elif kp_index >= 6.0: return "Умеренная буря"
    elif kp_index >= 5.0: return "Небольшая буря"
    else: return "Спокойное"

def get_warning_message(storm_level):
    """Получить предупреждение based on storm level"""
    warnings = {
        "Спокойное": "Геомагнитная обстановка спокойная",
        "Небольшая буря": "Возможны незначительные колебания",
        "Умеренная буря": "Внимание! Умеренная магнитная буря",
        "Сильная буря": "Осторожно! Сильная магнитная буря",
        "Очень сильная буря": "ВНИМАНИЕ! Очень сильная магнитная буря",
        "Экстремальная буря": "КРИТИЧЕСКО! Экстремальная магнитная буря"
    }
    return warnings.get(storm_level, "Мониторинг геомагнитной активности")

# Главная страница с фронтендом
@app.get("/")
async def read_root(request: Request):
    """Главная страница с фронтендом"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/sun-times")
async def get_sun_times_api():
    """API для получения времени солнца"""
    now = datetime.now()
    month = now.month
    is_winter = month >= 10 or month <= 2
    
    return {
        "dawnStart": "07:30" if is_winter else "04:30",
        "sunrise": "08:45" if is_winter else "05:45", 
        "solarNoon": "12:30",
        "sunset": "16:15" if is_winter else "19:15",
        "duskEnd": "17:30" if is_winter else "20:30"
    }

# Старые эндпоинты для обратной совместимости
@app.get("/api/old-forecast")
async def get_old_forecast():
    """Старый эндпоинт для обратной совместимости"""
    today = datetime.now().date()
    return {
        "forecast": [
            {
                "day": "today",
                "date": today.isoformat(),
                "kp_index": 3.0,
                "storm_level": "calm"
            },
            {
                "day": "tomorrow", 
                "date": (today + timedelta(days=1)).isoformat(),
                "kp_index": 5.0,
                "storm_level": "weak"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)