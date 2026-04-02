"""WebSocket module."""

from .compression import (
    WebSocketCompressor,
    CompressionConfig,
    CompressionAlgorithm,
    get_websocket_compressor,
)

__all__ = [
    "WebSocketCompressor",
    "CompressionConfig",
    "CompressionAlgorithm",
    "get_websocket_compressor",
]
