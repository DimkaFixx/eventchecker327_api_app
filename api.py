import os
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Берем модели прямо из вашего db.py
from db import s1_327, s2_327, MSK_TZ

load_dotenv()
DB_URL = os.getenv("DB_URL")
API_KEY = os.getenv("API_SECRET_KEY")

if not DB_URL or not API_KEY:
    raise RuntimeError("Ошибка: DB_URL или API_SECRET_KEY не заданы в .env")

app = FastAPI(title="327 Event Monitor API")
engine = create_engine(DB_URL)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(header_key: str = Security(api_key_header)):
    if header_key != API_KEY:
        raise HTTPException(status_code=403, detail="Доступ запрещен: неверный API-ключ")
    return header_key

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

    # Временное окно: 7 минут назад по МСК (с запасом к 5-минутному циклу парсера)
    now_msk = datetime.now(MSK_TZ)
    time_threshold = (now_msk - timedelta(minutes=7)).isoformat(timespec="seconds")
    today_date = now_msk.date().isoformat()

    with Session(engine) as session:
        # Фильтруем строго по сегодняшнему дню и времени последней активности
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
        # Приоритет отдаем полному нику со всеми префиксами
        # Если вдруг для старой записи full_nick еще пустой — берем обычный nick
        player_name = full_nick if full_nick else nick
        if player_name and player_name.strip():
            online_full_nicks.add(player_name.strip())

    return {
        "status": "ok",
        "server": server,
        "count": len(online_full_nicks),
        "players": sorted(list(online_full_nicks)) # отдаем полный сырой список
    }