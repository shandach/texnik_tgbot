from __future__ import annotations


class JSONResponse(dict):
    def __init__(self, status_code: int, content: dict):
        super().__init__(content)
        self.status_code = status_code


class _RouteDecorator:
    def __init__(self, registry: list[dict], method: str, path: str, response_model=None):
        self.registry = registry
        self.method = method
        self.path = path
        self.response_model = response_model

    def __call__(self, fn):
        self.registry.append(
            {
                "method": self.method,
                "path": self.path,
                "handler": fn.__name__,
                "response_model": getattr(self.response_model, "__name__", str(self.response_model)),
            }
        )
        return fn


class FastAPI:
    def __init__(self, title: str, version: str):
        self.title = title
        self.version = version
        self.routes: list[dict] = []

    def post(self, path: str, response_model=None):
        return _RouteDecorator(self.routes, "POST", path, response_model=response_model)

    def get(self, path: str, response_model=None):
        return _RouteDecorator(self.routes, "GET", path, response_model=response_model)

    def put(self, path: str, response_model=None):
        return _RouteDecorator(self.routes, "PUT", path, response_model=response_model)


def Query(*, default, ge=None, le=None):
    return default
