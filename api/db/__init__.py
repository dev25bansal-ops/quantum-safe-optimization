"""
Database package.
"""

from .cosmos import (
    cosmos_manager,
    init_cosmos,
    close_cosmos,
    JobRepository,
    UserRepository,
    KeyRepository,
)

from .repository import (
    get_job_store,
    get_user_store,
    get_key_store,
    get_token_store,
    reset_stores,
    BaseStore,
    InMemoryJobStore,
    InMemoryUserStore,
    InMemoryKeyStore,
    InMemoryTokenStore,
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
