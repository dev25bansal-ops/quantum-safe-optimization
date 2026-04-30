"""
WebSocket Compression Module.

Provides compression for large WebSocket payloads:
- Per-message compression using zlib
- Threshold-based compression
- Client capability negotiation
- Compression metrics
"""

import gzip
import logging
import struct
import zlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CompressionAlgorithm(str, Enum):
    """Supported compression algorithms."""

    ZLIB = "zlib"
    GZIP = "gzip"
    DEFLATE = "deflate"


@dataclass
class CompressionConfig:
    """Configuration for WebSocket compression."""

    enabled: bool = True
    threshold_bytes: int = 1024
    level: int = 6
    algorithm: CompressionAlgorithm = CompressionAlgorithm.ZLIB
    max_uncompressed_size: int = 10 * 1024 * 1024


@dataclass
class CompressionMetrics:
    """Metrics for compression performance."""

    messages_compressed: int = 0
    messages_uncompressed: int = 0
    total_bytes_before: int = 0
    total_bytes_after: int = 0
    compression_errors: int = 0

    @property
    def compression_ratio(self) -> float:
        if self.total_bytes_before == 0:
            return 0.0
        return self.total_bytes_after / self.total_bytes_before

    @property
    def bytes_saved(self) -> int:
        return self.total_bytes_before - self.total_bytes_after


class WebSocketCompressor:
    """
    Compressor for WebSocket messages.

    Features:
    - Threshold-based compression (only compress large messages)
    - Multiple algorithms (zlib, gzip, deflate)
    - Compression negotiation
    - Metrics tracking
    """

    def __init__(self, config: CompressionConfig | None = None):
        self.config = config or CompressionConfig()
        self._metrics = CompressionMetrics()
        self._compressors: dict[str, Any] = {}

    def compress(self, data: bytes) -> tuple[bytes, bool]:
        """
        Compress data if above threshold.

        Returns:
            Tuple of (compressed_data, was_compressed)
        """
        if not self.config.enabled:
            return data, False

        if len(data) < self.config.threshold_bytes:
            self._metrics.messages_uncompressed += 1
            return data, False

        try:
            if self.config.algorithm == CompressionAlgorithm.ZLIB:
                compressed = zlib.compress(data, self.config.level)
            elif self.config.algorithm == CompressionAlgorithm.GZIP:
                compressed = gzip.compress(data, self.config.level)
            elif self.config.algorithm == CompressionAlgorithm.DEFLATE:
                compressor = zlib.compressobj(
                    self.config.level,
                    zlib.DEFLATED,
                    -zlib.MAX_WBITS,
                )
                compressed = compressor.compress(data) + compressor.flush()
            else:
                return data, False

            if len(compressed) >= len(data):
                self._metrics.messages_uncompressed += 1
                return data, False

            self._metrics.messages_compressed += 1
            self._metrics.total_bytes_before += len(data)
            self._metrics.total_bytes_after += len(compressed)

            return compressed, True

        except Exception as e:
            logger.error(f"Compression error: {e}")
            self._metrics.compression_errors += 1
            return data, False

    def decompress(self, data: bytes, compressed: bool) -> bytes:
        """Decompress data."""
        if not compressed:
            return data

        try:
            if self.config.algorithm == CompressionAlgorithm.ZLIB:
                return zlib.decompress(data)
            elif self.config.algorithm == CompressionAlgorithm.GZIP:
                return gzip.decompress(data)
            elif self.config.algorithm == CompressionAlgorithm.DEFLATE:
                decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
                return decompressor.decompress(data)
            else:
                return data

        except Exception as e:
            logger.error(f"Decompression error: {e}")
            self._metrics.compression_errors += 1
            raise

    def compress_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Compress a JSON message.

        Adds compression metadata to message:
        - compressed: bool
        - algorithm: str (if compressed)
        - original_size: int (if compressed)
        """
        import json

        data = json.dumps(message).encode("utf-8")

        if len(data) < self.config.threshold_bytes:
            return message

        compressed_data, was_compressed = self.compress(data)

        if not was_compressed:
            return message

        return {
            "__compressed__": True,
            "__algorithm__": self.config.algorithm.value,
            "__original_size__": len(data),
            "__data__": compressed_data.hex(),
        }

    def decompress_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Decompress a compressed message."""
        import json

        if not message.get("__compressed__"):
            return message

        try:
            compressed_data = bytes.fromhex(message["__data__"])
            decompressed = self.decompress(compressed_data, True)
            return json.loads(decompressed.decode("utf-8"))
        except Exception as e:
            logger.error(f"Message decompression error: {e}")
            return message

    def get_metrics(self) -> dict[str, Any]:
        """Get compression metrics."""
        return {
            "enabled": self.config.enabled,
            "algorithm": self.config.algorithm.value,
            "threshold_bytes": self.config.threshold_bytes,
            "level": self.config.level,
            "messages_compressed": self._metrics.messages_compressed,
            "messages_uncompressed": self._metrics.messages_uncompressed,
            "total_bytes_before": self._metrics.total_bytes_before,
            "total_bytes_after": self._metrics.total_bytes_after,
            "bytes_saved": self._metrics.bytes_saved,
            "compression_ratio": round(self._metrics.compression_ratio, 4),
            "compression_errors": self._metrics.compression_errors,
        }


class BinaryMessageProtocol:
    """
    Binary message protocol for efficient WebSocket communication.

    Format:
    - Byte 0: Flags (bit 0: compressed, bit 1-2: algorithm)
    - Bytes 1-4: Message length (uint32, big endian)
    - Bytes 5+: Message data
    """

    FLAG_COMPRESSED = 0x01
    FLAG_ALGORITHM_MASK = 0x06
    FLAG_ALGORITHM_ZLIB = 0x00
    FLAG_ALGORITHM_GZIP = 0x02
    FLAG_ALGORITHM_DEFLATE = 0x04

    @staticmethod
    def encode(data: bytes, compressed: bool, algorithm: int = 0) -> bytes:
        """Encode data with protocol header."""
        flags = 0
        if compressed:
            flags |= BinaryMessageProtocol.FLAG_COMPRESSED
            flags |= algorithm

        length = len(data)
        header = struct.pack(">BI", flags, length)

        return header + data

    @staticmethod
    def decode(data: bytes) -> tuple[bytes, bool, int]:
        """Decode data from protocol format."""
        if len(data) < 5:
            raise ValueError("Message too short")

        flags, length = struct.unpack(">BI", data[:5])

        if len(data) < 5 + length:
            raise ValueError("Message truncated")

        compressed = bool(flags & BinaryMessageProtocol.FLAG_COMPRESSED)
        algorithm = flags & BinaryMessageProtocol.FLAG_ALGORITHM_MASK

        return data[5 : 5 + length], compressed, algorithm


@dataclass
class CompressionNegotiation:
    """Result of compression negotiation."""

    compression_enabled: bool
    algorithm: CompressionAlgorithm | None
    client_supports: list[str] = field(default_factory=list)


def negotiate_compression(
    client_extensions: list[str] | None = None,
) -> CompressionNegotiation:
    """
    Negotiate compression with client.

    WebSocket extension negotiation per RFC 7692.
    """
    if not client_extensions:
        return CompressionNegotiation(
            compression_enabled=False,
            algorithm=None,
            client_supports=[],
        )

    supported = []
    for ext in client_extensions:
        ext_lower = ext.lower()
        if "permessage-deflate" in ext_lower:
            supported.append("deflate")
        elif "permessage-gzip" in ext_lower:
            supported.append("gzip")

    if not supported:
        return CompressionNegotiation(
            compression_enabled=False,
            algorithm=None,
            client_supports=[],
        )

    algorithm = (
        CompressionAlgorithm.DEFLATE if "deflate" in supported else CompressionAlgorithm.GZIP
    )

    return CompressionNegotiation(
        compression_enabled=True,
        algorithm=algorithm,
        client_supports=supported,
    )


_websocket_compressor: WebSocketCompressor | None = None


def get_websocket_compressor() -> WebSocketCompressor:
    """Get or create the global WebSocket compressor."""
    global _websocket_compressor
    if _websocket_compressor is None:
        config = CompressionConfig(
            enabled=True,
            threshold_bytes=1024,
            level=6,
            algorithm=CompressionAlgorithm.ZLIB,
        )
        _websocket_compressor = WebSocketCompressor(config)
    return _websocket_compressor
