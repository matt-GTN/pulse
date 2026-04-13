from typing import List, Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)

_TOP_N = 15


def rank(scored_pairs: List[Tuple[dict, object]]) -> List[Tuple[dict, object]]:
    """
    Sort by importance (cross-source items get +1 boost), return top _TOP_N.
    Each pair is (item_dict, ScoredResult).
    """
    def sort_key(pair):
        item, scored = pair
        boost = 1 if item.get("cross_source_boost") else 0
        return scored.importance + boost

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
