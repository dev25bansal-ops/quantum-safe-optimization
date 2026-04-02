"""
Algorithm Marketplace Models.

Provides models for the quantum algorithm marketplace.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AlgorithmCategory(str, Enum):
    """Algorithm categories."""

    QAOA = "qaoa"
    VQE = "vqe"
    QUBO = "qubo"
    ANNEALING = "annealing"
    ML = "machine_learning"
    CHEMISTRY = "chemistry"
    FINANCE = "finance"
    LOGISTICS = "logistics"
    CRYPTOGRAPHY = "cryptography"
    OTHER = "other"


class LicenseType(str, Enum):
    """License types for algorithms."""

    MIT = "mit"
    APACHE = "apache"
    GPL = "gpl"
    PROPRIETARY = "proprietary"
    RESEARCH = "research"


class PricingModel(str, Enum):
    """Pricing models."""

    FREE = "free"
    ONE_TIME = "one_time"
    SUBSCRIPTION = "subscription"
    USAGE_BASED = "usage_based"


@dataclass
class AlgorithmVersion:
    """Version of an algorithm."""

    version: str
    changes: list[str]
    released_at: datetime
    download_url: str
    checksum: str
    min_qubits: int
    max_qubits: int | None = None


@dataclass
class AlgorithmRating:
    """Rating for an algorithm."""

    algorithm_id: str
    user_id: str
    rating: int
    comment: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AlgorithmPurchase:
    """Purchase record."""

    purchase_id: str
    algorithm_id: str
    user_id: str
    tenant_id: str
    price_paid: float
    purchased_at: datetime
    license_key: str | None = None


@dataclass
class MarketplaceAlgorithm:
    """Algorithm in the marketplace."""

    algorithm_id: str
    name: str
    slug: str
    description: str
    long_description: str | None
    category: AlgorithmCategory
    author_id: str
    author_name: str
    version: str
    pricing_model: PricingModel
    price: float
    license_type: LicenseType
    tags: list[str]
    min_qubits: int
    max_qubits: int | None
    created_at: datetime
    updated_at: datetime
    downloads: int = 0
    rating_avg: float = 0.0
    rating_count: int = 0
    is_verified: bool = False
    is_featured: bool = False
    source_url: str | None = None
    documentation_url: str | None = None

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        category: AlgorithmCategory,
        author_id: str,
        author_name: str,
        pricing_model: PricingModel = PricingModel.FREE,
        price: float = 0.0,
        tags: list[str] | None = None,
        **kwargs,
    ) -> "MarketplaceAlgorithm":
        """Create a new marketplace algorithm."""
        now = datetime.now(timezone.utc)
        slug = name.lower().replace(" ", "-").replace("_", "-")[:50]

        return cls(
            algorithm_id=f"algo_{uuid4().hex[:12]}",
            name=name,
            slug=slug,
            description=description,
            long_description=kwargs.get("long_description"),
            category=category,
            author_id=author_id,
            author_name=author_name,
            version=kwargs.get("version", "1.0.0"),
            pricing_model=pricing_model,
            price=price,
            license_type=kwargs.get("license_type", LicenseType.MIT),
            tags=tags or [],
            min_qubits=kwargs.get("min_qubits", 2),
            max_qubits=kwargs.get("max_qubits"),
            created_at=now,
            updated_at=now,
            source_url=kwargs.get("source_url"),
            documentation_url=kwargs.get("documentation_url"),
        )


# Pydantic models for API


class AlgorithmCreate(BaseModel):
    """Request to publish an algorithm."""

    name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=10, max_length=500)
    long_description: str | None = None
    category: AlgorithmCategory
    pricing_model: PricingModel = PricingModel.FREE
    price: float = Field(default=0.0, ge=0)
    license_type: LicenseType = LicenseType.MIT
    tags: list[str] = Field(default_factory=list)
    min_qubits: int = Field(default=2, ge=1)
    max_qubits: int | None = None
    source_url: str | None = None
    documentation_url: str | None = None
    code: str | None = None


class AlgorithmResponse(BaseModel):
    """Algorithm response."""

    algorithm_id: str
    name: str
    slug: str
    description: str
    long_description: str | None
    category: AlgorithmCategory
    author_id: str
    author_name: str
    version: str
    pricing_model: PricingModel
    price: float
    license_type: LicenseType
    tags: list[str]
    min_qubits: int
    max_qubits: int | None
    downloads: int
    rating_avg: float
    rating_count: int
    is_verified: bool
    is_featured: bool
    created_at: str
    updated_at: str
    source_url: str | None
    documentation_url: str | None


class AlgorithmReviewCreate(BaseModel):
    """Request to submit a review."""

    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewResponse(BaseModel):
    """Review response."""

    review_id: str
    algorithm_id: str
    user_id: str
    username: str
    rating: int
    comment: str | None
    created_at: str


class PurchaseResponse(BaseModel):
    """Purchase response."""

    purchase_id: str
    algorithm_id: str
    algorithm_name: str
    price_paid: float
    purchased_at: str
    license_key: str | None


class MarketplaceSearch(BaseModel):
    """Search request."""

    query: str | None = None
    category: AlgorithmCategory | None = None
    min_rating: float | None = Field(default=None, ge=0, le=5)
    pricing_model: PricingModel | None = None
    max_price: float | None = None
    tags: list[str] | None = None
    sort_by: str = Field(
        default="relevance", pattern="^(relevance|rating|downloads|newest|price_low|price_high)$"
    )
    limit: int = Field(default=20, le=100)
    offset: int = Field(default=0, ge=0)


# In-memory storage
_algorithms: dict[str, MarketplaceAlgorithm] = {}
_ratings: dict[str, list[AlgorithmRating]] = {}
_purchases: dict[str, list[AlgorithmPurchase]] = {}


def seed_marketplace():
    """Seed marketplace with sample algorithms."""
    if _algorithms:
        return

    sample_algorithms = [
        {
            "name": "QAOA MaxCut Optimizer",
            "description": "High-performance QAOA for MaxCut problems on weighted graphs",
            "category": AlgorithmCategory.QAOA,
            "author_name": "Quantum Labs",
            "pricing_model": PricingModel.FREE,
            "tags": ["optimization", "graphs", "qaoa"],
            "min_qubits": 4,
            "max_qubits": 20,
        },
        {
            "name": "VQE Molecular Energy Calculator",
            "description": "Accurate ground state energy calculation for small molecules",
            "category": AlgorithmCategory.CHEMISTRY,
            "author_name": "ChemQuantum",
            "pricing_model": PricingModel.ONE_TIME,
            "price": 49.99,
            "tags": ["chemistry", "vqe", "molecules"],
            "min_qubits": 4,
            "max_qubits": 12,
        },
        {
            "name": "Portfolio Optimization Suite",
            "description": "Quantum portfolio optimization for financial applications",
            "category": AlgorithmCategory.FINANCE,
            "author_name": "QuantFinance AI",
            "pricing_model": PricingModel.SUBSCRIPTION,
            "price": 99.0,
            "tags": ["finance", "portfolio", "optimization"],
            "min_qubits": 8,
            "max_qubits": 50,
        },
        {
            "name": "Vehicle Routing Solver",
            "description": "QUBO-based vehicle routing problem solver",
            "category": AlgorithmCategory.LOGISTICS,
            "author_name": "LogiQuant",
            "pricing_model": PricingModel.USAGE_BASED,
            "price": 0.10,
            "tags": ["logistics", "routing", "qubo"],
            "min_qubits": 6,
            "max_qubits": 30,
        },
        {
            "name": "Quantum ML Classifier",
            "description": "Variational quantum classifier for ML tasks",
            "category": AlgorithmCategory.ML,
            "author_name": "QML Research",
            "pricing_model": PricingModel.FREE,
            "tags": ["machine-learning", "classification", "variational"],
            "min_qubits": 2,
            "max_qubits": 16,
        },
    ]

    for algo_data in sample_algorithms:
        algo = MarketplaceAlgorithm.create(
            name=algo_data["name"],
            description=algo_data["description"],
            category=algo_data["category"],
            author_id=f"author_{uuid4().hex[:8]}",
            author_name=algo_data["author_name"],
            pricing_model=algo_data["pricing_model"],
            price=algo_data.get("price", 0),
            tags=algo_data["tags"],
            min_qubits=algo_data["min_qubits"],
            max_qubits=algo_data["max_qubits"],
        )
        algo.downloads = 100 + len(sample_algorithms) * 50
        algo.rating_avg = 4.0 + (len(_algorithms) * 0.2) % 1.0
        algo.rating_count = 10 + len(_algorithms) * 5
        algo.is_verified = True

        _algorithms[algo.algorithm_id] = algo


def search_algorithms(
    query: str | None = None,
    category: AlgorithmCategory | None = None,
    min_rating: float | None = None,
    pricing_model: PricingModel | None = None,
    max_price: float | None = None,
    tags: list[str] | None = None,
    sort_by: str = "relevance",
    limit: int = 20,
    offset: int = 0,
) -> list[MarketplaceAlgorithm]:
    """Search algorithms in marketplace."""
    seed_marketplace()

    results = list(_algorithms.values())

    if query:
        query_lower = query.lower()
        results = [
            a
            for a in results
            if query_lower in a.name.lower()
            or query_lower in a.description.lower()
            or any(query_lower in t.lower() for t in a.tags)
        ]

    if category:
        results = [a for a in results if a.category == category]

    if min_rating is not None:
        results = [a for a in results if a.rating_avg >= min_rating]

    if pricing_model:
        results = [a for a in results if a.pricing_model == pricing_model]

    if max_price is not None:
        results = [a for a in results if a.price <= max_price]

    if tags:
        results = [a for a in results if any(t in a.tags for t in tags)]

    sort_keys = {
        "rating": lambda a: -a.rating_avg,
        "downloads": lambda a: -a.downloads,
        "newest": lambda a: -a.created_at.timestamp(),
        "price_low": lambda a: a.price,
        "price_high": lambda a: -a.price,
        "relevance": lambda a: -(a.rating_avg * 10 + a.downloads / 100),
    }

    results.sort(key=sort_keys.get(sort_by, sort_keys["relevance"]))

    return results[offset : offset + limit]


def purchase_algorithm(
    algorithm_id: str,
    user_id: str,
    tenant_id: str,
) -> AlgorithmPurchase:
    """Purchase an algorithm."""
    seed_marketplace()

    if algorithm_id not in _algorithms:
        raise ValueError("Algorithm not found")

    algo = _algorithms[algorithm_id]

    purchase = AlgorithmPurchase(
        purchase_id=f"purchase_{uuid4().hex[:12]}",
        algorithm_id=algorithm_id,
        user_id=user_id,
        tenant_id=tenant_id,
        price_paid=algo.price,
        purchased_at=datetime.now(timezone.utc),
        license_key=f"KEY-{uuid4().hex[:16].upper()}" if algo.price > 0 else None,
    )

    _purchases.setdefault(user_id, []).append(purchase)
    algo.downloads += 1

    return purchase
