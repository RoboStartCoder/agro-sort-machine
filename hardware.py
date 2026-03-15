import glob
from enum import Enum
import re
from typing import Optional

import serial
import serial.tools.list_ports
import cv2
import backend


# ENUMS
class MotorState(Enum):
    STOP = 's'
    BACKWARD = 'b'
    FORWARD = 'f'


class ServoState(Enum):
    OPEN = 'o'
    LEFT = 'l'
    RIGHT = 'r'


class Hardware:
    def __init__(self, port_id: int, baud_rate: int = 115200):
        self._motor_state = MotorState.STOP
        self._servo_1_state = ServoState.OPEN
        self._servo_2_state = ServoState.OPEN
        self._servo_3_state = ServoState.OPEN

        self.serial = serial.Serial(str(f"/dev/ttyUSB{port_id}"), baud_rate)

    def __sync(self):
        self.serial.write(f"m{self._motor_state.value}".encode())

        self.serial.write(f"s{ServoState.OPEN}1".encode())
        self.serial.write(f"s{ServoState.OPEN}2".encode())
        self.serial.write(f"s{ServoState.OPEN}3".encode())

        self.serial.write(f"s{self._servo_1_state.value}1".encode())
        self.serial.write(f"s{self._servo_2_state.value}2".encode())
        self.serial.write(f"s{self._servo_3_state.value}3".encode())

    def to_json(self):
        return {
            "type": "sync",
            "motor": self._motor_state.value,
            "servo_1": self._servo_1_state.value,
            "servo_2": self._servo_2_state.value,
            "servo_3": self._servo_3_state.value
        }

    def __del__(self):
        self._motor_state = MotorState.STOP
        self._servo_1_state = ServoState.OPEN
        self._servo_2_state = ServoState.OPEN
        self._servo_3_state = ServoState.OPEN

        self.__sync()
        self.serial.close()

    @property
    def motor(self) -> MotorState:
        return self._motor_state

    @motor.setter
    def motor(self, value: MotorState):
        self._motor_state = value
        self.__sync()

    @property
    def servo_1(self) -> ServoState:
        return self._servo_1_state

    @servo_1.setter
    def servo_1(self, value: ServoState):
        self._servo_1_state = value
        self.__sync()

    @property
    def servo_2(self) -> ServoState:
        return self._servo_2_state

    @servo_2.setter
    def servo_2(self, value: ServoState):
        self._servo_2_state = value
        self.__sync()

    @property
    def servo_3(self) -> ServoState:
        return self._servo_3_state

    @servo_3.setter
    def servo_3(self, value: ServoState):
        self._servo_3_state = value
        self.__sync()


class Camera:
    def __init__(self, id: int):
        self.camera = cv2.VideoCapture(id)

        if not self.camera.isOpened():
            raise OSError("Could not open camera")

    def __del__(self):
        self.camera.release()

    async def generate_frames(self):
        try:
            print("Viewport stream opened")
            while True:
                success, frame = self.camera.read()
                if not success:
                    break
                else:
                    from ai import think
                    await think(frame)
                    ret, buffer = cv2.imencode('.jpg', frame)
                    frame_bytes = buffer.tobytes()

                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        finally:
            print("Viewport stream closed")


machine: Optional[Hardware] = None
camera: Optional[Camera] = None


def available_ports():
    devices = []

    for port in serial.tools.list_ports.comports():
        if port.device.__contains__("USB"):
            devices.append(int(port.device[11:]))

    return devices


def is_machine_connected() -> bool:
    global machine
    return machine is not None


def is_camera_connected() -> bool:
    global camera
    return camera is not None


async def connect_machine(port):
    global machine

    if is_machine_connected():
        raise ValueError("Machine already connected")

    machine = Hardware(port)
    await backend.Socket.send({
        "type": "connectedHw",
    })


async def connect_camera(port):
    global camera

    if is_camera_connected():
        raise ValueError("Camera already connected")

    camera = Camera(int(port))
    await backend.Socket.send({
        "type": "connectedCam",
    })


def abandon():
    global machine, camera

    if machine:
        del machine
        machine = None
    if camera:
        del camera
        camera = None


async def sync(data):
    global machine
    machine.motor = MotorState(data['motor'])
    machine.servo_1 = ServoState(data['servo_1'])
    machine.servo_2 = ServoState(data['servo_2'])
    machine.servo_3 = ServoState(data['servo_3'])

    await backend.Socket.send(machine.to_json())


def get_cameras():
    cams = []
    for path in glob.glob("/dev/video*"):
        m = re.search(r'\d+', path)
        if m:
            cams.append(int(m.group()))
    return sorted(cams)
