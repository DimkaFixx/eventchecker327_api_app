import os
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import Column, Integer, String, create_engine, select
from sqlalchemy.orm import declarative_base, Session
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DB_URL")
API_KEY = os.getenv("API_SECRET_KEY")

if not DB_URL or not API_KEY:
    raise RuntimeError("Ошибка: DB_URL или API_SECRET_KEY не заданы в .env")

# Настройки базы и времени
app = FastAPI(title="327 Event Monitor API")
engine = create_engine(DB_URL)
Base = declarative_base()
MSK_TZ = timezone(timedelta(hours=3))

# --- Описание моделей таблиц БД прямо здесь (без файла db.py) ---
def create_bat_table_model(table_name: str):
    return type(
        f"BatTable_{table_name}",
        (Base,),
        {
            "__tablename__": table_name,
            "id": Column(Integer, primary_key=True),
            "nick": Column(String),
            "full_nick": Column(String, nullable=True),
            "bat": Column(String),
            "date": Column(String),
            "duration_seconds": Column(Integer, default=0),
            "last_session_start_time": Column(String),
            "last_seen_at": Column(String),
        },
    )

s1_327 = create_bat_table_model("s1_327")
s2_327 = create_bat_table_model("s2_327")

# --- Защита API-ключом ---
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(header_key: str = Security(api_key_header)):
    if header_key != API_KEY:
        raise HTTPException(status_code=403, detail="Доступ запрещен: неверный API-ключ")
    return header_key

# --- Эндпоинт для Discord-бота ---
@app.get("/online/327", dependencies=[Depends(verify_api_key)])
def get_current_327_online(server: int):
    """
    Возвращает список полных ников игроков 327, замеченных онлайн за последние 7 минут.
    """
    if server == 1:
        table = s1_327
    elif server == 2:
        table = s2_327
    else:
        raise HTTPException(status_code=400, detail="Доступны только серверы 1 или 2")

    # Временное окно: последние 7 минут по МСК (с запасом к циклу опроса)
    now_msk = datetime.now(MSK_TZ)
    time_threshold = (now_msk - timedelta(minutes=7)).isoformat(timespec="seconds")
    today_date = now_msk.date().isoformat()

    with Session(engine) as session:
        # Отбираем игроков сегодняшнего дня, активных за последние 7 минут
        stmt = (
            select(table.full_nick, table.nick)
            .where(
                table.date == today_date,
                table.last_seen_at >= time_threshold
            )
        )
        rows = session.execute(stmt).all()

    online_full_nicks = set()
    for full_nick, nick in rows:
        # Приоритетно берем полный ник, если пусто — обычный ник
        player_name = full_nick if full_nick else nick
        if player_name and player_name.strip():
            online_full_nicks.add(player_name.strip())

    return {
        "status": "ok",
        "server": server,
        "count": len(online_full_nicks),
        "players": sorted(list(online_full_nicks))
    }