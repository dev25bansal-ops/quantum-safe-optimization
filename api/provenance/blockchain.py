"""
Algorithm Provenance and Blockchain Integration.

Tracks algorithm lineage, versions, and execution history with immutable records.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class ProvenanceEventType(str, Enum):
    ALGORITHM_CREATED = "algorithm_created"
    ALGORITHM_UPDATED = "algorithm_updated"
    ALGORITHM_EXECUTED = "algorithm_executed"
    RESULT_GENERATED = "result_generated"
    RESULT_VALIDATED = "result_validated"
    ALGORITHM_PUBLISHED = "algorithm_published"
    ALGORITHM_PURCHASED = "algorithm_purchased"
    KEY_ROTATED = "key_rotated"


@dataclass
class ProvenanceBlock:
    block_id: str
    previous_hash: str
    timestamp: datetime
    event_type: ProvenanceEventType
    algorithm_id: str
    user_id: str
    data: dict[str, Any]
    signature: str = ""
    nonce: int = 0
    hash: str = ""

    def compute_hash(self) -> str:
        block_data = {
            "block_id": self.block_id,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "algorithm_id": self.algorithm_id,
            "user_id": self.user_id,
            "data": self.data,
            "nonce": self.nonce,
        }
        block_string = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine(self, difficulty: int = 4) -> None:
        target = "0" * difficulty
        while True:
            self.hash = self.compute_hash()
            if self.hash.startswith(target):
                break
            self.nonce += 1

    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "algorithm_id": self.algorithm_id,
            "user_id": self.user_id,
            "data": self.data,
            "signature": self.signature,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProvenanceBlock":
        return cls(
            block_id=data["block_id"],
            previous_hash=data["previous_hash"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=ProvenanceEventType(data["event_type"]),
            algorithm_id=data["algorithm_id"],
            user_id=data["user_id"],
            data=data["data"],
            signature=data.get("signature", ""),
            nonce=data.get("nonce", 0),
            hash=data.get("hash", ""),
        )


@dataclass
class AlgorithmLineage:
    algorithm_id: str
    name: str
    version: str
    author_id: str
    created_at: datetime
    parent_ids: list[str] = field(default_factory=list)
    children_ids: list[str] = field(default_factory=list)
    execution_count: int = 0
    last_executed_at: Optional[datetime] = None
    checksum: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "algorithm_id": self.algorithm_id,
            "name": self.name,
            "version": self.version,
            "author_id": self.author_id,
            "created_at": self.created_at.isoformat(),
            "parent_ids": self.parent_ids,
            "children_ids": self.children_ids,
            "execution_count": self.execution_count,
            "last_executed_at": self.last_executed_at.isoformat()
            if self.last_executed_at
            else None,
            "checksum": self.checksum,
            "tags": self.tags,
        }


class ProvenanceChain:
    """Blockchain for algorithm provenance tracking."""

    GENESIS_HASH = "0" * 64
    DIFFICULTY = 4

    def __init__(self):
        self._chain: list[ProvenanceBlock] = []
        self._lineages: dict[str, AlgorithmLineage] = {}
        self._pending_blocks: list[ProvenanceBlock] = []

        self._create_genesis_block()

    def _create_genesis_block(self) -> None:
        genesis = ProvenanceBlock(
            block_id="genesis",
            previous_hash=self.GENESIS_HASH,
            timestamp=datetime.now(timezone.utc),
            event_type=ProvenanceEventType.ALGORITHM_CREATED,
            algorithm_id="genesis",
            user_id="system",
            data={"message": "Genesis block for quantum algorithm provenance"},
        )
        genesis.mine(self.DIFFICULTY)
        self._chain.append(genesis)

    def get_last_block(self) -> ProvenanceBlock:
        return self._chain[-1]

    def add_block(
        self,
        event_type: ProvenanceEventType,
        algorithm_id: str,
        user_id: str,
        data: dict[str, Any],
        sign_func: Optional[callable] = None,
    ) -> ProvenanceBlock:
        """Add a new block to the chain."""
        previous_block = self.get_last_block()

        block = ProvenanceBlock(
            block_id=f"block_{uuid4().hex[:12]}",
            previous_hash=previous_block.hash,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            algorithm_id=algorithm_id,
            user_id=user_id,
            data=data,
        )

        if sign_func:
            block_data_to_sign = json.dumps(
                {
                    "event_type": event_type.value,
                    "algorithm_id": algorithm_id,
                    "user_id": user_id,
                    "timestamp": block.timestamp.isoformat(),
                },
                sort_keys=True,
            )
            block.signature = sign_func(block_data_to_sign)

        block.mine(self.DIFFICULTY)

        self._chain.append(block)

        self._update_lineage(event_type, algorithm_id, user_id, data)

        logger.info(
            "provenance_block_added",
            block_id=block.block_id,
            event_type=event_type.value,
            algorithm_id=algorithm_id,
        )

        return block

    def _update_lineage(
        self,
        event_type: ProvenanceEventType,
        algorithm_id: str,
        user_id: str,
        data: dict,
    ) -> None:
        """Update algorithm lineage tracking."""
        if algorithm_id == "genesis":
            return

        if algorithm_id not in self._lineages:
            lineage = AlgorithmLineage(
                algorithm_id=algorithm_id,
                name=data.get("name", "Unknown"),
                version=data.get("version", "1.0.0"),
                author_id=user_id,
                created_at=datetime.now(timezone.utc),
                checksum=data.get("checksum", ""),
                tags=data.get("tags", []),
            )
            self._lineages[algorithm_id] = lineage

        lineage = self._lineages[algorithm_id]

        if event_type == ProvenanceEventType.ALGORITHM_EXECUTED:
            lineage.execution_count += 1
            lineage.last_executed_at = datetime.now(timezone.utc)

        elif event_type == ProvenanceEventType.ALGORITHM_UPDATED:
            lineage.version = data.get("new_version", lineage.version)
            lineage.checksum = data.get("new_checksum", lineage.checksum)

        if "parent_id" in data and data["parent_id"]:
            parent_id = data["parent_id"]
            if parent_id not in lineage.parent_ids:
                lineage.parent_ids.append(parent_id)

            if parent_id in self._lineages:
                parent_lineage = self._lineages[parent_id]
                if algorithm_id not in parent_lineage.children_ids:
                    parent_lineage.children_ids.append(algorithm_id)

    def verify_chain(self) -> tuple[bool, list[str]]:
        """Verify the integrity of the blockchain."""
        errors = []

        for i in range(1, len(self._chain)):
            current = self._chain[i]
            previous = self._chain[i - 1]

            if current.previous_hash != previous.hash:
                errors.append(f"Block {i}: Invalid previous hash")

            computed_hash = current.compute_hash()
            if current.hash != computed_hash:
                errors.append(f"Block {i}: Invalid hash")

            if not current.hash.startswith("0" * self.DIFFICULTY):
                errors.append(f"Block {i}: Hash doesn't meet difficulty requirement")

        return len(errors) == 0, errors

    def get_algorithm_history(
        self,
        algorithm_id: str,
    ) -> list[dict]:
        """Get all provenance records for an algorithm."""
        history = []

        for block in self._chain:
            if block.algorithm_id == algorithm_id:
                history.append(block.to_dict())

        return sorted(history, key=lambda x: x["timestamp"])

    def get_lineage_tree(
        self,
        algorithm_id: str,
        depth: int = 5,
    ) -> dict:
        """Get the full lineage tree for an algorithm."""
        lineage = self._lineages.get(algorithm_id)

        if not lineage:
            return {}

        def build_tree(lin: AlgorithmLineage, current_depth: int) -> dict:
            if current_depth > depth:
                return {"algorithm_id": lin.algorithm_id, "truncated": True}

            tree = {
                "algorithm_id": lin.algorithm_id,
                "name": lin.name,
                "version": lin.version,
                "author_id": lin.author_id,
                "execution_count": lin.execution_count,
                "parents": [],
                "children": [],
            }

            for parent_id in lin.parent_ids:
                if parent_id in self._lineages:
                    tree["parents"].append(build_tree(self._lineages[parent_id], current_depth + 1))

            for child_id in lin.children_ids:
                if child_id in self._lineages:
                    tree["children"].append(build_tree(self._lineages[child_id], current_depth + 1))

            return tree

        return build_tree(lineage, 0)

    def search_by_user(
        self,
        user_id: str,
        event_type: Optional[ProvenanceEventType] = None,
    ) -> list[dict]:
        """Search provenance records by user."""
        results = []

        for block in self._chain:
            if block.user_id == user_id:
                if event_type is None or block.event_type == event_type:
                    results.append(block.to_dict())

        return sorted(results, key=lambda x: x["timestamp"], reverse=True)

    def get_statistics(self) -> dict:
        """Get provenance chain statistics."""
        event_counts = {}
        for event_type in ProvenanceEventType:
            event_counts[event_type.value] = sum(
                1 for block in self._chain if block.event_type == event_type
            )

        return {
            "total_blocks": len(self._chain),
            "total_algorithms": len(self._lineages),
            "event_counts": event_counts,
            "chain_valid": self.verify_chain()[0],
            "difficulty": self.DIFFICULTY,
        }

    def export_chain(self) -> str:
        """Export the blockchain as JSON."""
        return json.dumps(
            {
                "chain": [block.to_dict() for block in self._chain],
                "lineages": {aid: lin.to_dict() for aid, lin in self._lineages.items()},
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )

    def import_chain(self, data: str) -> bool:
        """Import a blockchain from JSON."""
        try:
            parsed = json.loads(data)

            self._chain = [ProvenanceBlock.from_dict(block) for block in parsed["chain"]]

            self._lineages = {
                aid: AlgorithmLineage(**lin_data) for aid, lin_data in parsed["lineages"].items()
            }

            valid, errors = self.verify_chain()
            if not valid:
                logger.error("imported_chain_invalid", errors=errors)
                return False

            return True

        except Exception as e:
            logger.error("chain_import_failed", error=str(e))
            return False


provenance_chain = ProvenanceChain()
