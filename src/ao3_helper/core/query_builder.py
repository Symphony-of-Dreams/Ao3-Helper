import random
import re
from typing import Any, Dict

import AO3

from ao3_helper.logger_setup import logger


def _normalize_fandom_name(name: str) -> str:
    """
    Pulisce il nome di un fandom per l'aggregazione, rimuovendo qualificatori
    come '(Manga)' e convertendo in minuscolo.
    """
    return re.sub(r"\s*\([^)]*\)", "", name).strip().lower()


def build_discovery_query(profile: Dict[str, Any], search_params: Dict[str, Any]) -> AO3.Search:
    """
    Costruisce un oggetto AO3.Search configurato basandosi su un'analisi
    intelligente e randomica del profilo dell'utente per la scoperta di nuove opere.

    Args:
        profile: I dati aggregati dall'AnalysisEngine (tws, aws, etc.).
        search_params: I parametri scelti dall'utente nella UI (strategia, parole, etc.).

    Returns:
        Un'istanza di AO3.Search pronta per l'esecuzione.
    """
    strategy = search_params.get("strategy", "safe_bet")

    aggregated_fandoms: Dict[str, Dict[str, Any]] = {}
    for fandom in profile.get("fandoms", []):
        original_name = fandom["name"]
        normalized_key = _normalize_fandom_name(original_name)
        if normalized_key not in aggregated_fandoms:
            aggregated_fandoms[normalized_key] = {"tws": 0, "representative_name": original_name}
        aggregated_fandoms[normalized_key]["tws"] += fandom["tws"]

    sorted_fandoms = sorted(aggregated_fandoms.values(), key=lambda item: item["tws"], reverse=True)

    if not sorted_fandoms:
        raise ValueError("Cannot build query: user profile has no fandoms.")

    fandom_pool = [f["representative_name"] for f in sorted_fandoms[:3]]
    fandom_weights = [f["tws"] for f in sorted_fandoms[:3]]
    if fandom_pool:
        fandom_to_search = random.choices(fandom_pool, weights=fandom_weights, k=1)[0]
    else:
        fandom_to_search = sorted_fandoms[0]["representative_name"]
    logger.info(f"Query Builder randomly selected Fandom (weighted): '{fandom_to_search}'")

    if strategy == "hidden_gem":
        ao3_sort_column = "kudos_count"
    else:
        user_sort_choice = search_params.get("sort_by", "best_match")
        ao3_sort_column = "kudos_count" if user_sort_choice == "best_match" else user_sort_choice

    search_query = AO3.Search(
        fandoms=f'"{fandom_to_search}"', word_count=search_params.get("word_count"), sort_column=ao3_sort_column
    )
    is_complete_param = search_params.get("is_complete")
    if is_complete_param is not None:
        search_query.complete = is_complete_param

    anchor_pool = []
    anchor_pool.extend(profile.get("relationships", [])[:10])
    anchor_pool.extend(profile.get("characters", [])[:10])
    anchor_pool.sort(key=lambda x: x["tws"], reverse=True)

    context_pool = profile.get("tags", [])[:20]

    if not anchor_pool or not context_pool:
        raise ValueError("Not enough profile data (anchors/context) to build a hybrid query.")

    selected_anchor = random.choices([e["name"] for e in anchor_pool], weights=[e["tws"] for e in anchor_pool], k=1)[0]

    num_context_tags = 5
    selected_context = []
    if len(context_pool) >= num_context_tags:
        selected_context = random.choices(
            [t["name"] for t in context_pool], weights=[t["tws"] for t in context_pool], k=num_context_tags
        )
    else:
        selected_context = [t["name"] for t in context_pool]

    logger.info(f"Query Builder Anchor: '{selected_anchor}'")
    logger.info(f"Query Builder Context Tags: {selected_context}")

    num_and_tags = random.randint(1, 2)
    and_tags = selected_context[:num_and_tags]
    or_tags = selected_context[num_and_tags:]

    query_parts = [f'"{selected_anchor}"']
    query_parts.extend(f'"{tag}"' for tag in and_tags)

    if or_tags:
        or_part = " OR ".join(f'"{tag}"' for tag in or_tags)
        query_parts.append(f"({or_part})")

    hybrid_query_string = " ".join(query_parts)

    if strategy == "safe_bet":
        search_query.any_field = hybrid_query_string

    elif strategy == "hidden_gem":
        search_query.any_field = f"({hybrid_query_string}) kudos:<300"

    elif strategy == "wildcard":
        if len(anchor_pool) >= 2:
            wildcard_anchors = random.sample([a["name"] for a in anchor_pool[:5]], 2)
            search_query.any_field = " ".join(f'"{a}"' for a in wildcard_anchors)
            logger.info(f"Wildcard strategy is using AND logic for anchors: {wildcard_anchors}")
        else:
            search_query.any_field = hybrid_query_string

    logger.info(f"Query Builder constructed final query string: '{search_query.any_field}'")
    logger.info(f"Query Builder constructed params: {search_query.__dict__}")
    return search_query
