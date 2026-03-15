import os
import pathlib
import shutil

from fastapi import *

import config
import hardware
from hardware import *
from starlette.responses import StreamingResponse
from typing import Optional
from json import loads
import ai

app = FastAPI()

class Socket:
    ws: Optional[WebSocket] = None

    @classmethod
    async def send(cls, message):
        if cls.ws:
            await cls.ws.send_json(message)
    @classmethod
    def close(cls):
        cls.ws = None
        abandon()

def mount_backend(main_app: FastAPI):
    main_app.mount("/api", app)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    Socket.ws = ws
    ai.object_found = False
    try:
        while True:
            await proceed_ws(loads(await ws.receive_text()))
    except WebSocketDisconnect:
        pass
    finally:
        Socket.close()

@app.post("/upload")
async def upload_model(
    name: str = Form(...),
    model: UploadFile = File(...),
    labels: UploadFile = File(...),
):
    os.makedirs("models", exist_ok=True)

    model_path = f"models/{name}.tflite"
    labels_path = f"models/{name}.txt"

    with open(model_path, "wb") as f:
        shutil.copyfileobj(model.file, f)

    with open(labels_path, "wb") as f:
        shutil.copyfileobj(labels.file, f)

    return {"status": "ok", "name": name}

async def proceed_ws(data):
    print(data)
    if data["type"] == "mode":
        ai.allow_control = not bool(data["manual"])
    elif data["type"] == "sync":
        await sync(data)
    elif data["type"] == "info":
        await Socket.send({
            "type": "info",
            "machine": {
                "connected": is_machine_connected(),
                "availablePorts": available_ports()
            },
            "camera": {
                "connected": False,
                "availablePorts": get_cameras()
            }
        })
    elif data["type"] == "connectHw":
        await connect_machine(data["port"])
    elif data["type"] == "connectCam":
        await connect_camera(data["port"])
    elif data["type"] == "disconnect":
        abandon()
    elif data["type"] == "modelInfo":
        await Socket.send({
            "type": "modelInfo",
            "model": f"{config.config['ai']['default_model']}",
            "modelsList": [p.name for p in pathlib.Path("models").glob("*.tflite")]
        })
    elif data["type"] == "useModel":
        config.config['ai']['default_model'] = data["model"]
        config.update_config()
        if data["model"] == "":
            ai.unload_model()
        else:
            ai.load_model(config.config["ai"]["default_model"])
    elif data["type"] == "getContainer":
        await Socket.send({
            "type": "getContainer",
            "container": config.get_container(data["id"])
        })
    elif data["type"] == "setContainer":
        config.set_container(data["container"])
    elif data["type"] == "containerAiList":
        await Socket.send({
            "type": "containerAiList",
            "available": config.get_ai_available()
        })
    elif data["type"] == "containerAiClasses":
        await Socket.send({
            "type": "containerAiClasses",
            "classes": config.get_ai_classes(data["model"])
        })

@app.get("/video")
async def video_feed():
    if Socket.ws:
        return StreamingResponse(
            hardware.camera.generate_frames(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={
                "X-Frame-Options": "ALLOWALL"
            }
        )
    else:
        return None
