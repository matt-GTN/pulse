from typing import List, Tuple, Optional, Dict

from src.utils.logger import get_logger

logger = get_logger(__name__)

_TOP_N = 15


def rank(
    scored_pairs: List[Tuple[dict, object]],
    source_weights: Optional[Dict[str, int]] = None,
) -> List[Tuple[dict, object]]:
    """
    Sort by LLM importance + cross-source boost + editorial weight, return top _TOP_N.
    Editorial boost = source_weights[item.source] - 1 (so weight=1 is baseline).
    """
    source_weights = source_weights or {}

    def sort_key(pair):
        item, scored = pair
        # LLM compressed to 0-3 — tiebreaker only, not the dominant signal
        llm = round(scored.importance / 10 * 3)
        # Cross-source: same story on multiple sources = strong validation signal
        cross_boost = 4 if item.get("cross_source_boost") else 0
        # Editorial weight: (weight-1)*2 → weight 1=0, weight 2=2, weight 3=4
        editorial_boost = (source_weights.get(item.get("source", ""), 1) - 1) * 2
        return llm + cross_boost + editorial_boost

    ranked = sorted(scored_pairs, key=sort_key, reverse=True)
    top = ranked[:_TOP_N]

    logger.info(
        "Ranked %d items → top %d (importance range %d–%d)",
        len(scored_pairs),
        len(top),
        top[-1][1].importance if top else 0,
        top[0][1].importance if top else 0,
    )
    return top
