"""
Real-Time Collaboration Service.

Enables:
- Real-time document editing
- Presence indicators
- Cursor tracking
- Comments and annotations
- Session management
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class CollaborationEventType(str, Enum):
    """Types of collaboration events."""

    CURSOR_MOVE = "cursor.move"
    SELECTION_CHANGE = "selection.change"
    EDIT = "document.edit"
    COMMENT_ADD = "comment.add"
    COMMENT_RESOLVE = "comment.resolve"
    USER_JOIN = "session.join"
    USER_LEAVE = "session.leave"
    PRESENCE_UPDATE = "presence.update"
    LOCK_ACQUIRE = "lock.acquire"
    LOCK_RELEASE = "lock.release"
    SYNC_REQUEST = "sync.request"
    SYNC_RESPONSE = "sync.response"


class DocumentLockType(str, Enum):
    """Types of document locks."""

    READ = "read"
    WRITE = "write"
    EDIT_SECTION = "edit_section"
    EXCLUSIVE = "exclusive"


@dataclass
class User:
    """Collaborating user."""

    user_id: str
    username: str
    display_name: str
    color: str
    avatar_url: Optional[str] = None
    last_active: datetime = field(default_factory=lambda: datetime.now(UTC))
    cursor_position: Optional[dict] = None
    selection: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "color": self.color,
            "avatar_url": self.avatar_url,
            "last_active": self.last_active.isoformat(),
            "cursor_position": self.cursor_position,
            "selection": self.selection,
        }


@dataclass
class Session:
    """Collaboration session."""

    session_id: str
    document_id: str
    created_at: datetime
    users: dict[str, User] = field(default_factory=dict)
    locks: dict[str, dict] = field(default_factory=dict)
    comments: list[dict] = field(default_factory=list)
    document_state: dict = field(default_factory=dict)
    version: int = 0

    @property
    def active_users(self) -> list[User]:
        """Get active users (active in last 5 minutes)."""
        threshold = datetime.now(UTC) - timedelta(minutes=5)
        return [u for u in self.users.values() if u.last_active >= threshold]


@dataclass
class CollaborationEvent:
    """A collaboration event."""

    event_id: str
    event_type: CollaborationEventType
    session_id: str
    user_id: str
    timestamp: datetime
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


class CollaborationService:
    """
    Real-time collaboration service.

    Features:
    - Multi-user document editing
    - Presence indicators
    - Cursor and selection tracking
    - Comments and annotations
    - Document locking
    - Conflict resolution
    """

    def __init__(self, max_users_per_session: int = 50):
        self.max_users_per_session = max_users_per_session
        self._sessions: dict[str, Session] = {}
        self._user_sessions: dict[str, str] = {}
        self._event_history: dict[str, list[CollaborationEvent]] = defaultdict(list)
        self._subscribers: dict[str, list[callable]] = defaultdict(list)
        self._lock = asyncio.Lock()

        self._colors = [
            "#FF6B6B",
            "#4ECDC4",
            "#45B7D1",
            "#96CEB4",
            "#FFEAA7",
            "#DDA0DD",
            "#98D8C8",
            "#F7DC6F",
            "#BB8FCE",
            "#85C1E9",
            "#F8B500",
            "#00CED1",
        ]

    def _assign_color(self, session_id: str) -> str:
        """Assign a unique color to a user."""
        session = self._sessions.get(session_id)
        if not session:
            return self._colors[0]

        used_colors = {u.color for u in session.users.values()}
        for color in self._colors:
            if color not in used_colors:
                return color
        return self._colors[len(session.users) % len(self._colors)]

    async def create_session(
        self, document_id: str, initial_state: Optional[dict] = None
    ) -> Session:
        """Create a new collaboration session."""
        session_id = f"session_{uuid4().hex[:12]}"

        session = Session(
            session_id=session_id,
            document_id=document_id,
            created_at=datetime.now(UTC),
            document_state=initial_state or {},
        )

        async with self._lock:
            self._sessions[session_id] = session

        logger.info("session_created", session_id=session_id, document_id=document_id)

        return session

    async def join_session(
        self, session_id: str, user_id: str, username: str, display_name: Optional[str] = None
    ) -> User:
        """Join a collaboration session."""
        async with self._lock:
            if session_id not in self._sessions:
                raise ValueError(f"Session {session_id} not found")

            session = self._sessions[session_id]

            if len(session.users) >= self.max_users_per_session:
                raise RuntimeError("Session is full")

            if user_id in session.users:
                user = session.users[user_id]
                user.last_active = datetime.now(UTC)
                return user

            user = User(
                user_id=user_id,
                username=username,
                display_name=display_name or username,
                color=self._assign_color(session_id),
                last_active=datetime.now(UTC),
            )

            session.users[user_id] = user
            self._user_sessions[user_id] = session_id

        await self._emit_event(
            session_id=session_id,
            user_id=user_id,
            event_type=CollaborationEventType.USER_JOIN,
            data={"user": user.to_dict()},
        )

        logger.info("user_joined", session_id=session_id, user_id=user_id)

        return user

    async def leave_session(self, session_id: str, user_id: str) -> bool:
        """Leave a collaboration session."""
        async with self._lock:
            if session_id not in self._sessions:
                return False

            session = self._sessions[session_id]
            user = session.users.pop(user_id, None)

            if not user:
                return False

            self._user_sessions.pop(user_id, None)

            # Release any locks held by user
            locks_to_release = [
                lock_id for lock_id, lock in session.locks.items() if lock.get("owner") == user_id
            ]
            for lock_id in locks_to_release:
                del session.locks[lock_id]

        await self._emit_event(
            session_id=session_id,
            user_id=user_id,
            event_type=CollaborationEventType.USER_LEAVE,
            data={"user_id": user_id},
        )

        logger.info("user_left", session_id=session_id, user_id=user_id)

        return True

    async def update_cursor(self, session_id: str, user_id: str, position: dict) -> None:
        """Update user cursor position."""
        async with self._lock:
            if session_id not in self._sessions:
                return

            session = self._sessions[session_id]
            if user_id not in session.users:
                return

            user = session.users[user_id]
            user.cursor_position = position
            user.last_active = datetime.now(UTC)

        await self._emit_event(
            session_id=session_id,
            user_id=user_id,
            event_type=CollaborationEventType.CURSOR_MOVE,
            data={"position": position},
        )

    async def update_selection(self, session_id: str, user_id: str, selection: dict) -> None:
        """Update user selection."""
        async with self._lock:
            if session_id not in self._sessions:
                return

            session = self._sessions[session_id]
            if user_id not in session.users:
                return

            user = session.users[user_id]
            user.selection = selection
            user.last_active = datetime.now(UTC)

        await self._emit_event(
            session_id=session_id,
            user_id=user_id,
            event_type=CollaborationEventType.SELECTION_CHANGE,
            data={"selection": selection},
        )

    async def apply_edit(self, session_id: str, user_id: str, edit: dict) -> dict:
        """Apply an edit to the document."""
        async with self._lock:
            if session_id not in self._sessions:
                raise ValueError(f"Session {session_id} not found")

            session = self._sessions[session_id]

            # Check for conflicts
            if edit.get("base_version") and edit["base_version"] != session.version:
                return {
                    "success": False,
                    "error": "version_conflict",
                    "current_version": session.version,
                }

            # Apply edit (simplified - real implementation would use OT/CRDT)
            session.version += 1
            session.document_state.update(edit.get("changes", {}))

            if user_id in session.users:
                session.users[user_id].last_active = datetime.now(UTC)

        await self._emit_event(
            session_id=session_id,
            user_id=user_id,
            event_type=CollaborationEventType.EDIT,
            data={"edit": edit, "version": session.version},
        )

        return {"success": True, "version": session.version}

    async def add_comment(
        self, session_id: str, user_id: str, content: str, position: dict
    ) -> dict:
        """Add a comment to the document."""
        comment = {
            "comment_id": f"comment_{uuid4().hex[:8]}",
            "user_id": user_id,
            "content": content,
            "position": position,
            "created_at": datetime.now(UTC).isoformat(),
            "resolved": False,
        }

        async with self._lock:
            if session_id not in self._sessions:
                raise ValueError(f"Session {session_id} not found")

            session = self._sessions[session_id]
            session.comments.append(comment)

        await self._emit_event(
            session_id=session_id,
            user_id=user_id,
            event_type=CollaborationEventType.COMMENT_ADD,
            data={"comment": comment},
        )

        return comment

    async def resolve_comment(self, session_id: str, user_id: str, comment_id: str) -> bool:
        """Resolve a comment."""
        async with self._lock:
            if session_id not in self._sessions:
                return False

            session = self._sessions[session_id]

            for comment in session.comments:
                if comment["comment_id"] == comment_id:
                    comment["resolved"] = True
                    comment["resolved_by"] = user_id
                    comment["resolved_at"] = datetime.now(UTC).isoformat()
                    break
            else:
                return False

        await self._emit_event(
            session_id=session_id,
            user_id=user_id,
            event_type=CollaborationEventType.COMMENT_RESOLVE,
            data={"comment_id": comment_id},
        )

        return True

    async def acquire_lock(
        self,
        session_id: str,
        user_id: str,
        lock_type: DocumentLockType,
        scope: Optional[dict] = None,
    ) -> bool:
        """Acquire a document lock."""
        lock_id = f"lock_{uuid4().hex[:8]}"

        async with self._lock:
            if session_id not in self._sessions:
                return False

            session = self._sessions[session_id]

            # Check for conflicting locks
            for existing_lock in session.locks.values():
                if existing_lock["type"] in [DocumentLockType.EXCLUSIVE, DocumentLockType.WRITE]:
                    if existing_lock["owner"] != user_id:
                        return False

            lock = {
                "lock_id": lock_id,
                "type": lock_type.value,
                "owner": user_id,
                "scope": scope,
                "acquired_at": datetime.now(UTC).isoformat(),
            }

            session.locks[lock_id] = lock

        await self._emit_event(
            session_id=session_id,
            user_id=user_id,
            event_type=CollaborationEventType.LOCK_ACQUIRE,
            data={"lock": lock},
        )

        return True

    async def release_lock(self, session_id: str, user_id: str, lock_id: str) -> bool:
        """Release a document lock."""
        async with self._lock:
            if session_id not in self._sessions:
                return False

            session = self._sessions[session_id]
            lock = session.locks.get(lock_id)

            if not lock or lock["owner"] != user_id:
                return False

            del session.locks[lock_id]

        await self._emit_event(
            session_id=session_id,
            user_id=user_id,
            event_type=CollaborationEventType.LOCK_RELEASE,
            data={"lock_id": lock_id},
        )

        return True

    async def get_session_state(self, session_id: str) -> dict:
        """Get current session state."""
        async with self._lock:
            if session_id not in self._sessions:
                raise ValueError(f"Session {session_id} not found")

            session = self._sessions[session_id]

            return {
                "session_id": session_id,
                "document_id": session.document_id,
                "version": session.version,
                "users": [u.to_dict() for u in session.active_users],
                "active_count": len(session.active_users),
                "document_state": session.document_state,
                "comments": session.comments,
                "locks": session.locks,
            }

    async def subscribe(self, session_id: str, handler: callable) -> callable:
        """Subscribe to session events."""
        self._subscribers[session_id].append(handler)

        def unsubscribe():
            if handler in self._subscribers[session_id]:
                self._subscribers[session_id].remove(handler)

        return unsubscribe

    async def _emit_event(
        self, session_id: str, user_id: str, event_type: CollaborationEventType, data: dict
    ) -> None:
        """Emit an event to subscribers."""
        event = CollaborationEvent(
            event_id=f"evt_{uuid4().hex[:8]}",
            event_type=event_type,
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.now(UTC),
            data=data,
        )

        self._event_history[session_id].append(event)

        for handler in self._subscribers.get(session_id, []):
            try:
                await handler(event.to_dict())
            except Exception as e:
                logger.error("event_handler_error", error=str(e))

    async def get_events(
        self, session_id: str, since_version: int = 0, limit: int = 100
    ) -> list[dict]:
        """Get events since a version."""
        events = self._event_history.get(session_id, [])
        return [e.to_dict() for e in events[-limit:]]


collaboration_service = CollaborationService()
