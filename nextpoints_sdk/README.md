# nextpoints-sdk

Shared data models and simple synchronous service protocol client between NextPoints and its ML backend.

MVP scope:

- Pydantic models for project metadata, annotations, calibration.
- Synchronous HTTP client (httpx) for three service endpoints: pre-annotation, reconstruction, calibration.
- Minimal error and artifact models.

## Install (local)

```
pip install -e .
```

## Run tests

```
pytest -q
```

## Basic Usage

```python
from nextpoints_sdk.client.services import ServicesClient
from nextpoints_sdk.models.requests import PreAnnotationRequest
# build project_meta ...
client = ServicesClient(base_url="http://ml-backend:8000", api_key="your-key")
resp = client.pre_annotate(PreAnnotationRequest(project_meta=project_meta))
print(resp.annotations.keys())
```

This is an early skeleton. Models will be filled incrementally.
