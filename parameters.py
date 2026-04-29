import asyncio
import json
from pathlib import Path
from typing import Optional

from asm import logman
from asm.api.base import ContainerParameterType, ContainerParameterResults
from asm.api.cv import DetectedObject, FrameType

import backend
import containers
import engine

allow_control: bool = False
object_found: bool = False
calibration: float = False


async def think(frame):
    from engine import ai, od, hw
    global object_found

    real_object = await od.process(frame)

    results = {}
    ai_state = True
    hw_state = True

    if real_object is not None and real_object.detected and not object_found:
        object_found = True
        object_frame = frame[
            real_object.ymin:real_object.ymax,
            real_object.xmin:real_object.xmax
        ]

        try:
            ai_result, ai_parameters = await asyncio.to_thread(ai.process, frame)
        except Exception:
            ai_state = False

        try:
            hw_results = await asyncio.to_thread(hw.process)
            if hw_results is None:
                hw_state = False
        except Exception:
            hw_state = False

        if ai_state:
            results.update({
                f"{engine.get_id_by_module(ai)}_baseai_model":
                    ai_result.model.split('.')[0] if ai_result else "NIAY",
                f"{engine.get_id_by_module(ai)}_baseai_class":
                    ai_result.label if ai_result else "NIAY"
            })

        if hw_state:
            for hw_res in hw_results:
                results.update(get_parameter_normal(hw_res, engine.get_id_by_module(hw)))
        if ai_state:
            for ai_res in ai_parameters:
                results.update(get_parameter_normal(ai_res, engine.get_id_by_module(ai)))

        for cv in engine.cvs:
            module_id = engine.get_id_by_module(cv)

            cv_input = object_frame if cv.frame_type() == FrameType.OBJECT else frame

            cv_results = await cv.process(cv_input)

            for cv_result in cv_results:
                results.update(get_parameter_normal(cv_result, module_id))

        preset = containers.get_containers_preset()
        for pres in preset:
            if not pres["enabled"]:
                continue
            if pres["id"] not in results:
                if pres["group"]["type"] == ContainerParameterType.STRING.value:
                    results.update({pres["id"]: "NIAY"})
                if pres["group"]["type"] == ContainerParameterType.RANGE.value:
                    results.update({pres["id"]: -1})

        results.update({
            "container": containers.find_container(results)
        })
        if allow_control:
            await backend.Socket.send(hw.set_container(results["container"][0]))
        await backend.Socket.send({"type": "parameter", "parameters": results})

    elif real_object is None or (not real_object.detected and object_found):
        object_found = False


def get_parameter_normal(result: ContainerParameterResults, module_id: str) -> dict:
    active_name: str = engine.get_id_by_display_name(
        f"{module_id}_{result.parameter.group.name}_{result.parameter.name}")
    if result.parameter.group.parameter_type is ContainerParameterType.STRING:
        return {active_name: str(result.result)}
    if result.parameter.group.parameter_type is ContainerParameterType.RANGE:
        return {active_name: int(result.result)}
    if result.parameter.group.parameter_type is ContainerParameterType.TOGGLE:
        return {active_name: bool(result.result)}
    raise NotImplementedError


async def ai_load_model(model: Path, labels: Optional[Path] = None):
    from engine import ai
    ai.load(model, labels)
    await backend.Socket.send({
        "type": "modelUse"
    })


def ai_unload_model():
    from engine import ai
    ai.unload()


def get_models() -> list[str]:
    import engine

    expansions = engine.ai.expansions().model_expansion
    current_ai_id = engine.get_id_by_module(engine.ai)
    base_path = Path("models").joinpath(current_ai_id)
    result = []
    for file in base_path.iterdir():
        if file.name.split('.')[-1] in expansions:
            result.append(file.name)
    return result


def find_model(data: str) -> Path:
    import engine

    expansions = engine.ai.expansions().model_expansion
    current_ai_id = engine.get_id_by_module(engine.ai)
    base_path = Path("models").joinpath(current_ai_id)

    for ext in expansions:
        for file in base_path.glob(f"{data}.{ext}"):
            return file

    raise FileNotFoundError


def find_label(data: str) -> Optional[Path]:
    import engine

    expansions = engine.ai.expansions().labels_expansion
    current_ai_id = engine.get_id_by_module(engine.ai)
    base_path = Path("models").joinpath(current_ai_id)
    if expansions is None:
        return None
    for ext in expansions:
        for file in base_path.glob(f"{data}.{ext}"):
            return file

    raise FileNotFoundError
