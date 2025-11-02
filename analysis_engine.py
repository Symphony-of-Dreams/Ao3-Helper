# analysis_engine.py

import math
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from database import get_filtered_fics


class AnalysisEngine:
    """
    A stateful service that calculates and maintains weighted scores for authors,
    tags, fandoms, and other entities based on user behavior.

    This engine uses a v3.1 weighting model that differentiates scores for authors
    based on user ratings (stars).
    """

    def __init__(self):
        # Internal cache for all scores.
        # Structure: {'entity_name': {'tws': float, 'fic_count': int}}
        self.author_scores: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"tws": 0.0, "fic_count": 0})
        self.fandom_scores: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"tws": 0.0, "fic_count": 0})
        self.tag_scores: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"tws": 0.0, "fic_count": 0})
        self.relationship_scores: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"tws": 0.0, "fic_count": 0})
        self.character_scores: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"tws": 0.0, "fic_count": 0})

        self.entity_map = [
            (self.fandom_scores, "fandoms"),
            (self.tag_scores, "tags"),
            (self.relationship_scores, "relationships"),
            (self.character_scores, "characters"),
        ]

    def _calculate_fic_scores(self, fic_data: Dict[str, Any]) -> Tuple[float, float]:
        """Calculates the two types of scores for a given fic."""

        # 1. Base Score (Engagement + Intent)
        engagement_score = 0.0
        if fic_data.get("is_in_history") and fic_data.get("visit_count", 0) > 0:
            visit_count = fic_data.get("visit_count", 1)
            engagement_score = math.log(visit_count) + 1

        intent_score = 1.5 if fic_data.get("is_in_library") else 0.0
        base_score = engagement_score + intent_score

        # 2. Status Multiplier
        status = fic_data.get("status", "To Read")
        status_map = {"Read": 1.1, "Kudosed": 1.25, "Commented": 1.5}
        status_multiplier = status_map.get(status, 1.0)

        # 3. Rating Multiplier (for author score only)
        rating = fic_data.get("user_rating", 0) or 0
        rating_map = {1: 0.4, 2: 0.7, 3: 1.0, 4: 1.2, 5: 1.5}
        rating_multiplier = rating_map.get(rating, 1.0)

        # 4. Final Scores
        entity_score = base_score * status_multiplier
        author_score = entity_score * rating_multiplier

        return entity_score, author_score

    def _update_scores(self, fic_data: Dict[str, Any], operation: str = "add"):
        """Internal helper to add or subtract fic scores from the cache."""
        entity_score, author_score = self._calculate_fic_scores(fic_data)

        multiplier = 1 if operation == "add" else -1

        # Update author score
        if fic_data.get("author"):
            authors = [a.strip() for a in fic_data["author"].split(",") if a.strip()]
            for author_name in authors:
                self.author_scores[author_name]["tws"] += author_score * multiplier
                self.author_scores[author_name]["fic_count"] += 1 * multiplier

        # Update scores for all other entities
        for scores_dict, key in self.entity_map:
            if fic_data.get(key):
                items = [item.strip() for item in fic_data[key].split(",") if item.strip()]
                for item_name in items:
                    scores_dict[item_name]["tws"] += entity_score * multiplier
                    scores_dict[item_name]["fic_count"] += 1 * multiplier

    def full_recalculation(self):
        """Performs a full analysis of all fics in the database. Should be called on startup."""
        all_fics = get_filtered_fics(view_filter="all")

        # Reset all scores
        self.author_scores.clear()
        self.fandom_scores.clear()
        self.tag_scores.clear()
        self.relationship_scores.clear()
        self.character_scores.clear()

        for fic in all_fics:
            self.add_fic(fic)

    def add_fic(self, fic_data: Dict[str, Any]):
        """Incrementally adds a fic's scores to the analysis cache."""
        self._update_scores(fic_data, operation="add")

    def remove_fic(self, fic_data: Dict[str, Any]):
        """Incrementally removes a fic's scores from the analysis cache."""
        self._update_scores(fic_data, operation="subtract")

    def update_fic(self, old_fic_data: Dict[str, Any], new_fic_data: Dict[str, Any]):
        """Efficiently updates a fic's scores by subtracting the old and adding the new."""
        self.remove_fic(old_fic_data)
        self.add_fic(new_fic_data)

    def get_analysis_results(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns the current state of the analysis cache, processed and sorted."""
        final_analysis: Dict[str, List[Dict[str, Any]]] = {}

        def process_scores(scores_dict: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
            processed_list = []
            for name, data in scores_dict.items():
                if data["fic_count"] <= 0:
                    continue
                tws = data["tws"]
                fic_count = data["fic_count"]
                aws = tws / fic_count
                processed_list.append(
                    {"name": name, "tws": round(tws, 2), "aws": round(aws, 2), "fic_count": fic_count}
                )
            return sorted(processed_list, key=lambda x: x["tws"], reverse=True)

        final_analysis["authors"] = process_scores(self.author_scores)
        final_analysis["fandoms"] = process_scores(self.fandom_scores)
        final_analysis["tags"] = process_scores(self.tag_scores)
        final_analysis["relationships"] = process_scores(self.relationship_scores)
        final_analysis["characters"] = process_scores(self.character_scores)

        return final_analysis

    # --- INSERISCI IL NUOVO METODO QUI ---

    def generate_recommendations(self, fics_to_consider: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculates a 'recommendation score' for a list of candidate fics based on
        the pre-calculated TWS scores of their associated entities.

        Args:
            fics_to_consider: A list of fic dictionaries (e.g., all 'To Read' fics).

        Returns:
            A new list of fic dictionaries, each augmented with a 'recommendation_score',
            sorted from highest to lowest score.
        """
        recommendations = []

        # Map the fic data keys to the engine's score caches for easy iteration.
        entity_mappings = [
            ("author", self.author_scores),
            ("fandoms", self.fandom_scores),
            ("tags", self.tag_scores),
            ("relationships", self.relationship_scores),
            ("characters", self.character_scores),
        ]

        for fic in fics_to_consider:
            recommendation_score = 0.0

            # Iterate through each type of entity (author, fandoms, etc.) for the fic.
            for fic_key, score_cache in entity_mappings:
                entity_string = fic.get(fic_key)

                # If the entity string exists (e.g., 'Fandom A, Fandom B')
                if entity_string:
                    # Split into individual items and strip whitespace.
                    items = [item.strip() for item in entity_string.split(",") if item.strip()]

                    for item_name in items:
                        # Safely get the TWS from the cache. If an entity is not in the
                        # cache, it contributes 0 to the score.
                        score_data = score_cache.get(item_name, {"tws": 0.0})
                        recommendation_score += score_data["tws"]

            # Create a copy of the fic dictionary and add the calculated score.
            fic_with_score = fic.copy()
            fic_with_score["recommendation_score"] = round(recommendation_score, 2)
            recommendations.append(fic_with_score)

        # Sort the final list by the new score in descending order.
        return sorted(recommendations, key=lambda x: x["recommendation_score"], reverse=True)
