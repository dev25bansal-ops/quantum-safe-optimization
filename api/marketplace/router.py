"""
Algorithm Marketplace API Endpoints.

Provides search, publishing, and purchasing for quantum algorithms.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from .models import (
    AlgorithmCategory,
    AlgorithmCreate,
    AlgorithmRating,
    AlgorithmResponse,
    AlgorithmReviewCreate,
    MarketplaceAlgorithm,
    PricingModel,
    PurchaseResponse,
    ReviewResponse,
    _algorithms,
    _ratings,
    purchase_algorithm,
    search_algorithms,
    seed_marketplace,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_user_id() -> str:
    """Get current user ID (stub for auth integration)."""
    return "user_default"


def get_tenant_id() -> str:
    """Get current tenant ID (stub for auth integration)."""
    return "tenant_default"


@router.get("/", response_model=dict[str, Any])
async def marketplace_home():
    """Get marketplace homepage data."""
    seed_marketplace()

    featured = [a for a in _algorithms.values() if a.is_featured][:5]
    if not featured:
        featured = sorted(_algorithms.values(), key=lambda a: -a.downloads)[:5]

    categories = [
        {
            "id": c.value,
            "name": c.value.upper(),
            "count": sum(1 for a in _algorithms.values() if a.category == c),
        }
        for c in AlgorithmCategory
    ]

    return {
        "featured": [
            AlgorithmResponse(
                algorithm_id=a.algorithm_id,
                name=a.name,
                slug=a.slug,
                description=a.description,
                long_description=a.long_description,
                category=a.category,
                author_id=a.author_id,
                author_name=a.author_name,
                version=a.version,
                pricing_model=a.pricing_model,
                price=a.price,
                license_type=a.license_type,
                tags=a.tags,
                min_qubits=a.min_qubits,
                max_qubits=a.max_qubits,
                downloads=a.downloads,
                rating_avg=a.rating_avg,
                rating_count=a.rating_count,
                is_verified=a.is_verified,
                is_featured=a.is_featured,
                created_at=a.created_at.isoformat(),
                updated_at=a.updated_at.isoformat(),
                source_url=a.source_url,
                documentation_url=a.documentation_url,
            )
            for a in featured
        ],
        "categories": categories,
        "total_algorithms": len(_algorithms),
    }


@router.get("/search", response_model=list[AlgorithmResponse])
async def search_marketplace(
    q: str | None = Query(default=None, description="Search query"),
    category: AlgorithmCategory | None = None,
    min_rating: float | None = Query(default=None, ge=0, le=5),
    pricing: PricingModel | None = None,
    max_price: float | None = None,
    tags: str | None = Query(default=None, description="Comma-separated tags"),
    sort: str = Query(default="relevance"),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Search algorithms in marketplace."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    results = search_algorithms(
        query=q,
        category=category,
        min_rating=min_rating,
        pricing_model=pricing,
        max_price=max_price,
        tags=tag_list,
        sort_by=sort,
        limit=limit,
        offset=offset,
    )

    return [
        AlgorithmResponse(
            algorithm_id=a.algorithm_id,
            name=a.name,
            slug=a.slug,
            description=a.description,
            long_description=a.long_description,
            category=a.category,
            author_id=a.author_id,
            author_name=a.author_name,
            version=a.version,
            pricing_model=a.pricing_model,
            price=a.price,
            license_type=a.license_type,
            tags=a.tags,
            min_qubits=a.min_qubits,
            max_qubits=a.max_qubits,
            downloads=a.downloads,
            rating_avg=a.rating_avg,
            rating_count=a.rating_count,
            is_verified=a.is_verified,
            is_featured=a.is_featured,
            created_at=a.created_at.isoformat(),
            updated_at=a.updated_at.isoformat(),
            source_url=a.source_url,
            documentation_url=a.documentation_url,
        )
        for a in results
    ]


@router.get("/categories", response_model=list[dict[str, Any]])
async def list_categories():
    """List all categories with counts."""
    seed_marketplace()

    return [
        {
            "id": c.value,
            "name": c.value.upper(),
            "count": sum(1 for a in _algorithms.values() if a.category == c),
        }
        for c in AlgorithmCategory
    ]


@router.get("/{algorithm_id}", response_model=AlgorithmResponse)
async def get_algorithm(algorithm_id: str):
    """Get algorithm details."""
    seed_marketplace()

    if algorithm_id not in _algorithms:
        raise HTTPException(status_code=404, detail="Algorithm not found")

    a = _algorithms[algorithm_id]

    return AlgorithmResponse(
        algorithm_id=a.algorithm_id,
        name=a.name,
        slug=a.slug,
        description=a.description,
        long_description=a.long_description,
        category=a.category,
        author_id=a.author_id,
        author_name=a.author_name,
        version=a.version,
        pricing_model=a.pricing_model,
        price=a.price,
        license_type=a.license_type,
        tags=a.tags,
        min_qubits=a.min_qubits,
        max_qubits=a.max_qubits,
        downloads=a.downloads,
        rating_avg=a.rating_avg,
        rating_count=a.rating_count,
        is_verified=a.is_verified,
        is_featured=a.is_featured,
        created_at=a.created_at.isoformat(),
        updated_at=a.updated_at.isoformat(),
        source_url=a.source_url,
        documentation_url=a.documentation_url,
    )


@router.post("/", response_model=AlgorithmResponse)
async def publish_algorithm(
    request: AlgorithmCreate,
    user_id: str = Depends(get_user_id),
):
    """Publish a new algorithm to marketplace."""
    algo = MarketplaceAlgorithm.create(
        name=request.name,
        description=request.description,
        category=request.category,
        author_id=user_id,
        author_name=user_id.replace("user_", ""),
        pricing_model=request.pricing_model,
        price=request.price,
        tags=request.tags,
        min_qubits=request.min_qubits,
        max_qubits=request.max_qubits,
        long_description=request.long_description,
        license_type=request.license_type,
        source_url=request.source_url,
        documentation_url=request.documentation_url,
    )

    _algorithms[algo.algorithm_id] = algo

    logger.info(f"Published algorithm: {algo.algorithm_id} - {algo.name}")

    return AlgorithmResponse(
        algorithm_id=algo.algorithm_id,
        name=algo.name,
        slug=algo.slug,
        description=algo.description,
        long_description=algo.long_description,
        category=algo.category,
        author_id=algo.author_id,
        author_name=algo.author_name,
        version=algo.version,
        pricing_model=algo.pricing_model,
        price=algo.price,
        license_type=algo.license_type,
        tags=algo.tags,
        min_qubits=algo.min_qubits,
        max_qubits=algo.max_qubits,
        downloads=algo.downloads,
        rating_avg=algo.rating_avg,
        rating_count=algo.rating_count,
        is_verified=algo.is_verified,
        is_featured=algo.is_featured,
        created_at=algo.created_at.isoformat(),
        updated_at=algo.updated_at.isoformat(),
        source_url=algo.source_url,
        documentation_url=algo.documentation_url,
    )


@router.post("/{algorithm_id}/purchase", response_model=PurchaseResponse)
async def purchase_algorithm_endpoint(
    algorithm_id: str,
    user_id: str = Depends(get_user_id),
    tenant_id: str = Depends(get_tenant_id),
):
    """Purchase an algorithm."""
    seed_marketplace()

    try:
        purchase = purchase_algorithm(algorithm_id, user_id, tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    algo = _algorithms[algorithm_id]

    logger.info(f"Algorithm purchased: {algorithm_id} by {user_id}")

    return PurchaseResponse(
        purchase_id=purchase.purchase_id,
        algorithm_id=purchase.algorithm_id,
        algorithm_name=algo.name,
        price_paid=purchase.price_paid,
        purchased_at=purchase.purchased_at.isoformat(),
        license_key=purchase.license_key,
    )


@router.get("/{algorithm_id}/reviews", response_model=list[ReviewResponse])
async def get_algorithm_reviews(algorithm_id: str):
    """Get reviews for an algorithm."""
    seed_marketplace()

    if algorithm_id not in _algorithms:
        raise HTTPException(status_code=404, detail="Algorithm not found")

    reviews = _ratings.get(algorithm_id, [])

    return [
        ReviewResponse(
            review_id=f"review_{r.algorithm_id}_{r.user_id}",
            algorithm_id=r.algorithm_id,
            user_id=r.user_id,
            username=r.user_id.replace("user_", ""),
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at.isoformat(),
        )
        for r in reviews
    ]


@router.post("/{algorithm_id}/reviews", response_model=ReviewResponse)
async def submit_review(
    algorithm_id: str,
    request: AlgorithmReviewCreate,
    user_id: str = Depends(get_user_id),
):
    """Submit a review for an algorithm."""
    seed_marketplace()

    if algorithm_id not in _algorithms:
        raise HTTPException(status_code=404, detail="Algorithm not found")

    algo = _algorithms[algorithm_id]

    rating = AlgorithmRating(
        algorithm_id=algorithm_id,
        user_id=user_id,
        rating=request.rating,
        comment=request.comment,
    )

    _ratings.setdefault(algorithm_id, []).append(rating)

    ratings = _ratings[algorithm_id]
    algo.rating_avg = sum(r.rating for r in ratings) / len(ratings)
    algo.rating_count = len(ratings)

    return ReviewResponse(
        review_id=f"review_{algorithm_id}_{user_id}",
        algorithm_id=algorithm_id,
        user_id=user_id,
        username=user_id.replace("user_", ""),
        rating=rating.rating,
        comment=rating.comment,
        created_at=rating.created_at.isoformat(),
    )


@router.get("/user/purchases", response_model=list[PurchaseResponse])
async def get_user_purchases(
    user_id: str = Depends(get_user_id),
):
    """Get user's purchased algorithms."""
    from .models import _purchases

    user_purchases = _purchases.get(user_id, [])

    results = []
    for p in user_purchases:
        if p.algorithm_id in _algorithms:
            algo = _algorithms[p.algorithm_id]
            results.append(
                PurchaseResponse(
                    purchase_id=p.purchase_id,
                    algorithm_id=p.algorithm_id,
                    algorithm_name=algo.name,
                    price_paid=p.price_paid,
                    purchased_at=p.purchased_at.isoformat(),
                    license_key=p.license_key,
                )
            )

    return results


@router.delete("/{algorithm_id}")
async def delete_algorithm(
    algorithm_id: str,
    user_id: str = Depends(get_user_id),
):
    """Delete an algorithm (author only)."""
    if algorithm_id not in _algorithms:
        raise HTTPException(status_code=404, detail="Algorithm not found")

    algo = _algorithms[algorithm_id]

    if algo.author_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this algorithm")

    del _algorithms[algorithm_id]

    logger.info(f"Algorithm deleted: {algorithm_id}")

    return {"status": "deleted", "algorithm_id": algorithm_id}
