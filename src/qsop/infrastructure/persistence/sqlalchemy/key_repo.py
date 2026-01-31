"""SQLAlchemy repository for key persistence."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import KeyModel, KeyVersionModel


class SQLAlchemyKeyRepository:
    """Repository for key CRUD operations using SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        tenant_id: str,
        name: str,
        algorithm: str,
        key_size: int | None,
        public_key_id: str,
        private_key_id: str,
        metadata: dict[str, Any] | None = None,
        expires_in_days: int | None = None,
        auto_rotate: bool = False,
        rotation_period_days: int | None = None,
    ) -> KeyModel:
        """Create a new key."""
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        key = KeyModel(
            tenant_id=tenant_id,
            name=name,
            algorithm=algorithm,
            key_size=key_size,
            public_key_id=public_key_id,
            private_key_id=private_key_id,
            metadata_json=metadata or {},
            expires_at=expires_at,
            auto_rotate=auto_rotate,
            rotation_period_days=rotation_period_days,
            status="active",
            version=1,
        )
        self.session.add(key)
        await self.session.flush()
        
        # Create initial version record
        version = KeyVersionModel(
            key_id=key.id,
            version=1,
            public_key_id=public_key_id,
            private_key_id=private_key_id,
        )
        self.session.add(version)
        await self.session.flush()
        await self.session.refresh(key)
        
        return key

    async def get_by_id(
        self,
        key_id: UUID,
        tenant_id: str | None = None,
    ) -> KeyModel | None:
        """Get a key by ID, optionally filtering by tenant."""
        stmt = select(KeyModel).where(KeyModel.id == key_id)
        if tenant_id:
            stmt = stmt.where(KeyModel.tenant_id == tenant_id)
        
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        name: str,
        tenant_id: str,
    ) -> KeyModel | None:
        """Get a key by name within a tenant."""
        stmt = select(KeyModel).where(
            KeyModel.name == name,
            KeyModel.tenant_id == tenant_id,
            KeyModel.status != "revoked",
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[KeyModel], int]:
        """List keys for a tenant with pagination."""
        base_query = select(KeyModel).where(KeyModel.tenant_id == tenant_id)
        
        if status:
            base_query = base_query.where(KeyModel.status == status)
        
        # Count query
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Data query with pagination
        stmt = (
            base_query
            .order_by(KeyModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        keys = list(result.scalars().all())
        
        return keys, total

    async def rotate(
        self,
        key_id: UUID,
        new_public_key_id: str,
        new_private_key_id: str,
    ) -> KeyModel:
        """Rotate a key to a new version."""
        key = await self.get_by_id(key_id)
        if key is None:
            raise ValueError(f"Key {key_id} not found")
        
        # Retire current version
        await self.session.execute(
            update(KeyVersionModel)
            .where(
                KeyVersionModel.key_id == key_id,
                KeyVersionModel.version == key.version,
            )
            .values(retired_at=datetime.utcnow())
        )
        
        new_version = key.version + 1
        
        # Update key with new version
        stmt = (
            update(KeyModel)
            .where(KeyModel.id == key_id)
            .values(
                public_key_id=new_public_key_id,
                private_key_id=new_private_key_id,
                version=new_version,
                rotated_at=datetime.utcnow(),
            )
            .returning(KeyModel)
        )
        result = await self.session.execute(stmt)
        updated_key = result.scalar_one()
        
        # Create new version record
        version = KeyVersionModel(
            key_id=key_id,
            version=new_version,
            public_key_id=new_public_key_id,
            private_key_id=new_private_key_id,
        )
        self.session.add(version)
        await self.session.flush()
        
        return updated_key

    async def revoke(self, key_id: UUID) -> bool:
        """Revoke a key."""
        stmt = (
            update(KeyModel)
            .where(KeyModel.id == key_id)
            .values(
                status="revoked",
                revoked_at=datetime.utcnow(),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def record_usage(self, key_id: UUID) -> None:
        """Record key usage."""
        stmt = (
            update(KeyModel)
            .where(KeyModel.id == key_id)
            .values(
                usage_count=KeyModel.usage_count + 1,
                last_used_at=datetime.utcnow(),
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_version(
        self,
        key_id: UUID,
        version: int,
    ) -> KeyVersionModel | None:
        """Get a specific key version."""
        stmt = select(KeyVersionModel).where(
            KeyVersionModel.key_id == key_id,
            KeyVersionModel.version == version,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_keys_for_rotation(self) -> list[KeyModel]:
        """Get keys that need automatic rotation."""
        now = datetime.utcnow()
        
        stmt = (
            select(KeyModel)
            .where(
                KeyModel.auto_rotate.is_(True),
                KeyModel.status == "active",
                KeyModel.rotation_period_days.isnot(None),
            )
        )
        result = await self.session.execute(stmt)
        keys = result.scalars().all()
        
        # Filter keys that need rotation based on last rotation time
        keys_to_rotate = []
        for key in keys:
            last_rotation = key.rotated_at or key.created_at
            next_rotation = last_rotation + timedelta(days=key.rotation_period_days)
            if now >= next_rotation:
                keys_to_rotate.append(key)
        
        return keys_to_rotate

    async def get_expiring_keys(
        self,
        days_until_expiry: int = 30,
    ) -> list[KeyModel]:
        """Get keys that will expire soon."""
        threshold = datetime.utcnow() + timedelta(days=days_until_expiry)
        
        stmt = (
            select(KeyModel)
            .where(
                KeyModel.status == "active",
                KeyModel.expires_at.isnot(None),
                KeyModel.expires_at <= threshold,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
