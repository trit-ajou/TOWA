"""Model adapter interfaces."""

from .base import ModelAdapter
from .callable import CallableModelAdapter
from .container_worker import ContainerWorkerModelAdapter
from .http_api import HttpApiModelAdapter

__all__ = ["CallableModelAdapter", "ContainerWorkerModelAdapter", "HttpApiModelAdapter", "ModelAdapter"]
