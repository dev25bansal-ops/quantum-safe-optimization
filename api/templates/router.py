"""
Job Templates System.

Provides reusable job configuration templates for common optimization tasks.
"""

import logging
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class TemplateParameter(BaseModel):
    """Template parameter definition."""

    name: str
    type: str = Field(..., pattern="^(string|integer|float|boolean|array|object)$")
    default: Any = None
    required: bool = False
    description: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    options: list[Any] | None = None


class TemplateCreate(BaseModel):
    """Request to create a job template."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    category: str = Field(default="general")
    algorithm: str
    parameters: dict[str, Any]
    parameter_schema: list[TemplateParameter] | None = None
    backend_config: dict[str, Any] | None = None
    tags: list[str] = []
    public: bool = False


class TemplateUpdate(BaseModel):
    """Request to update a job template."""

    name: str | None = None
    description: str | None = None
    category: str | None = None
    algorithm: str | None = None
    parameters: dict[str, Any] | None = None
    parameter_schema: list[TemplateParameter] | None = None
    backend_config: dict[str, Any] | None = None
    tags: list[str] | None = None
    public: bool | None = None


class TemplateResponse(BaseModel):
    """Template response."""

    id: str
    name: str
    description: str | None
    category: str
    algorithm: str
    parameters: dict[str, Any]
    parameter_schema: list[dict[str, Any]] | None
    backend_config: dict[str, Any] | None
    tags: list[str]
    public: bool
    usage_count: int
    created_at: str
    updated_at: str
    created_by: str


class TemplateListResponse(BaseModel):
    """List of templates."""

    templates: list[TemplateResponse]
    total: int


class InstantiateTemplateRequest(BaseModel):
    """Request to instantiate a template."""

    parameters: dict[str, Any] = {}
    overrides: dict[str, Any] | None = None


# Storage
_templates: dict[str, dict[str, Any]] = {}


def get_user_id() -> str:
    return "user_default"


def _generate_template_id() -> str:
    return f"tpl_{secrets.token_hex(8)}"


def _validate_parameters(
    params: dict[str, Any],
    schema: list[TemplateParameter] | None,
) -> dict[str, Any]:
    """Validate and apply defaults to parameters."""
    result = {}

    if not schema:
        return params

    for param_def in schema:
        name = param_def.name
        value = params.get(name, param_def.default)

        if param_def.required and value is None:
            raise HTTPException(status_code=400, detail=f"Required parameter '{name}' is missing")

        if value is not None:
            if param_def.type == "integer":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    raise HTTPException(
                        status_code=400, detail=f"Parameter '{name}' must be an integer"
                    )
            elif param_def.type == "float":
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    raise HTTPException(
                        status_code=400, detail=f"Parameter '{name}' must be a float"
                    )
            elif param_def.type == "boolean":
                if not isinstance(value, bool):
                    raise HTTPException(
                        status_code=400, detail=f"Parameter '{name}' must be a boolean"
                    )

            if param_def.min_value is not None and isinstance(value, (int, float)):
                if value < param_def.min_value:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Parameter '{name}' must be >= {param_def.min_value}",
                    )
            if param_def.max_value is not None and isinstance(value, (int, float)):
                if value > param_def.max_value:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Parameter '{name}' must be <= {param_def.max_value}",
                    )
            if param_def.options and value not in param_def.options:
                raise HTTPException(
                    status_code=400,
                    detail=f"Parameter '{name}' must be one of {param_def.options}",
                )

        result[name] = value

    return result


# Built-in templates
BUILTIN_TEMPLATES = {
    "qaoa_maxcut": {
        "id": "tpl_builtin_qaoa_maxcut",
        "name": "QAOA MaxCut",
        "description": "Solve the Maximum Cut problem using QAOA",
        "category": "optimization",
        "algorithm": "qaoa",
        "parameters": {
            "p": 2,
            "shots": 1024,
            "optimizer": "COBYLA",
        },
        "parameter_schema": [
            TemplateParameter(
                name="p",
                type="integer",
                default=2,
                min_value=1,
                max_value=10,
                description="QAOA depth",
            ),
            TemplateParameter(
                name="shots",
                type="integer",
                default=1024,
                min_value=100,
                max_value=10000,
                description="Number of shots",
            ),
            TemplateParameter(
                name="optimizer",
                type="string",
                default="COBYLA",
                options=["COBYLA", "SPSA", "ADAM"],
                description="Classical optimizer",
            ),
        ],
        "backend_config": {"type": "simulator", "noise_model": None},
        "tags": ["qaoa", "maxcut", "graph"],
        "public": True,
        "usage_count": 0,
        "created_by": "system",
    },
    "vqe_ground_state": {
        "id": "tpl_builtin_vqe_ground_state",
        "name": "VQE Ground State",
        "description": "Find molecular ground state energy using VQE",
        "category": "chemistry",
        "algorithm": "vqe",
        "parameters": {
            "ansatz": "UCCSD",
            "shots": 1024,
            "optimizer": "SPSA",
        },
        "parameter_schema": [
            TemplateParameter(
                name="ansatz",
                type="string",
                default="UCCSD",
                options=["UCCSD", "HardwareEfficient", "QAOA"],
                description="Variational ansatz",
            ),
            TemplateParameter(
                name="shots",
                type="integer",
                default=1024,
                min_value=100,
                max_value=10000,
                description="Number of shots",
            ),
            TemplateParameter(
                name="optimizer",
                type="string",
                default="SPSA",
                options=["COBYLA", "SPSA", "ADAM", "L_BFGS_B"],
                description="Classical optimizer",
            ),
        ],
        "backend_config": {"type": "simulator"},
        "tags": ["vqe", "chemistry", "molecular"],
        "public": True,
        "usage_count": 0,
        "created_by": "system",
    },
    "annealing_qubo": {
        "id": "tpl_builtin_annealing_qubo",
        "name": "Quantum Annealing QUBO",
        "description": "Solve QUBO problems using quantum annealing",
        "category": "optimization",
        "algorithm": "annealing",
        "parameters": {
            "num_reads": 1000,
            "annealing_time": 20,
        },
        "parameter_schema": [
            TemplateParameter(
                name="num_reads",
                type="integer",
                default=1000,
                min_value=100,
                max_value=10000,
                description="Number of annealing reads",
            ),
            TemplateParameter(
                name="annealing_time",
                type="integer",
                default=20,
                min_value=1,
                max_value=2000,
                description="Annealing time (μs)",
            ),
        ],
        "backend_config": {"provider": "dwave"},
        "tags": ["annealing", "qubo", "optimization"],
        "public": True,
        "usage_count": 0,
        "created_by": "system",
    },
}

# Initialize with built-in templates
_templates.update(BUILTIN_TEMPLATES)


@router.post("/", response_model=TemplateResponse, status_code=201)
async def create_template(
    request: TemplateCreate,
    user_id: str = Depends(get_user_id),
):
    """Create a new job template."""
    template_id = _generate_template_id()
    now = datetime.now(UTC).isoformat()

    _templates[template_id] = {
        "id": template_id,
        "name": request.name,
        "description": request.description,
        "category": request.category,
        "algorithm": request.algorithm,
        "parameters": request.parameters,
        "parameter_schema": [p.model_dump() for p in request.parameter_schema]
        if request.parameter_schema
        else None,
        "backend_config": request.backend_config,
        "tags": request.tags,
        "public": request.public,
        "usage_count": 0,
        "created_at": now,
        "updated_at": now,
        "created_by": user_id,
    }

    logger.info("template_created", template_id=template_id, name=request.name)

    return TemplateResponse(**_templates[template_id])


@router.get("/", response_model=TemplateListResponse)
async def list_templates(
    user_id: str = Depends(get_user_id),
    category: str | None = None,
    algorithm: str | None = None,
    tag: str | None = None,
    public_only: bool = False,
    search: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List available templates."""
    templates = list(_templates.values())

    if category:
        templates = [t for t in templates if t["category"] == category]
    if algorithm:
        templates = [t for t in templates if t["algorithm"] == algorithm]
    if tag:
        templates = [t for t in templates if tag in t.get("tags", [])]
    if public_only:
        templates = [t for t in templates if t["public"]]
    if search:
        search_lower = search.lower()
        templates = [
            t
            for t in templates
            if search_lower in t["name"].lower()
            or (t.get("description") and search_lower in t["description"].lower())
        ]

    templates = sorted(templates, key=lambda x: (-x["usage_count"], x["name"]))

    return TemplateListResponse(
        templates=[TemplateResponse(**t) for t in templates[offset : offset + limit]],
        total=len(templates),
    )


@router.get("/categories")
async def list_categories(user_id: str = Depends(get_user_id)):
    """List all template categories."""
    categories = {}
    for t in _templates.values():
        cat = t["category"]
        categories[cat] = categories.get(cat, 0) + 1

    return {"categories": [{"name": k, "count": v} for k, v in sorted(categories.items())]}


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    user_id: str = Depends(get_user_id),
):
    """Get a template by ID."""
    if template_id not in _templates:
        raise HTTPException(status_code=404, detail="Template not found")

    return TemplateResponse(**_templates[template_id])


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: TemplateUpdate,
    user_id: str = Depends(get_user_id),
):
    """Update a template."""
    if template_id not in _templates:
        raise HTTPException(status_code=404, detail="Template not found")

    template = _templates[template_id]

    if template["created_by"] != user_id and template["created_by"] != "system":
        raise HTTPException(status_code=403, detail="Not authorized to update this template")

    update_data = request.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if key == "parameter_schema" and value:
            template[key] = [p.model_dump() if hasattr(p, "model_dump") else p for p in value]
        else:
            template[key] = value

    template["updated_at"] = datetime.now(UTC).isoformat()

    return TemplateResponse(**template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_user_id),
):
    """Delete a template."""
    if template_id not in _templates:
        raise HTTPException(status_code=404, detail="Template not found")

    template = _templates[template_id]

    if template["created_by"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this template")

    del _templates[template_id]

    return {"status": "deleted", "template_id": template_id}


@router.post("/{template_id}/instantiate")
async def instantiate_template(
    template_id: str,
    request: InstantiateTemplateRequest,
    user_id: str = Depends(get_user_id),
):
    """Create a job configuration from a template."""
    if template_id not in _templates:
        raise HTTPException(status_code=404, detail="Template not found")

    template = _templates[template_id]

    # Validate parameters
    schema = None
    if template.get("parameter_schema"):
        schema = [TemplateParameter(**p) for p in template["parameter_schema"]]

    validated_params = _validate_parameters(request.parameters, schema)

    # Merge parameters: template defaults -> validated params -> overrides
    job_config = {
        "algorithm": template["algorithm"],
        "parameters": {**template["parameters"], **validated_params},
        "backend_config": template.get("backend_config", {}),
    }

    if request.overrides:
        job_config["parameters"].update(request.overrides.get("parameters", {}))
        if "backend_config" in request.overrides:
            job_config["backend_config"].update(request.overrides["backend_config"])

    # Increment usage count
    template["usage_count"] = template.get("usage_count", 0) + 1

    logger.info("template_instantiated", template_id=template_id, user_id=user_id)

    return {
        "template_id": template_id,
        "template_name": template["name"],
        "job_config": job_config,
        "instantiated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/{template_id}/duplicate", response_model=TemplateResponse, status_code=201)
async def duplicate_template(
    template_id: str,
    user_id: str = Depends(get_user_id),
):
    """Duplicate an existing template."""
    if template_id not in _templates:
        raise HTTPException(status_code=404, detail="Template not found")

    source = _templates[template_id]
    new_id = _generate_template_id()
    now = datetime.now(UTC).isoformat()

    new_template = {
        **source,
        "id": new_id,
        "name": f"{source['name']} (Copy)",
        "public": False,
        "usage_count": 0,
        "created_at": now,
        "updated_at": now,
        "created_by": user_id,
    }

    _templates[new_id] = new_template

    return TemplateResponse(**new_template)


@router.get("/health")
async def templates_health():
    return {
        "status": "healthy",
        "templates_count": len(_templates),
        "builtin_count": len(BUILTIN_TEMPLATES),
        "timestamp": datetime.now(UTC).isoformat(),
    }
