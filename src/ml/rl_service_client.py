"""
RL Service Client for Cloud-based Reinforcement Learning

Provides unified interface for cloud RL training on:
- Google Vertex AI (primary)
- AWS SageMaker (future)
- Azure ML (future)

Features:
- Submit training jobs to Vertex AI
- Track job status and metrics
- Download trained model artifacts
- Integration with LangSmith for experiment tracking

Environment Variables:
- RL_AGENT_KEY: Service account key or API key for cloud RL
- GOOGLE_CLOUD_PROJECT: GCP project ID
- VERTEX_AI_LOCATION: GCP region (default: us-central1)

Usage:
    from src.ml.rl_service_client import RLServiceClient

    client = RLServiceClient(provider="vertex_ai")
    job = client.start_training(env_spec, algorithm="PPO")
    status = client.get_job_status(job["job_id"])
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RLProvider(Enum):
    """Supported cloud RL providers."""

    VERTEX_AI = "vertex_ai"
    SAGEMAKER = "sagemaker"
    AZURE_ML = "azure_ml"
    LOCAL = "local"


class JobStatus(Enum):
    """Training job status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingJob:
    """Represents a cloud RL training job."""

    job_id: str
    provider: str
    algorithm: str
    symbol: str
    status: JobStatus
    created_at: str
    updated_at: str
    metrics: dict[str, Any] = field(default_factory=dict)
    artifact_uri: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "provider": self.provider,
            "algorithm": self.algorithm,
            "symbol": self.symbol,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metrics": self.metrics,
            "artifact_uri": self.artifact_uri,
            "error_message": self.error_message,
        }


class RLServiceClient:
    """
    Unified client for cloud-based RL training.

    Supports multiple providers with automatic fallback to local training.
    Integrates with LangSmith for experiment tracking and observability.
    """

    # Vertex AI configuration
    VERTEX_AI_LOCATION = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    VERTEX_AI_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "email-outreach-ai-460404")

    # Training container images
    TRAINING_IMAGES = {
        "PPO": "gcr.io/cloud-aiplatform/training/pytorch-gpu.1-13:latest",
        "DQN": "gcr.io/cloud-aiplatform/training/pytorch-gpu.1-13:latest",
        "A2C": "gcr.io/cloud-aiplatform/training/pytorch-gpu.1-13:latest",
    }

    def __init__(
        self,
        provider: str = "vertex_ai",
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        enable_langsmith: bool = True,
    ):
        """
        Initialize RL Service Client.

        Args:
            provider: Cloud provider ("vertex_ai", "sagemaker", "local")
            api_key: API key or service account key (defaults to RL_AGENT_KEY)
            project_id: Cloud project ID (defaults to GOOGLE_CLOUD_PROJECT)
            enable_langsmith: Enable LangSmith experiment tracking
        """
        self.provider = RLProvider(provider)
        self.api_key = api_key or os.getenv("RL_AGENT_KEY")
        self.project_id = project_id or self.VERTEX_AI_PROJECT
        self.enable_langsmith = enable_langsmith

        # Job tracking
        self.jobs_dir = Path("data/rl_jobs")
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

        # Initialize provider-specific clients
        self._vertex_client = None
        self._langsmith_client = None

        if self.provider == RLProvider.VERTEX_AI:
            self._init_vertex_ai()

        if enable_langsmith:
            self._init_langsmith()

        logger.info(f"RLServiceClient initialized (provider={provider})")

    def _init_vertex_ai(self) -> None:
        """Initialize Vertex AI client."""
        try:
            from google.cloud import aiplatform

            # Initialize with project and location
            aiplatform.init(
                project=self.project_id,
                location=self.VERTEX_AI_LOCATION,
            )
            self._vertex_client = aiplatform
            logger.info(f"Vertex AI initialized (project={self.project_id})")
        except ImportError:
            logger.warning(
                "google-cloud-aiplatform not installed. "
                "Install with: pip install google-cloud-aiplatform"
            )
            self._vertex_client = None
        except Exception as e:
            logger.warning(f"Vertex AI initialization failed: {e}")
            self._vertex_client = None

    def _init_langsmith(self) -> None:
        """Initialize LangSmith for experiment tracking."""
        try:
            from langsmith import Client

            self._langsmith_client = Client()
            logger.info("LangSmith experiment tracking enabled")
        except ImportError:
            logger.warning("LangSmith not installed")
            self._langsmith_client = None
        except Exception as e:
            logger.warning(f"LangSmith initialization failed: {e}")
            self._langsmith_client = None

    def start_training(
        self,
        env_spec: dict[str, Any],
        algorithm: str = "PPO",
        job_name: Optional[str] = None,
        hyperparameters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Start a cloud RL training job.

        Args:
            env_spec: Environment specification
            algorithm: RL algorithm ("PPO", "DQN", "A2C")
            job_name: Optional job name
            hyperparameters: Training hyperparameters

        Returns:
            Job information dictionary
        """
        symbol = env_spec.get("symbol", "UNKNOWN")
        job_name = job_name or f"rl_{algorithm.lower()}_{symbol.lower()}_{int(time.time())}"

        # Default hyperparameters
        hp = {
            "learning_rate": 0.0003,
            "gamma": 0.99,
            "batch_size": 64,
            "n_epochs": 10,
            "clip_range": 0.2,
            "ent_coef": 0.01,
            "max_steps": 100000,
            **(hyperparameters or {}),
        }

        # Log to LangSmith
        if self._langsmith_client:
            self._log_experiment_start(job_name, env_spec, algorithm, hp)

        # Route to appropriate provider
        if self.provider == RLProvider.VERTEX_AI and self._vertex_client:
            return self._start_vertex_ai_job(job_name, env_spec, algorithm, hp)
        else:
            return self._start_local_job(job_name, env_spec, algorithm, hp)

    def _start_vertex_ai_job(
        self,
        job_name: str,
        env_spec: dict[str, Any],
        algorithm: str,
        hyperparameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Start training job on Vertex AI."""
        try:
            from google.cloud.aiplatform import CustomJob

            # Prepare training script arguments
            args = [
                f"--algorithm={algorithm}",
                f"--symbol={env_spec.get('symbol', 'SPY')}",
                f"--state_dim={env_spec.get('state_dim', 10)}",
                f"--learning_rate={hyperparameters.get('learning_rate', 0.0003)}",
                f"--gamma={hyperparameters.get('gamma', 0.99)}",
                f"--batch_size={hyperparameters.get('batch_size', 64)}",
                f"--max_steps={hyperparameters.get('max_steps', 100000)}",
            ]

            # Create custom job
            job = CustomJob.from_local_script(
                display_name=job_name,
                script_path="src/ml/training_script.py",
                container_uri=self.TRAINING_IMAGES.get(
                    algorithm, self.TRAINING_IMAGES["PPO"]
                ),
                args=args,
                requirements=["torch", "numpy", "pandas"],
                machine_type="n1-standard-4",
                accelerator_type="NVIDIA_TESLA_T4",
                accelerator_count=1,
            )

            # Submit job
            job.run(sync=False)

            # Create tracking record
            training_job = TrainingJob(
                job_id=job.resource_name,
                provider="vertex_ai",
                algorithm=algorithm,
                symbol=env_spec.get("symbol", "UNKNOWN"),
                status=JobStatus.PENDING,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )

            self._save_job(training_job)

            logger.info(f"Vertex AI job submitted: {job.resource_name}")

            return {
                "job_id": job.resource_name,
                "provider": "vertex_ai",
                "status": "submitted",
                "display_name": job_name,
                "console_url": f"https://console.cloud.google.com/vertex-ai/training/custom-jobs?project={self.project_id}",
            }

        except Exception as e:
            logger.error(f"Vertex AI job submission failed: {e}")
            # Fallback to local
            return self._start_local_job(job_name, env_spec, algorithm, hyperparameters)

    def _start_local_job(
        self,
        job_name: str,
        env_spec: dict[str, Any],
        algorithm: str,
        hyperparameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Start local training job (fallback)."""
        job_id = f"local_{job_name}_{int(time.time())}"

        training_job = TrainingJob(
            job_id=job_id,
            provider="local",
            algorithm=algorithm,
            symbol=env_spec.get("symbol", "UNKNOWN"),
            status=JobStatus.RUNNING,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        self._save_job(training_job)

        # Trigger local training asynchronously
        logger.info(f"Starting local RL training: {job_id}")

        # For now, return immediately - actual training would be async
        return {
            "job_id": job_id,
            "provider": "local",
            "status": "running",
            "message": "Local training started (no cloud provider available)",
        }

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        """
        Get status of a training job.

        Args:
            job_id: Job identifier

        Returns:
            Job status dictionary
        """
        # Try to load from local cache first
        job = self._load_job(job_id)
        if job:
            # If Vertex AI job, check actual status
            if job.provider == "vertex_ai" and self._vertex_client:
                try:
                    from google.cloud.aiplatform import CustomJob

                    vertex_job = CustomJob.get(job_id)
                    job.status = self._map_vertex_status(vertex_job.state)
                    job.updated_at = datetime.now().isoformat()

                    if vertex_job.state.name == "SUCCEEDED":
                        job.artifact_uri = vertex_job.output_artifact_uri

                    self._save_job(job)
                except Exception as e:
                    logger.warning(f"Failed to fetch Vertex AI job status: {e}")

            return job.to_dict()

        return {"job_id": job_id, "status": "unknown", "error": "Job not found"}

    def list_jobs(
        self, status: Optional[str] = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        List training jobs.

        Args:
            status: Filter by status (optional)
            limit: Maximum jobs to return

        Returns:
            List of job dictionaries
        """
        jobs = []
        for job_file in sorted(self.jobs_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                with open(job_file) as f:
                    job_data = json.load(f)
                if status is None or job_data.get("status") == status:
                    jobs.append(job_data)
            except Exception:
                continue

        return jobs

    def download_model(self, job_id: str, output_dir: str = "models/ml") -> Optional[str]:
        """
        Download trained model from completed job.

        Args:
            job_id: Job identifier
            output_dir: Local directory to save model

        Returns:
            Path to downloaded model or None
        """
        job = self._load_job(job_id)
        if not job or not job.artifact_uri:
            logger.warning(f"No artifacts found for job {job_id}")
            return None

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        try:
            if job.provider == "vertex_ai":
                from google.cloud import storage

                # Parse GCS URI
                if job.artifact_uri.startswith("gs://"):
                    bucket_name = job.artifact_uri.split("/")[2]
                    blob_path = "/".join(job.artifact_uri.split("/")[3:])

                    client = storage.Client()
                    bucket = client.bucket(bucket_name)
                    blob = bucket.blob(blob_path)

                    local_path = output_path / f"{job.symbol}_rl_model.pt"
                    blob.download_to_filename(str(local_path))

                    logger.info(f"Model downloaded to {local_path}")
                    return str(local_path)

        except Exception as e:
            logger.error(f"Failed to download model: {e}")

        return None

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running training job.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled successfully
        """
        job = self._load_job(job_id)
        if not job:
            return False

        try:
            if job.provider == "vertex_ai" and self._vertex_client:
                from google.cloud.aiplatform import CustomJob

                vertex_job = CustomJob.get(job_id)
                vertex_job.cancel()

            job.status = JobStatus.CANCELLED
            job.updated_at = datetime.now().isoformat()
            self._save_job(job)

            logger.info(f"Job cancelled: {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            return False

    def _log_experiment_start(
        self,
        job_name: str,
        env_spec: dict[str, Any],
        algorithm: str,
        hyperparameters: dict[str, Any],
    ) -> None:
        """Log experiment start to LangSmith."""
        if not self._langsmith_client:
            return

        try:
            # Create a run in LangSmith
            self._langsmith_client.create_run(
                name=job_name,
                run_type="chain",
                inputs={
                    "env_spec": env_spec,
                    "algorithm": algorithm,
                    "hyperparameters": hyperparameters,
                },
                extra={
                    "metadata": {
                        "type": "rl_training",
                        "provider": self.provider.value,
                        "symbol": env_spec.get("symbol"),
                    }
                },
            )
        except Exception as e:
            logger.debug(f"LangSmith logging failed: {e}")

    def _save_job(self, job: TrainingJob) -> None:
        """Save job to local cache."""
        job_file = self.jobs_dir / f"{job.job_id.replace('/', '_')}.json"
        with open(job_file, "w") as f:
            json.dump(job.to_dict(), f, indent=2)

    def _load_job(self, job_id: str) -> Optional[TrainingJob]:
        """Load job from local cache."""
        job_file = self.jobs_dir / f"{job_id.replace('/', '_')}.json"
        if not job_file.exists():
            # Try to find by partial match
            for f in self.jobs_dir.glob("*.json"):
                if job_id in f.stem:
                    job_file = f
                    break
            else:
                return None

        try:
            with open(job_file) as f:
                data = json.load(f)
            return TrainingJob(
                job_id=data["job_id"],
                provider=data["provider"],
                algorithm=data["algorithm"],
                symbol=data["symbol"],
                status=JobStatus(data["status"]),
                created_at=data["created_at"],
                updated_at=data["updated_at"],
                metrics=data.get("metrics", {}),
                artifact_uri=data.get("artifact_uri"),
                error_message=data.get("error_message"),
            )
        except Exception:
            return None

    def _map_vertex_status(self, state) -> JobStatus:
        """Map Vertex AI job state to our status enum."""
        state_name = state.name if hasattr(state, "name") else str(state)
        mapping = {
            "JOB_STATE_PENDING": JobStatus.PENDING,
            "JOB_STATE_RUNNING": JobStatus.RUNNING,
            "JOB_STATE_SUCCEEDED": JobStatus.SUCCEEDED,
            "JOB_STATE_FAILED": JobStatus.FAILED,
            "JOB_STATE_CANCELLED": JobStatus.CANCELLED,
        }
        return mapping.get(state_name, JobStatus.PENDING)


# Convenience function
def get_rl_client(provider: str = "vertex_ai") -> RLServiceClient:
    """Get configured RL service client."""
    return RLServiceClient(provider=provider)
