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
    
    if room_code not in ROOMS:
        # Автоматически создаем комнату, если игрок пытается войти по коду
        ROOMS[room_code] = {"players": [], "connections": []}

    room = ROOMS[room_code]
    
    # Избегаем дублирования игрока
    if player_name not in room["players"]:
        room["players"].append(player_name)
    
    if websocket not in room["connections"]:
        room["connections"].append(websocket)

    # Рассылаем обновленный список игроков
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
                            "message": "Нужно минимум 3 игрока для распределения ролей!"
                        }))
                        continue
                    
                    # Распределяем роли
                    roles = ["Мафия", "Шериф"]
                    while len(roles) < len(players):
                        roles.append("Мирный житель")
                    random.shuffle(roles)
                    
                    # Отправляем каждому его роль
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
            # Не удаляем имя игрока сразу, чтобы при перезагрузке страницы лобби не ломалось
            await broadcast(room_code, {
                "action": "update_players",
                "players": room["players"]
            })

@app.post("/create_room")
async def create_room():
    room_code = str(random.randint(1000, 9999))
    while room_code in ROOMS:
        room_code = str(random.randint(1000, 9999))
    ROOMS[room_code] = {"players": [], "connections": []}
    return {"status": "success", "room_code": room_code}

@app.get("/check_room/{room_code}")
async def check_room(room_code: str):
    return {"exists": True} # Упрощаем вход

async def broadcast(room_code: str, message: dict):
    if room_code in ROOMS:
        payload = json.dumps(message)
        for connection in ROOMS[room_code]["connections"]:
            try:
                await connection.send_text(payload)
            except Exception:
                pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
