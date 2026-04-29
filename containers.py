import json
from pathlib import Path
from typing import Union

from asm.api.base import ContainerParameterType

from exceptions import ContainerExists, ContainerParameterExists, ContainerParameterDoesntExists, \
    ContainerDoesntExists

CONTAINERS_PATTERN = {
    "containers_parameters_preset": [],
    "containers_parameters_configuration": []
}
containers: dict


def load_containers():
    global containers
    try:
        with open("containers.json", "x"):
            containers = CONTAINERS_PATTERN.copy()
        _update_local_containers()
    except FileExistsError:
        with open("containers.json", "r") as f:
            containers = json.load(f)
    _sync_containers_with_preset()


def add_container(name: str) -> int:
    """
    Adds a container

    :param name: Name of the container
    :raises ContainerExists: Raised if the container already exists
    :return: Container ID
    """
    if _container_exists(name):
        raise ContainerExists
    container = {"name": name}

    containers["containers_parameters_configuration"].append(container)
    _sync_containers_with_preset()
    _update_local_containers()

    return len(containers["containers_parameters_configuration"]) - 1


def get_container(container: Union[str, int]):
    if not _container_exists(container):
        raise ContainerDoesntExists
    if isinstance(container, int):
        return containers["containers_parameters_configuration"][container]
    elif isinstance(container, str):
        for c in containers["containers_parameters_configuration"]:
            if c["name"] == container:
                return c
    raise ContainerDoesntExists


def update_container(container: Union[str, int], data: dict):
    if not _container_exists(container):
        raise ContainerDoesntExists
    if isinstance(container, int):
        containers["containers_parameters_configuration"][container].update(data)
    elif isinstance(container, str):
        for c in containers["containers_parameters_configuration"]:
            if c["name"] == container:
                c.update(data)
                break

    _update_local_containers()


def remove_container(container: Union[str, int]):
    """
    Removes a container

    :param container: Name or ID of container
    :raises ContainerDoesntExists: Raised if the container already exists
    :return: Container ID
    """
    if not _container_exists(container):
        raise ContainerDoesntExists
    if isinstance(container, int):
        containers["containers_parameters_configuration"].pop(container)
    elif isinstance(container, str):
        containers["containers_parameters_configuration"] = [
            c for c in containers["containers_parameters_configuration"]
            if c.get("name") != container
        ]

    _update_local_containers()


def add_parameter(parameter_name: str, parameter_type: ContainerParameterType) -> Union[ContainerParameterExists, None]:
    """
    Adds container parameter

    :param parameter_type: Parameter Type (RANGE, STRING, TOGGLE)
    :param parameter_name: Parameter ID
    :raises ContainerParameterExists: Raised if the parameter already added
    """
    if any(p["name"] == parameter_name for p in containers["containers_parameters_preset"]):
        raise ContainerParameterExists
    containers["containers_parameters_preset"].append({
        "name": parameter_name,
        "type": parameter_type.value,
        "enabled": True if not "baseai" in parameter_name else False
    })
    _update_local_containers()
    _sync_containers_with_preset()


def remove_parameter(parameter_name: str):
    """
    Removes container parameter

    :param parameter_name: Parameter ID
    :raises ContainerParameterDoesntExists: Raised if the parameter doesn't exist
    """
    if not any(p["name"] == parameter_name for p in containers["containers_parameters_preset"]):
        raise ContainerParameterDoesntExists
    for container in containers["containers_parameters_preset"]:
        if container["name"] == parameter_name:
            containers["containers_parameters_preset"].remove(container)
    _cleanup_deprecated_parameters()
    _update_local_containers()


def _container_exists(container: Union[int, str]) -> bool:
    if isinstance(container, int):
        return 0 <= container < len(containers["containers_parameters_configuration"])
    elif isinstance(container, str):
        for c in containers["containers_parameters_configuration"]:
            if c["name"] == container:
                return True
    return False


def _cleanup_deprecated_parameters():
    """
    Clean up removed from preset parameters in containers
    """
    valid_params = {p["name"] for p in containers["containers_parameters_preset"]}

    for container in containers["containers_parameters_configuration"]:
        keys_to_remove = [
            key for key in container
            if key != "name" and key not in valid_params
        ]

        for key in keys_to_remove:
            del container[key]

    _update_local_containers()


def _update_local_containers():
    """
    Updates containers.json
    """
    with open("containers.json", "w") as f:
        f.write(json.dumps(containers, indent=4))


def active_ai(module):
    import engine
    module_id = engine.get_id_by_module(module)
    allowed: list[str] = []
    with open(f"modules/data/{module_id}.json", "rb") as f:
        json_data = json.load(f)
        for parameter in json_data["parameters"]:
            if parameter["name"] == "baseAI":
                for param in parameter["parameters"]:
                    allowed.append(param["id"])
    for preset in containers["containers_parameters_preset"]:
        if "baseai" in preset["name"]:
            if preset["name"] not in allowed:
                preset["enabled"] = False
            else:
                preset["enabled"] = True
    _update_local_containers()


def _sync_containers_with_preset():
    for container in containers["containers_parameters_configuration"]:
        for preset in containers["containers_parameters_preset"]:
            name = preset["name"]
            p_type = preset["type"]

            if name not in container:
                if p_type == "range":
                    container[name] = {
                        "min": 0,
                        "max": 1
                    }
                elif p_type == "string":
                    container[name] = ""
                elif p_type == "toggle":
                    container[name] = True

    _update_local_containers()


def get_containers_count():
    return len(containers["containers_parameters_configuration"])


def get_containers_preset():
    result = []

    for container in containers["containers_parameters_preset"]:
        for module in Path("modules/data").iterdir():
            if container["name"].startswith(module.name.split(".")[0]):
                with open(module, "r", encoding="utf-8") as f:
                    current_module = json.load(f)
        for param in current_module["parameters"]:
            for param1 in param["parameters"]:
                if param1["id"] == container["name"]:
                    group_name = param["name"]
                    group_id = param["id"]
                    group_type = param["type"]
                    param_name = param1["name"]
                    module_name = current_module["name"],
                    module_id = current_module["id"]
        result.append({
            "group": {
                "id": group_id,
                "name": group_name,
                "type": group_type
            },
            "name": param_name,
            "id": container["name"],
            "enabled": container["enabled"],
            "module": module_name,
            "moduleId": module_id
        })
    return result


def find_container(results):
    for idx, container in enumerate(containers["containers_parameters_configuration"]):
        ok = True

        for key, value in results.items():
            if key not in container:
                continue

            rule = container[key]

            if isinstance(rule, dict):
                min_v = rule.get("min", float("-inf"))
                max_v = rule.get("max", float("inf"))

                if not (min_v <= value <= max_v):
                    ok = False
                    break

            else:
                if rule != "" and rule != value:
                    ok = False
                    break

        if ok:
            return idx, container["name"]

    return None
