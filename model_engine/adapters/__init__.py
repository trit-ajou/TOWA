"""Model adapter interfaces."""

from .base import ModelAdapter
from .callable import CallableModelAdapter
from .http_api import HttpApiModelAdapter

__all__ = ["CallableModelAdapter", "HttpApiModelAdapter", "ModelAdapter"]
