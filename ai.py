import cv2
import numpy as np
import tensorflow.lite as tflite
import asyncio

import backend
import config

allow_control: bool = False
object_found: bool = False
calibration: float = False

_interpreter = None
_input_details = None
_output_details = None
_labels = None

async def think(frame):
    global object_found, calibration

    available = await asyncio.to_thread(get_object_available, frame)

    if available and calibration != 0:
        xmin, xmax, ymin, ymax, mask = get_object_available(frame)
        width_px = xmax - xmin

        config.set_pixels_per_cm(width_px / calibration)
        await backend.Socket.send({
            "type": "calibrate",
            "result": width_px / calibration
        })
        calibration = 0

    if available is not None and not object_found:
        result = await asyncio.to_thread(get_object, frame)
        object_found = True

        container = config.find(
            result["ai"],
            config.get_default_model(),
            result["color"][0],
            result["color"][1],
            result["color"][2],
            result["size"][0],
            result["size"][1]
        ) if result["ai"] is not None else None

        await backend.Socket.send({
            "type": "parameter",
            "container": container if result["ai"] is not None else None,
            "aiType": result["ai"] if result["ai"] is not None else None,
            "aiName": config.get_default_model() if result["ai"] is not None else None,
            "r": int(result["color"][0]),
            "g": int(result["color"][1]),
            "b": int(result["color"][2]),
            "w": int(result["size"][0]),
            "h": int(result["size"][1])
        })
        if allow_control:
            import hardware
            layout = hardware.containers_layout[int(container['id'])-1] if container is not None else {1: hardware.ServoState.OPEN, 2: hardware.ServoState.OPEN, 3: hardware.ServoState.OPEN}
            await hardware.sync({
                "motor": hardware.MotorState.FORWARD,
                "servo_1": layout[1],
                "servo_2": layout[2],
                "servo_3": layout[3]
            })

    elif available is None and object_found:
        object_found = False

def get_object(frame):
    xmin, xmax, ymin, ymax, mask = get_object_available(frame)
    object_size = get_object_size(xmax, xmin, ymin, ymax)
    object_color = get_object_color(frame, mask)
    object_type = get_object_type(frame[ymin:ymax, xmin:xmax])

    object_ = {
        "size": object_size,
        "color": object_color,
        "ai": object_type
    }
    return object_

def get_object_available(frame):
    h, w = frame.shape[:2]

    mask = get_object_mask(frame)

    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None

    xmin, xmax = xs.min(), xs.max()
    ymin, ymax = ys.min(), ys.max()

    if xmin == 0 or ymin == 0 or xmax >= w - 1 or ymax >= h - 1:
        return None

    return xmin, xmax, ymin, ymax, mask

def get_object_type(frame):
    if config.get_default_model() is None:
        return None

    if _interpreter is None:
        return None

    h, w = _input_details[0]["shape"][1:3]

    img = cv2.resize(frame, (w, h))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = np.expand_dims(img, axis=0)

    if _input_details[0]["dtype"] == np.float32:
        img = img.astype(np.float32) / 255.0

    _interpreter.set_tensor(_input_details[0]["index"], img)
    _interpreter.invoke()

    output = _interpreter.get_tensor(_output_details[0]["index"])[0]
    class_id = np.argmax(output)

    return _labels[class_id]

def load_model(name):
    global _interpreter, _input_details, _output_details, _labels

    model_path = f"models/{name}.tflite"
    labels_path = f"models/{name}.txt"

    _interpreter = tflite.Interpreter(model_path=model_path)
    _interpreter.allocate_tensors()

    _input_details = _interpreter.get_input_details()
    _output_details = _interpreter.get_output_details()

    _labels = []
    with open(labels_path, "r") as f:
        for line in f:
            parts = line.strip().split(maxsplit=1)
            _labels.append(parts[1])

def unload_model():
    global _interpreter, _input_details, _output_details, _labels
    _interpreter = None
    _input_details = None
    _output_details = None
    _labels = None

def get_object_color(frame, mask):
    object_pixels = frame[mask > 0]
    b, g, r = object_pixels.mean(axis=0)
    return r, g, b

def get_object_size(xmax, xmin, ymin, ymax):
    width_px = xmax - xmin
    height_px = ymax - ymin

    scale = float(config.config["ai"]["scale"])

    width_cm = width_px / scale
    height_cm = height_px / scale

    return width_cm, height_cm

def get_object_mask(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 120, 70])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 120, 70])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)

    mask = mask1 | mask2

    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel)

    return mask