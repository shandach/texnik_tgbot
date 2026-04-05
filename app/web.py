from __future__ import annotations

import importlib
import importlib.util


def get_web_components():
    if importlib.util.find_spec("fastapi"):
        fastapi = importlib.import_module("fastapi")
        responses = importlib.import_module("fastapi.responses")
        return fastapi.FastAPI, fastapi.Query, responses.JSONResponse

    shim = importlib.import_module("app.fastapi_shim")
    return shim.FastAPI, shim.Query, shim.JSONResponse
