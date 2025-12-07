"""
Model registry for versioning and lifecycle management.
"""

import json
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ModelStage(Enum):
    """Model lifecycle stages."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


@dataclass
class ModelVersion:
    """A versioned model with metadata."""

    model_name: str
    version: int
    stage: ModelStage
    created_at: str
    experiment_run_id: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    description: str = ""
    tags: list[str] = field(default_factory=list)
    artifact_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model_name": self.model_name,
            "version": self.version,
            "stage": self.stage.value,
            "created_at": self.created_at,
            "experiment_run_id": self.experiment_run_id,
            "metrics": self.metrics,
            "description": self.description,
            "tags": self.tags,
            "artifact_path": self.artifact_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelVersion":
        """Create from dictionary."""
        return cls(
            model_name=data["model_name"],
            version=data["version"],
            stage=ModelStage(data["stage"]),
            created_at=data["created_at"],
            experiment_run_id=data.get("experiment_run_id"),
            metrics=data.get("metrics", {}),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            artifact_path=data.get("artifact_path"),
        )


class ModelRegistry:
    """
    Registry for managing model versions and lifecycle.

    Example:
        >>> registry = ModelRegistry()
        >>> version = registry.register_model(
        ...     "momentum_model", my_model,
        ...     metrics={"sharpe": 1.5}
        ... )
        >>> registry.transition_stage("momentum_model", 1, ModelStage.PRODUCTION)
        >>> model = registry.load_model("momentum_model", stage=ModelStage.PRODUCTION)
    """

    def __init__(self, registry_dir: str = "models/registry"):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._load_registry()

    def _load_registry(self) -> None:
        """Load registry metadata from disk."""
        self.registry_file = self.registry_dir / "registry.json"
        if self.registry_file.exists():
            with open(self.registry_file) as f:
                self._registry = json.load(f)
        else:
            self._registry = {"models": {}}

    def _save_registry(self) -> None:
        """Save registry metadata to disk."""
        with open(self.registry_file, "w") as f:
            json.dump(self._registry, f, indent=2)

    def register_model(
        self,
        model_name: str,
        model: Any,
        experiment_run_id: str | None = None,
        metrics: dict[str, float] | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ) -> ModelVersion:
        """
        Register a new model version.

        Args:
            model_name: Name of the model
            model: Model object to save
            experiment_run_id: Optional linked experiment run
            metrics: Performance metrics
            description: Model description
            tags: Optional tags

        Returns:
            ModelVersion with version number
        """
        if model_name not in self._registry["models"]:
            self._registry["models"][model_name] = {"versions": []}

        versions = self._registry["models"][model_name]["versions"]
        next_version = len(versions) + 1

        model_dir = self.registry_dir / model_name
        model_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = str(model_dir / f"v{next_version}.pkl")

        with open(artifact_path, "wb") as f:
            pickle.dump(model, f)

        version = ModelVersion(
            model_name=model_name,
            version=next_version,
            stage=ModelStage.DEVELOPMENT,
            created_at=datetime.now().isoformat(),
            experiment_run_id=experiment_run_id,
            metrics=metrics or {},
            description=description,
            tags=tags or [],
            artifact_path=artifact_path,
        )

        versions.append(version.to_dict())
        self._save_registry()

        return version

    def get_model_versions(self, model_name: str) -> list[ModelVersion]:
        """Get all versions of a model."""
        if model_name not in self._registry["models"]:
            return []

        return [ModelVersion.from_dict(v) for v in self._registry["models"][model_name]["versions"]]

    def get_latest_version(
        self,
        model_name: str,
        stage: ModelStage | None = None,
    ) -> ModelVersion | None:
        """Get the latest version, optionally filtered by stage."""
        versions = self.get_model_versions(model_name)

        if stage:
            versions = [v for v in versions if v.stage == stage]

        if not versions:
            return None

        return max(versions, key=lambda v: v.version)

    def transition_stage(
        self,
        model_name: str,
        version: int,
        new_stage: ModelStage,
    ) -> ModelVersion:
        """Transition a model version to a new stage."""
        if model_name not in self._registry["models"]:
            raise ValueError(f"Model not found: {model_name}")

        versions = self._registry["models"][model_name]["versions"]
        for v in versions:
            if v["version"] == version:
                v["stage"] = new_stage.value
                self._save_registry()
                return ModelVersion.from_dict(v)

        raise ValueError(f"Version {version} not found for model {model_name}")

    def load_model(
        self,
        model_name: str,
        version: int | None = None,
        stage: ModelStage | None = None,
    ) -> Any:
        """
        Load a model from the registry.

        Args:
            model_name: Model name
            version: Specific version (if None, uses latest)
            stage: Filter by stage (if None, gets latest of any stage)

        Returns:
            Loaded model object
        """
        if version:
            versions = self.get_model_versions(model_name)
            model_version = next((v for v in versions if v.version == version), None)
        else:
            model_version = self.get_latest_version(model_name, stage)

        if model_version is None:
            raise ValueError(f"No matching model found: {model_name}")

        with open(model_version.artifact_path, "rb") as f:
            return pickle.load(f)  # noqa: S301 - Models are trusted internal artifacts

    def list_models(self) -> list[str]:
        """List all registered model names."""
        return list(self._registry["models"].keys())

    def delete_version(self, model_name: str, version: int) -> None:
        """Delete a specific model version."""
        if model_name not in self._registry["models"]:
            return

        versions = self._registry["models"][model_name]["versions"]
        for i, v in enumerate(versions):
            if v["version"] == version:
                artifact_path = Path(v["artifact_path"])
                if artifact_path.exists():
                    artifact_path.unlink()
                versions.pop(i)
                self._save_registry()
                return
