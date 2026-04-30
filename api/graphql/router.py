"""
GraphQL Router for the API.
"""

from fastapi import APIRouter, Depends
from strawberry.fastapi import GraphQLRouter

from .schema import schema

router = APIRouter()


def get_context():
    """Get GraphQL context."""
    return {"user_id": "graphql_user", "tenant_id": "default_tenant"}


graphql_app = GraphQLRouter(schema, context_getter=get_context, debug=True, graphiql=True)

router.include_router(graphql_app, prefix="/graphql")
