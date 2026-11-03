"""SIH26051 - Rank candidates by total score."""


def rank_candidates(candidates, top=10):
    ordered = sorted(candidates, key=lambda c: c["score"]["total"], reverse=True)
    for i, c in enumerate(ordered[:top], 1):
        c["rank"] = i
    return ordered[:top]