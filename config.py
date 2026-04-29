import json
import os
import pathlib
from pathlib import Path
from typing import Any

import parameters

config_pattern = {
    "ai": {
        "default_model": "",
        "scale": 1.0
    },
    "containers": [
        {
            "id": "1",
            "name": "Container 1",
            "ai": {
                "type": "",
                "model": ""
            },
            "color": {
                "r": {
                    "min": "0",
                    "max": "0"
                },
                "g": {
                    "min": "0",
                    "max": "0"
                },
                "b": {
                    "min": "0",
                    "max": "0"
                }
            },
            "size": {
                "width": {
                    "min": "0",
                    "max": "0"
                },
                "height": {
                    "min": "0",
                    "max": "0"
                }
            }
        },

        {
            "id": "2",
            "name": "Container 2",
            "ai": {
                "type": "",
                "model": ""
            },
            "color": {
                "r": {
                    "min": "0",
                    "max": "0"
                },
                "g": {
                    "min": "0",
                    "max": "0"
                },
                "b": {
                    "min": "0",
                    "max": "0"
                }
            },
            "size": {
                "width": {
                    "min": "0",
                    "max": "0"
                },
                "height": {
                    "min": "0",
                    "max": "0"
                }
            }
        },

        {
            "id": "3",
            "name": "Container 3",
            "ai": {
                "type": "",
                "model": ""
            },
            "color": {
                "r": {
                    "min": "0",
                    "max": "0"
                },
                "g": {
                    "min": "0",
                    "max": "0"
                },
                "b": {
                    "min": "0",
                    "max": "0"
                }
            },
            "size": {
                "width": {
                    "min": "0",
                    "max": "0"
                },
                "height": {
                    "min": "0",
                    "max": "0"
                }
            }
        },

        {
            "id": "4",
            "name": "Container 4",
            "ai": {
                "type": "",
                "model": ""
            },
            "color": {
                "r": {
                    "min": "0",
                    "max": "0"
                },
                "g": {
                    "min": "0",
                    "max": "0"
                },
                "b": {
                    "min": "0",
                    "max": "0"
                }
            },
            "size": {
                "width": {
                    "min": "0",
                    "max": "0"
                },
                "height": {
                    "min": "0",
                    "max": "0"
                }
            }
        },

        {
            "id": "5",
            "name": "Container 5",
            "ai": {
                "type": "",
                "model": ""
            },
            "color": {
                "r": {
                    "min": "0",
                    "max": "0"
                },
                "g": {
                    "min": "0",
                    "max": "0"
                },
                "b": {
                    "min": "0",
                    "max": "0"
                }
            },
            "size": {
                "width": {
                    "min": "0",
                    "max": "0"
                },
                "height": {
                    "min": "0",
                    "max": "0"
                }
            }
        },

        {
            "id": "6",
            "name": "Container 6",
            "ai": {
                "type": "",
                "model": ""
            },
            "color": {
                "r": {
                    "min": "0",
                    "max": "0"
                },
                "g": {
                    "min": "0",
                    "max": "0"
                },
                "b": {
                    "min": "0",
                    "max": "0"
                }
            },
            "size": {
                "width": {
                    "min": "0",
                    "max": "0"
                },
                "height": {
                    "min": "0",
                    "max": "0"
                }
            }
        }
    ]
}
config: Any


def read_config() -> None:
    import parameters as ai
    global config
    if os.path.isfile("config.json"):
        with open("config.json", "r") as read_file:
            config = json.load(read_file)
    else:
        create_config()
        with open("config.json", "r") as read_file:
            config = json.load(read_file)


def update_config(from_file=False):
    global config
    if not from_file:
        with open("config.json", "w") as write_file:
            json.dump(config, write_file, indent=4)
    else:
        with open("config.json", "r") as read_file:
            config = json.load(read_file)


def create_config():
    with open("config.json", "w") as write_file:
        json.dump(config_pattern, write_file)


def range_overlap(a, b):
    return a["min"] <= b["max"] and b["min"] <= a["max"]


def set_pixels_per_cm(scale):
    config["ai"]["scale"] = float(scale)
    update_config()


def find(type_, model, r, g, b, width, height):
    for c in config["containers"]:

        if c["ai"]["type"] != type_:
            continue
        if c["ai"]["model"] != model:
            continue

        if not (int(c["color"]["r"]["min"]) <= int(r) <= int(c["color"]["r"]["max"])):
            continue
        if not (int(c["color"]["g"]["min"]) <= int(g) <= int(c["color"]["g"]["max"])):
            continue
        if not (int(c["color"]["b"]["min"]) <= int(b) <= int(c["color"]["b"]["max"])):
            continue

        if not (int(c["size"]["width"]["min"]) <= int(width) <= int(c["size"]["width"]["max"])):
            continue
        if not (int(c["size"]["height"]["min"]) <= int(height) <= int(c["size"]["height"]["max"])):
            continue

        return c

    return None


def get_ai_available():
    return [p.name for p in pathlib.Path("models").glob("*.tflite")]


def get_ai_classes(model_name):
    if model_name == "":
        return []
    with open(f"models/{model_name}.txt", "r") as read_file:
        result = []
        for model_class in read_file.read().splitlines():
            result.append(model_class.split(" ")[1])
        return result


def get_default_model():
    return config["ai"]["default_model"]


def set_container(data):
    for c in range(len(config["containers"])):
        if str(config["containers"][c]["id"]) == str(data["id"]):
            config["containers"][c] = data
            break
    update_config()
