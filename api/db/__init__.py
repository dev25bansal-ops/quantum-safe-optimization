"""
Database package.
"""

from .cosmos import (
    JobRepository,
    KeyRepository,
    UserRepository,
    close_cosmos,
    cosmos_manager,
    init_cosmos,
)
from .repository import (
    BaseStore,
    InMemoryJobStore,
    InMemoryKeyStore,
    InMemoryTokenStore,
    InMemoryUserStore,
    get_job_store,
    get_key_store,
    get_token_store,
    get_user_store,
    reset_stores,
)

__all__ = [
    # Cosmos DB
    "cosmos_manager",
    "init_cosmos",
    "close_cosmos",
    "JobRepository",
    "UserRepository",
    "KeyRepository",
    # Repository abstraction
    "get_job_store",
    "get_user_store",
    "get_key_store",
    "get_token_store",
    "reset_stores",
    "BaseStore",
    "InMemoryJobStore",
    "InMemoryUserStore",
    "InMemoryKeyStore",
    "InMemoryTokenStore",
]
