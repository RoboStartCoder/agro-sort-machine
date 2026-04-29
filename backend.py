import asyncio
import json
import os
from pathlib import Path
import shutil
import uuid
from enum import Enum
from types import TracebackType
from typing import Optional
from json import loads

import cv2
from asm import logman
from asm.logman import LogType
from fastapi import FastAPI, Form, UploadFile, File
from starlette.responses import StreamingResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

import containers
from exceptions import UploadNotRegistered, UploadTypeBroken, UnknownWebsocketTask

import parameters

import config

api = FastAPI()

uploads = []


class UploadType(Enum):
    MODEL = "Model"
    LABEL = "Label"
    MODULE = "Module"


class Socket:
    ws: Optional[WebSocket] = None
    connected: bool = False

    @classmethod
    async def send(cls, message):
        if not cls.ws or not cls.connected:
            return

        try:
            if message["type"] != "log":
                logman.log(f"WS push: {json.dumps(message, default=lambda o: f'<{type(o).__name__}>')}",
                           LogType.WEB_SERVER)
            await cls.ws.send_json(message)

        except Exception:
            cls.connected = False
            cls.ws = None

    @classmethod
    async def close(cls):
        import hardware as hw

        cls.connected = False

        try:
            if cls.ws:
                await cls.ws.close()
        except Exception:
            pass

        cls.ws = None

        await hw.abandon()
        parameters.ai_unload_model()


async def send_log(log: str):
    await Socket.send({
        "type": "log",
        "log": log
    })


def mount_backend(main_app: FastAPI):
    logman.bus.subscribe("onLog", send_log)
    main_app.mount("/api", api)


@api.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    Socket.ws = ws
    Socket.connected = True
    await send_log(logman.get_log_history())
    parameters.object_found = False
    parameters.allow_control = False
    try:
        while True:
            await proceed_ws(loads(await ws.receive_text()))
    except WebSocketDisconnect:
        pass
    finally:
        await Socket.close()


@api.post("/upload/{upload_id}")
async def upload(
        upload_id: str,
        name: str = Form(...),
        file: UploadFile = File(...)
):
    import engine
    for current_upload in uploads:
        if current_upload["id"] == upload_id:
            if current_upload["type"] == UploadType.MODEL.value or current_upload["type"] == UploadType.LABEL.value:
                Path(f"models/{engine.get_id_by_module(engine.ai)}").mkdir(parents=True, exist_ok=True)
                path = f"models/{engine.get_id_by_module(engine.ai)}/{current_upload['name']}.{file.filename.split('.')[-1]}"
            elif current_upload["type"] == UploadType.MODULE.value:
                path = f"modules/sources/{current_upload['name']}.{file.filename.split('.')[-1]}"
            else:
                raise UploadTypeBroken
            with open(path, "wb") as f:
                while chunk := await file.read(1024 * 1024):
                    f.write(chunk)

            if current_upload["type"] == UploadType.MODULE:
                await Socket.send({
                    "type": "registerModule"
                })
                engine.register_modules(Path(f"modules/sources/{current_upload['name']}"))
                await Socket.send({
                    "type": "registeredModule"
                })

            return {"status": "ok", "name": name}
    raise UploadNotRegistered


async def proceed_ws(data):
    import faulthandler
    faulthandler.enable()
    import hardware as hw
    import engine
    from asm import logman
    logman.log(f"WS pull: {data}", LogType.WEB_SERVER)
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
            }
        })
    elif data["type"] == "connectHw":
        await hw.connect_machine(data["port"])
    elif data["type"] == "connectCam":
        await hw.connect_camera(data["port"])
    elif data["type"] == "modelInfo":
        await Socket.send({
            "type": "modelInfo",
            "modelsList": parameters.get_models()
        })
    elif data["type"] == "useModel":
        if data["model"] == "":
            parameters.ai_unload_model()
        else:
            await parameters.ai_load_model(parameters.find_model(data["model"]),
                                           parameters.find_label(data["model"]) if data["model"] != "" else None)
    elif data["type"] == "getContainer":
        await Socket.send({
            "type": "getContainer",
            "container": containers.get_container(int(data["id"]))
        })
    elif data["type"] == "setContainer":
        containers.update_container(data["id"], data["container"])
    elif data["type"] == "calibrate":
        parameters.calibration = float(data["scale"])
    elif data["type"] == "resetConfigs":
        config.create_config()
        config.update_config(True)
        await Socket.close()
    elif data["type"] == "resetModels":
        parameters.ai_unload_model()
        config.update_config()
        shutil.rmtree("models")
        await Socket.close()
    elif data["type"] == "uploadTypes":
        await Socket.send({
            "type": "uploadTypes",
            "types": [c.value for c in UploadType]
        })
    elif data["type"] == "uploadExpansions":
        resss = []
        if data["upload_type"] == UploadType.MODULE.value:
            resss = ["py"]
        if data["upload_type"] == UploadType.MODEL.value:
            resss = engine.ai.expansions().model_expansion
        if data["upload_type"] == UploadType.LABEL.value:
            if engine.ai.expansions().labels_expansion is not None:
                resss = engine.ai.expansions().labels_expansion
        await Socket.send({
            "type": "uploadExtensions",
            "expansions": resss
        })
    elif data["type"] == "upload":
        await Socket.send({
            "type": "upload",
            "id": register_upload(data["name"], data["upload_type"])
        })
    elif data["type"] == "infoContainers":
        await Socket.send({
            "type": "infoContainers",
            "containers": containers.get_containers_count()
        })
    elif data["type"] == "getContainersPreset":
        await Socket.send({
            "type": "getContainersPreset",
            "preset": containers.get_containers_preset()
        })
    elif data["type"] == "getModulesActive":
        await Socket.send({
            "type": "getModulesActive",
            "modules": engine.get_active_modules()
        })
    elif data["type"] == "getModulesAll":
        await Socket.send({
            "type": "getModulesAll",
            "modules": engine.get_all_modules()
        })
    elif data["type"] == "getDirections":
        await Socket.send({
            "type": "getDirections",
            "directions": await hw.get_directions()
        })
    elif data["type"] == "getGatesCount":
        await Socket.send({
            "type": "getGatesCount",
            "gates": await hw.get_gates_count()
        })
    elif data["type"] == "getGates":
        await Socket.send({
            "type": "getGates",
            "gates": await hw.get_gates()
        })
    else:
        raise UnknownWebsocketTask


def register_upload(name: str, upload_type: str) -> str:
    upload_id = str(uuid.uuid4())
    uploads.append({
        "id": upload_id,
        "name": name,
        "type": upload_type
    })
    return upload_id


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
    import hardware as hw
    import cv2

    while True:
        frame = await asyncio.to_thread(hw.frame)
        if frame is None:
            continue
        await parameters.think(frame)
        if frame is None or frame.size == 0:
            continue
        ok, buffer = await asyncio.to_thread(cv2.imencode, '.jpg', frame)

        if not ok:
            continue

        frame_bytes = buffer.tobytes()

        yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                frame_bytes +
                b'\r\n'
        )

        await asyncio.sleep(0)
