import importlib
import inspect
import json
import re
import shutil
import subprocess
import sys
from importlib import metadata
import importlib.abc
from typing import Union, Any
from unittest.mock import MagicMock

from asm.api.ai import ASMAI
from asm.api.base import ASMBase, ModuleType, ModuleConfiguration, ModuleRequirement, ModuleRequirementVersionPolicy, \
    ModuleInformation
from asm.api.cv import ASMDetector, ASMOpenCV
from asm.api.hardware import ASMHardware
from asm.exceptions import ModuleAlreadyRegistered, ModuleRequirementsConflict, ModuleRequirementsNotFound

from asm.logman import *

import core

ai: ASMAI
hw: ASMHardware
od: ASMDetector
cvs: list[ASMOpenCV]


def logo():
    log("===========================================================")
    log("=     ___   _____ __  ___   ______            _           =")
    log("=    /   | / ___//  |/  /  / ____/___  ____ _(_)___  ___  =")
    log("=   / /| | \__ \/ /|_/ /  / __/ / __ \/ __ `/ / __ \/ _ \\ =")
    log("=  / ___ |___/ / /  / /  / /___/ / / / /_/ / / / / /  __/ =")
    log("= /_/  |_/____/_/  /_/  /_____/_/ /_/\__, /_/_/ /_/\___/  =")
    log("=                                   /____/                =")
    log("===========================================================")


def discover_modules(source_file: Path):
    loaded_modules = []

    module_name = source_file.stem
    spec = importlib.util.spec_from_file_location(module_name, source_file)

    original_modules = sys.modules.copy()

    class ImportMocker(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(self, fullname, path, target=None):
            if fullname not in sys.modules:
                return importlib.util.spec_from_loader(fullname, self)
            return None

        def create_module(self, spec):
            module = MagicMock()
            module.__path__ = []
            sys.modules[spec.name] = module
            return module

        def exec_module(self, module):
            pass

    mocker = ImportMocker()
    sys.meta_path.insert(0, mocker)

    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for cls_name, cls_obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls_obj, ASMBase) and not inspect.isabstract(cls_obj):
                loaded_modules.append(cls_obj())

    return loaded_modules, original_modules, mocker


def register_modules(source_file: Path):
    check_modules_folder()
    modules, original_modules, mocker = discover_modules(source_file)
    for module in modules:
        module_info: ModuleInformation = module.module_info()

        module_type: ModuleType = ModuleType.Hardware if ("ASMHardware" in str(type(module).__bases__[0])) else (
            ModuleType.AI if ("ASMAI" in str(type(module).__bases__[0])) else (
                ModuleType.ObjectDetector if ("ASMDetector" in str(type(module).__bases__[0])) else ModuleType.OpenCV))
        module_id: str = get_id_by_display_name(
            f"{module_type.value}_{source_file.name.split('.')[0]}_{module_info.name}")

        if Path(f"modules/data/{module_id}.json").exists():
            raise ModuleAlreadyRegistered(module_id)

        module_source: str = source_file.name
        module_name: str = module_info.name
        module_version: str = module_info.version
        module_configuration: ModuleConfiguration = module_info.configuration_pattern

        module_information: dict = {
            "name": module_name,
            "id": module_id,
            "version": module_version,
            "type": module_type.value,
            "source": module_source,
            "requirements": module_requirements_install(module_info.requirements),
            "configuration": check_configuration_pattern(module_configuration)
        }

        if not Path(f"modules/sources/{module_source}").exists():
            shutil.copyfile(source_file, Path(f"modules/data/{module_source}"))

        with open(Path(f"modules/data/{module_id}.json"), "x", encoding="utf-8") as f:
            f.write(json.dumps(module_information, indent=4))

    sys.meta_path.remove(mocker)
    for name in list(sys.modules.keys()):
        if name not in original_modules:
            del sys.modules[name]


def module_requirements_install(requirements: list[ModuleRequirement]):
    dists = metadata.distributions()
    total_requirements: list[str] = []
    log(f"Installing requirements...")
    if requirements is None:
        log(f"No requirements found. Skipping all...")
        return []

    for requirement in requirements:
        for dist in dists:
            if requirement.name == dist.metadata[
                'Name'] and requirement.policy == ModuleRequirementVersionPolicy.EQUAL and requirement.version != \
                    dist.metadata['Version']:
                raise ModuleRequirementsConflict(requirement.name)

        log(f"Installing {requirement.name}...")
        version_str: str = ""
        if requirement.policy != ModuleRequirementVersionPolicy.ANY:
            version_str += f"=={requirement.version}"

        command = [sys.executable, "-m", "pip", "install", f"{requirement.name}{version_str}"]

        result = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in result.stdout:
            log(line.strip(), LogType.PIP)

        result.wait()

        if result.returncode == 0:
            log(f"{requirement.name} successfully installed")
        elif result.returncode == 1:
            if "network" in result.stderr.lower():
                log(f"{requirement.name} failed to install! No internet connection", log_type=LogType.ERROR)
                raise ConnectionError(requirement.name)
            elif "not found" in result.stderr.lower():
                log(f"{requirement.name} failed to install! Module not found", log_type=LogType.ERROR)
                raise ModuleRequirementsNotFound(requirement.name)
            else:
                log(f"{requirement.name} failed to install!", log_type=LogType.ERROR)
                raise OSError(result.stderr)

        total_requirements.append(f"{requirement.name}{version_str}")

    return total_requirements


def check_configuration_pattern(module_configuration: Union[ModuleConfiguration, None]) -> str:
    if module_configuration is None:
        return json.dumps({}, indent=4)
    configuration: dict = module_configuration.configuration
    return json.dumps(configuration, indent=4)


def unregister_module(module_id: str):
    Path(f"modules/data/{module_id}.json").unlink(missing_ok=True)


def load_module(module_id: str) -> Union[Any, None]:
    with open(Path(f"modules/data/{module_id}.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
    module_source: str = data["source"]
    modules = discover_modules(Path(f"modules/sources/{module_source}"))
    for module in modules:
        if get_id_by_display_name(
                f"{data['type']}_{module_source.split('.')[0]}_{module.module_info().name}") == module_id:
            return module
    return None


def load_default_modules():
    log(f"Loading default modules")
    try:
        with open(Path(f"modules/default_modules.json"), "x", encoding="utf-8") as f:
            f.write(json.dumps({
                "hw": "",
                "ai": "",
                "od": "",
                "cv": []
            }, indent=4))
        log(f"Default modules not found, skipping all...")
        return
    except FileExistsError:
        with open(Path(f"modules/default_modules.json"), "r", encoding="utf-8") as f:
            defaults_config: dict = json.load(f)

    log(f"Loading default HW module")
    if defaults_config["hw"]:
        load_module(defaults_config["hw"])
        log(f"HW modules loaded!")
    else:
        log(f"HW module not found, skipping...")

    log(f"Loading default AI module")
    if defaults_config["ai"]:
        load_module(defaults_config["ai"])
        log(f"AI modules loaded!")
    else:
        log(f"AI module not found, skipping...")

    log(f"Loading default OD module")
    if defaults_config["od"]:
        load_module(defaults_config["od"])
        log(f"OD modules loaded!")
    else:
        log(f"OD module not found, skipping...")

    log(f"Loading default CV modules")
    cv_count: int = len(defaults_config['cv'])
    log(f"CV modules count: {cv_count}")
    for cv_module in defaults_config["cv"]:
        load_module(cv_module)
    if cv_count > 0:
        log(f"CV modules loaded!")
    else:
        log(f"CV modules not found, skipping...")
    log(f"Default modules loaded!")


def check_modules_folder():
    Path("modules/sources").mkdir(parents=True, exist_ok=True)
    Path("modules/data").mkdir(parents=True, exist_ok=True)


def init():
    logo()
    check_modules_folder()
    load_default_modules()

    core.init_fastapi()


def stop():
    stop_logger()


def get_id_by_display_name(display_name: str) -> str:
    return re.sub(r'[\\/*?:"<>| ]', '_', display_name)
