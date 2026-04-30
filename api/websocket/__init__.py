"""WebSocket module."""

from .compression import (
    CompressionAlgorithm,
    CompressionConfig,
    WebSocketCompressor,
    get_websocket_compressor,
)

__all__ = [
    "WebSocketCompressor",
    "CompressionConfig",
    "CompressionAlgorithm",
    "get_websocket_compressor",
]
