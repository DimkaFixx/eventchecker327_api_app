import os
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Модели берутся из вашего db.py
from db import s1_327, s2_327

load_dotenv()
DB_URL = os.getenv("DB_URL")
API_KEY = os.getenv("API_SECRET_KEY")

if not DB_URL or not API_KEY:
    raise RuntimeError("Ошибка: DB_URL или API_SECRET_KEY не заданы в .env")

app = FastAPI(title="327 Event Monitor API")
engine = create_engine(DB_URL)
MSK_TZ = timezone(timedelta(hours=3))

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(header_key: str = Security(api_key_header)):
    if header_key != API_KEY:
        raise HTTPException(status_code=403, detail="Доступ запрещен: неверный API-ключ")
    return header_key

@app.get("/online/327", dependencies=[Depends(verify_api_key)])
def get_current_327_online(server: int):
    """
    Возвращает список бойцов 327, замеченных на сервере за последние 7 минут.
    """
    if server == 1:
        table = s1_327
    elif server == 2:
        table = s2_327
    else:
        raise HTTPException(status_code=400, detail="Доступны только серверы 1 или 2")

    # Временное окно: последние 7 минут
    time_threshold = (datetime.now(MSK_TZ) - timedelta(minutes=7)).isoformat(timespec="seconds")

    with Session(engine) as session:
        stmt = (
            select(table.full_nick, table.nick)
            .where(
                table.last_seen_at >= time_threshold,
                table.bat == "327"
            )
        )
        rows = session.execute(stmt).all()

    online_players = []
    for full_nick, nick in rows:
        chosen_nick = full_nick if full_nick else nick
        if chosen_nick:
            online_players.append(chosen_nick.strip())

    return {
        "status": "ok",
        "server": server,
        "count": len(set(online_players)),
        "players": list(set(online_players))
    }