from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import random
import json

app = FastAPI()

# Хранилище для комнат: { room_code: { "players": [name, ...], "connections": [ws, ...] } }
ROOMS = {}

@app.get("/")
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws/{room_code}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, player_name: str):
    await websocket.accept()
    
    # Если комнаты нет в памяти, создаем её на лету
    if room_code not in ROOMS:
        ROOMS[room_code] = {"players": [], "connections": []}

    room = ROOMS[room_code]
    
    # Добавляем игрока и его соединение, если их еще нет
    if player_name not in room["players"]:
        room["players"].append(player_name)
    
    if websocket not in room["connections"]:
        room["connections"].append(websocket)

    # Отправляем всем в комнате обновленный список игроков
    await broadcast(room_code, {
        "action": "update_players",
        "players": room["players"]
    })

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "start_game":
                r_code = message.get("room_code")
                if r_code in ROOMS:
                    players = ROOMS[r_code]["players"]
                    
                    if len(players) < 3:
                        await websocket.send_text(json.dumps({
                            "action": "error",
                            "message": "Нужно минимум 3 игрока для игры!"
                        }))
                        continue
                    
                    # Распределяем роли
                    roles = ["Мафия", "Шериф"]
                    while len(roles) < len(players):
                        roles.append("Мирный житель")
                    random.shuffle(roles)
                    
                    # Рассылаем роли участникам
                    for i, conn in enumerate(ROOMS[r_code]["connections"]):
                        try:
                            await conn.send_text(json.dumps({
                                "action": "game_started",
                                "role": roles[i]
                            }))
                        except Exception:
                            pass
            
    except WebSocketDisconnect:
        if room_code in ROOMS:
            if websocket in room["connections"]:
                room["connections"].remove(websocket)
            await broadcast(room_code, {
                "action": "update_players",
                "players": room["players"]
            })

async def broadcast(room_code: str, message: dict):
    if room_code in ROOMS:
        payload = json.dumps(message)
        for connection in ROOMS[room_code]["connections"]:
            try:
                await connection.send_text(payload)
            except Exception:
                pass
