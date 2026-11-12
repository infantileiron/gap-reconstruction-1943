import os
from pathlib import Path
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/gap-reconstruction.sqlite")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
JWT_SECRET = os.getenv("JWT_SECRET", "gap-reconstruction-development-secret-change-this")
SEED_DEMO = os.getenv("SEED_DEMO", "true").lower() == "true"
TASK_MODE = os.getenv("TASK_MODE", "redis")
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "/tmp/gap-reconstruction-artifacts"))
