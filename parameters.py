from asm.api.base import ContainerParameterType
from asm.api.cv import DetectedObject, FrameType

import engine
from engine import ai, od, hw

allow_control: bool = False
object_found: bool = False
calibration: float = False


async def think(frame):
    global object_found, calibration

    real_object: DetectedObject = await od.process(frame)

    if real_object.detected and not object_found:
        object_frame = frame[real_object.ymin:real_object.ymax, real_object.xmin:real_object.xmax]

        results = {}

        ai_result, ai_parameters = ai.process(frame)
        hw_results = hw.process()

        for cv in engine.cvs:
            module_id = engine.get_id_by_module(cv)

            if cv.frame_type() == FrameType.OBJECT:
                cv_results = await cv.process(object_frame)
            else:
                cv_results = await cv.process(frame)

            for cv_result in cv_results:
                results.update({f"{module_id}_{cv_result.parameter.group.name}_{cv_result.parameter.name}": str(
                    cv_result.result) if cv_result.parameter.group.parameter_type is ContainerParameterType.STRING else float(
                    cv_result.result)})


    elif not real_object.detected and object_found:
        object_found = False


def ai_load_model(model, labels):
    ai.load(model, labels)

def ai_unload_model():
    ai.unload()
