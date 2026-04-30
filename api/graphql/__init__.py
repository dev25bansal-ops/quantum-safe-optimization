"""
GraphQL API Module.

Provides GraphQL interface for complex queries and mutations.
"""

try:
    from .schema import schema, Query, Mutation, Job, JobResult, KeyInfo, BackendInfo
    from .router import router as graphql_router

    GRAPHQL_AVAILABLE = True
except ImportError:
    schema = None
    Query = None
    Mutation = None
    Job = None
    JobResult = None
    KeyInfo = None
    BackendInfo = None
    graphql_router = None
    GRAPHQL_AVAILABLE = False

__all__ = [
    "schema",
    "Query",
    "Mutation",
    "Job",
    "JobResult",
    "KeyInfo",
    "BackendInfo",
    "graphql_router",
    "GRAPHQL_AVAILABLE",
]
