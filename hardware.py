from engine import hw


def abandon():
    disconnect_machine()
    disconnect_camera()


def get_available_machines():
    return hw.get_available_devices().available_machines


def is_machine_connected():
    return hw.is_machine_connected()


async def connect_machine(port):
    await hw.connect_machine(port)


async def disconnect_machine():
    await hw.disconnect_machine()

async def sync(data):
    hw.set_direction(data["direction"])
    for gate in range(len(data["gates"])):
        hw.set_gate(gate, data["gates"][gate])

def get_available_cameras():
    return hw.get_available_devices().available_cameras


def is_camera_connected():
    return hw.is_camera_connected()


async def connect_camera(port):
    await hw.connect_camera(port)


async def disconnect_camera():
    await hw.disconnect_camera()


def frame():
    return hw.frame()
