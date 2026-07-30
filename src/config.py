"""
Configuration — loaded from environment variables.
Copy .env.example → .env and fill in your values before running.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-20251101")
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))
MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", "15"))

# ---------------------------------------------------------------------------
# SAP S/4HANA connection
# ---------------------------------------------------------------------------
SAP_BASE_URL: str = os.getenv("SAP_BASE_URL", "https://<your-s4hana-host>")
SAP_USER: str = os.getenv("SAP_USER", "")
SAP_PASSWORD: str = os.getenv("SAP_PASSWORD", "")
SAP_CLIENT: str = os.getenv("SAP_CLIENT", "100")
SAP_CERT_PATH: str = os.getenv("SAP_CERT_PATH", "")  # path to PEM or False to skip

# ---------------------------------------------------------------------------
# Business defaults
# ---------------------------------------------------------------------------
DEFAULT_PURCHASING_ORG: str = os.getenv("DEFAULT_PURCHASING_ORG", "1010")

# ---------------------------------------------------------------------------
# Scoring weights — must sum to 1.0
# ---------------------------------------------------------------------------
DEFAULT_SCORING_WEIGHTS: dict[str, float] = {
    "price_weight": float(os.getenv("WEIGHT_PRICE", "0.35")),
    "delivery_weight": float(os.getenv("WEIGHT_DELIVERY", "0.30")),
    "evaluation_weight": float(os.getenv("WEIGHT_EVALUATION", "0.35")),
}

# ---------------------------------------------------------------------------
# Dev / test mode
# ---------------------------------------------------------------------------
USE_MOCK_DATA: bool = os.getenv("USE_MOCK_DATA", "false").lower() == "true"
