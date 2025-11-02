# tests/test_analysis_engine.py


import pytest

# Import the class, not the function
from analysis_engine import AnalysisEngine
from models import Fic

TEST_FIC_DEFAULTS = {
    "title": "Test Title",
    "fandoms": "Test Fandom",
    "tags": "Test Tag",
    "author": "Test Author",
    "relationships": "A/B",
    "characters": "A, B",
    "is_complete": True,
    "user_rating": 0,
    "status": "To Read",
    "is_in_library": False,
    "is_in_history": False,
    "visit_count": 0,
}


@pytest.fixture
def analysis_test_data():
    """Provides a controlled dataset to test the AnalysisEngine."""
    return [
        # Fic A: High engagement, low rating (should penalize author)
        # base=ln(50)+1+1.5=~6.41; status=Commented(1.5); rating=1-star(0.4)
        # entity_score = 6.41 * 1.5 = 9.62
        # author_score = 9.62 * 0.4 = 3.85
        {
            "url": "fic_A",
            "author": "Author One",
            "fandoms": "Fandom X",
            "tags": "Angst",
            "is_in_history": True,
            "visit_count": 50,
            "is_in_library": True,
            "status": "Commented",
            "user_rating": 1,
        },
        # Fic B: High intent, high rating (should reward author)
        # base=1.5; status=To Read(1.0); rating=5-star(1.5)
        # entity_score = 1.5 * 1.0 = 1.5
        # author_score = 1.5 * 1.5 = 2.25
        {
            "url": "fic_B",
            "author": "Author Two",
            "fandoms": "Fandom Y",
            "tags": "Fluff",
            "is_in_library": True,
            "user_rating": 5,
        },
        # Fic C: Balanced, neutral rating
        # base=ln(5)+1+1.5=~4.11; status=Kudosed(1.25); rating=3-star(1.0)
        # entity_score = 4.11 * 1.25 = 5.14
        # author_score = 5.14 * 1.0 = 5.14
        {
            "url": "fic_C",
            "author": "Author One",
            "fandoms": "Fandom X",
            "tags": "Angst, Fluff",
            "is_in_history": True,
            "visit_count": 5,
            "is_in_library": True,
            "status": "Kudosed",
            "user_rating": 3,
        },
    ]


@pytest.fixture
def populated_engine(db_connection, analysis_test_data):
    """Fixture to get an AnalysisEngine instance after a full calculation."""
    for fic_data in analysis_test_data:
        full_data = {**TEST_FIC_DEFAULTS, **fic_data}
        Fic.create(**full_data)

    engine = AnalysisEngine()
    engine.full_recalculation()
    return engine


def test_full_recalculation(populated_engine):
    """Tests that the initial full calculation produces correct results."""
    results = populated_engine.get_analysis_results()

    # --- Verify Author Scores (Differentiated) ---
    authors = {a["name"]: a for a in results["authors"]}
    # Author One = Fic A (3.85) + Fic C (5.14) = 8.99
    assert authors["Author One"]["tws"] == pytest.approx(8.99, 0.01)
    # Author Two = Fic B (2.25)
    assert authors["Author Two"]["tws"] == pytest.approx(2.25, 0.01)

    # --- Verify Tag Scores (Neutral) ---
    tags = {t["name"]: t for t in results["tags"]}
    # Angst = Fic A (9.62) + Fic C (5.14) = 14.76
    assert tags["Angst"]["tws"] == pytest.approx(14.76, 0.01)
    # Fluff = Fic B (1.5) + Fic C (5.14) = 6.64
    assert tags["Fluff"]["tws"] == pytest.approx(6.64, 0.01)


def test_incremental_updates(db_connection, analysis_test_data):
    """Tests the add, remove, and update methods of the engine."""
    engine = AnalysisEngine()

    # --- Test Add ---
    fic_a_data = {**TEST_FIC_DEFAULTS, **analysis_test_data[0]}
    engine.add_fic(fic_a_data)

    author_one_score = engine.author_scores["Author One"]["tws"]
    assert author_one_score == pytest.approx(3.85, 0.01)

    angst_score = engine.tag_scores["Angst"]["tws"]
    assert angst_score == pytest.approx(9.62, 0.01)

    # --- Test Remove ---
    engine.remove_fic(fic_a_data)
    assert engine.author_scores["Author One"]["tws"] == pytest.approx(0.0)
    assert engine.tag_scores["Angst"]["tws"] == pytest.approx(0.0)

    # --- Test Update ---
    # First, add the original data
    engine.add_fic(fic_a_data)

    # Now, create an "updated" version where the rating changed from 1 to 5 stars
    updated_fic_a_data = fic_a_data.copy()
    updated_fic_a_data["user_rating"] = 5
    # New author_score = 9.62 * 1.5 = 14.43

    engine.update_fic(old_fic_data=fic_a_data, new_fic_data=updated_fic_a_data)

    # The tag score should be unchanged
    assert engine.tag_scores["Angst"]["tws"] == pytest.approx(9.62, 0.01)
    # But the author score should reflect the new rating
    assert engine.author_scores["Author One"]["tws"] == pytest.approx(14.43, 0.01)


def test_generate_recommendations():
    """
    Tests the recommendation engine's ability to score and sort candidate fics
    based on a pre-existing user profile (reading history).
    """
    engine = AnalysisEngine()

    # 1. SETUP: Simulate a user's reading history to populate the engine's cache.
    # This fic establishes a strong preference for 'SuperAuthor', 'FandomA', and 'GoodTrope'.
    fic_history_strong = {
        "author": "SuperAuthor",
        "fandoms": "FandomA",
        "tags": "GoodTrope, AnotherTag",
        "is_in_library": True,
        "is_in_history": True,
        "visit_count": 5,  # High engagement
        "status": "Kudosed",  # High status multiplier
        "user_rating": 5,  # High author multiplier
    }
    # This fic establishes a weaker preference for 'OkayAuthor' and 'OkayTrope'.
    fic_history_weak = {
        "author": "OkayAuthor",
        "fandoms": "FandomA",
        "tags": "OkayTrope",
        "is_in_library": True,
        "status": "Read",
    }
    engine.add_fic(fic_history_strong)
    engine.add_fic(fic_history_weak)

    # Sanity check: ensure the cache is populated.
    assert engine.author_scores["SuperAuthor"]["tws"] > 0
    assert engine.tag_scores["GoodTrope"]["tws"] > 0
    assert engine.fandom_scores["FandomA"]["tws"] > 0

    # 2. DEFINE CANDIDATES: A list of fics from the user's "To Read" list.
    # This one should score highest as it matches all the strong preferences.
    candidate_high = {
        "url": "h1",
        "title": "Perfect Match",
        "author": "SuperAuthor",
        "fandoms": "FandomA",
        "tags": "GoodTrope",
    }
    # This one should score lower, matching only weaker preferences.
    candidate_low = {
        "url": "l1",
        "title": "Weak Match",
        "author": "OkayAuthor",
        "fandoms": "FandomA",
        "tags": "OkayTrope",
    }
    # This one has a mix of strong (author) and weak (tag) preferences.
    candidate_medium = {
        "url": "m1",
        "title": "Mixed Match",
        "author": "SuperAuthor",
        "fandoms": "FandomA",
        "tags": "OkayTrope",
    }
    # This one has no overlap and should score 0.
    candidate_zero = {
        "url": "z1",
        "title": "No Match",
        "author": "NewAuthor",
        "fandoms": "FandomB",
        "tags": "UnknownTrope",
    }

    fics_to_consider = [candidate_low, candidate_high, candidate_zero, candidate_medium]

    # 3. EXECUTE: Generate the recommendations.
    recommendations = engine.generate_recommendations(fics_to_consider)

    # 4. ASSERT: Verify the results.
    # Check that all candidates are present.
    assert len(recommendations) == 4

    # The list must be sorted by recommendation_score, descending.
    assert recommendations[0]["title"] == "Perfect Match"
    assert recommendations[1]["title"] == "Mixed Match"
    assert recommendations[2]["title"] == "Weak Match"
    assert recommendations[3]["title"] == "No Match"

    # Verify the calculated scores.
    # We expect the score to be the sum of the TWS of each entity.
    # Let's check the highest and lowest scores.
    score_high = recommendations[0]["recommendation_score"]
    score_medium = recommendations[1]["recommendation_score"]
    score_low = recommendations[2]["recommendation_score"]
    score_zero = recommendations[3]["recommendation_score"]

    assert score_high > score_medium
    assert score_medium > score_low
    assert score_low > score_zero
    assert score_zero == 0.0

    # Check that a score was added to each dictionary
    assert "recommendation_score" in recommendations[0]
    assert "recommendation_score" in recommendations[1]
    assert "recommendation_score" in recommendations[2]
    assert "recommendation_score" in recommendations[3]
