"""
Multi-Model Consensus Juror
Hedges against single-model hallucinations by requiring cross-model agreement.
Inspired by TechCrunch: 'Exclusivity is Dead'.
"""

import logging
from typing import Any

from src.utils.model_selector import ModelSelector

logger = logging.getLogger(__name__)


class MultiModelJuror:
    """
    Independent Auditor that cross-checks trade reasoning using a secondary high-frontier model.
    """

    def __init__(self):
        self.selector = ModelSelector()

    def get_consensus(self, trade_proposal: dict[str, Any], primary_reasoning: str) -> bool:
        """
        Queries a secondary model to audit the primary model's decision.
        Returns True if the secondary model agrees with the risk/reward logic.

        Never invents agreement. A previous MVP always returned AGREE (theater);
        that is forbidden. Until a real secondary-provider call is wired, this
        raises so callers fail closed rather than log fake consensus.
        """
        try:
            logger.info("⚖️ Requesting Multi-Model Consensus from Juror...")
            # Live multi-provider audit is not configured. Do not simulate AGREE.
            # Callers must only invoke this after learning_ready (n>=30, edge gates);
            # until then they should skip consensus entirely without claiming agreement.
            _ = (trade_proposal, primary_reasoning, self.selector)
            raise RuntimeError(
                "JUROR_UNAVAILABLE: secondary model not configured; refusing simulated AGREE"
            )
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"⚠️ Consensus Engine Error: {e}. Falling back to conservative safety.")
            return False  # Fail closed on engine error
