import backend
from engine import hw


async def abandon():
    await disconnect_machine()
    await disconnect_camera()


def get_available_machines():
    return hw.get_available_devices().available_machines


def is_machine_connected():
    return hw.is_machine_connected()


async def connect_machine(port):
    await hw.connect_machine(f"/dev/ttyUSB{port.split('-')[-1]}")
    await backend.Socket.send({
        "type": "connectedHw"
    })


async def disconnect_machine():
    await hw.disconnect_machine()

async def get_directions():
    return ["Stop", "Forward", "Backward"]

async def get_gates_count():
    return 3

async def get_gates():
    return ["open", "left", "right"]

async def sync(data):
    direction = data.get("direction")
    if direction:
        hw.set_direction(direction)

    gates = data.get("gates")
    for servo in hw.CONFIGURATION["servos"]:
        port = servo["port"]
        hw.set_gate(port, gates[port-1])
    await backend.Socket.send({
        "type": "sync",
        "motor": direction,
        "servo_1": gates[0],
        "servo_2": gates[1],
        "servo_3": gates[2],
    })


def get_available_cameras():
    return hw.get_available_devices().available_cameras


def is_camera_connected():
    return hw.is_camera_connected()


async def connect_camera(port):
    await hw.connect_camera(port)
    await backend.Socket.send({
        "type": "connectedCam"
    })


async def disconnect_camera():
    await hw.disconnect_camera()


def frame():
    return hw.frame()
