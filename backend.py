import os
import pathlib
import shutil
from typing import Optional
from json import loads

import cv2
from fastapi import *
from starlette.responses import StreamingResponse

import hardware as hw
import parameters

import config

api = FastAPI()


class Socket:
    ws: Optional[WebSocket] = None

    @classmethod
    async def send(cls, message):
        if cls.ws:
            await cls.ws.send_json(message)

    @classmethod
    def close(cls):
        cls.ws = None
        hw.abandon()
        parameters.ai_unload_model()


def mount_backend(main_app: FastAPI):
    main_app.mount("/api", api)


@api.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    Socket.ws = ws
    parameters.object_found = False
    parameters.allow_control = False
    if config.config["ai"]["default_model"] != "":
        parameters.ai_load_model(config.config["ai"]["default_model"])
    try:
        while True:
            await proceed_ws(loads(await ws.receive_text()))
    except WebSocketDisconnect:
        pass
    finally:
        Socket.close()


@api.post("/upload")
async def upload(
        name: str = Form(...),
        file: UploadFile = File(...)
):
    return {"status": "ok", "name": name}


async def proceed_ws(data):
    if data["type"] == "mode":
        parameters.allow_control = not bool(data["manual"])
    elif data["type"] == "sync":
        await hw.sync(data)
    elif data["type"] == "info":
        await Socket.send({
            "type": "info",
            "machine": {
                "connected": hw.is_machine_connected(),
                "availablePorts": hw.get_available_machines()
            },
            "camera": {
                "connected": hw.is_camera_connected(),
                "availablePorts": hw.get_available_cameras()
            },
            "calibration": str(config.config["ai"]["scale"])
        })
    elif data["type"] == "connectHw":
        await hw.connect_machine(data["port"])
    elif data["type"] == "connectCam":
        await hw.connect_camera(data["port"])
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
            parameters.ai_unload_model()
        else:
            parameters.ai_load_model(config.config["ai"]["default_model"])
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
    elif data["type"] == "calibrate":
        parameters.calibration = float(data["scale"])
    elif data["type"] == "resetConfigs":
        config.create_config()
        config.update_config(True)
        Socket.close()
    elif data["type"] == "resetModels":
        parameters.ai_unload_model()
        config.config["ai"]["default_model"] = ""
        config.update_config()
        shutil.rmtree("models")
        Socket.close()


@api.get("/video")
async def video_feed():
    if Socket.ws:
        return StreamingResponse(
            generate_frame(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={
                "X-Frame-Options": "ALLOWALL"
            }
        )
    else:
        return None


async def generate_frame():
    try:
        while True:
            frame = hw.frame()

            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    finally:
        pass
