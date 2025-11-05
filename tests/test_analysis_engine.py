import pytest

from ao3_helper.core.analysis_engine import AnalysisEngine
from ao3_helper.core.models import Fic

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
        {
            "url": "fic_B",
            "author": "Author Two",
            "fandoms": "Fandom Y",
            "tags": "Fluff",
            "is_in_library": True,
            "user_rating": 5,
        },
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

    authors = {a["name"]: a for a in results["authors"]}

    assert authors["Author One"]["tws"] == pytest.approx(8.99, 0.01)

    assert authors["Author Two"]["tws"] == pytest.approx(2.25, 0.01)

    tags = {t["name"]: t for t in results["tags"]}

    assert tags["Angst"]["tws"] == pytest.approx(14.76, 0.01)

    assert tags["Fluff"]["tws"] == pytest.approx(6.64, 0.01)


def test_incremental_updates(db_connection, analysis_test_data):
    """Tests the add, remove, and update methods of the engine."""
    engine = AnalysisEngine()

    fic_a_data = {**TEST_FIC_DEFAULTS, **analysis_test_data[0]}
    engine.add_fic(fic_a_data)

    author_one_score = engine.author_scores["Author One"]["tws"]
    assert author_one_score == pytest.approx(3.85, 0.01)

    angst_score = engine.tag_scores["Angst"]["tws"]
    assert angst_score == pytest.approx(9.62, 0.01)

    engine.remove_fic(fic_a_data)
    assert engine.author_scores["Author One"]["tws"] == pytest.approx(0.0)
    assert engine.tag_scores["Angst"]["tws"] == pytest.approx(0.0)

    engine.add_fic(fic_a_data)

    updated_fic_a_data = fic_a_data.copy()
    updated_fic_a_data["user_rating"] = 5

    engine.update_fic(old_fic_data=fic_a_data, new_fic_data=updated_fic_a_data)

    assert engine.tag_scores["Angst"]["tws"] == pytest.approx(9.62, 0.01)

    assert engine.author_scores["Author One"]["tws"] == pytest.approx(14.43, 0.01)


def test_generate_recommendations():
    """
    Tests the recommendation engine's ability to score and sort candidate fics
    based on a pre-existing user profile (reading history).
    """
    engine = AnalysisEngine()

    fic_history_strong = {
        "author": "SuperAuthor",
        "fandoms": "FandomA",
        "tags": "GoodTrope, AnotherTag",
        "is_in_library": True,
        "is_in_history": True,
        "visit_count": 5,
        "status": "Kudosed",
        "user_rating": 5,
    }

    fic_history_weak = {
        "author": "OkayAuthor",
        "fandoms": "FandomA",
        "tags": "OkayTrope",
        "is_in_library": True,
        "status": "Read",
    }
    engine.add_fic(fic_history_strong)
    engine.add_fic(fic_history_weak)

    assert engine.author_scores["SuperAuthor"]["tws"] > 0
    assert engine.tag_scores["GoodTrope"]["tws"] > 0
    assert engine.fandom_scores["FandomA"]["tws"] > 0

    candidate_high = {
        "url": "h1",
        "title": "Perfect Match",
        "author": "SuperAuthor",
        "fandoms": "FandomA",
        "tags": "GoodTrope",
    }

    candidate_low = {
        "url": "l1",
        "title": "Weak Match",
        "author": "OkayAuthor",
        "fandoms": "FandomA",
        "tags": "OkayTrope",
    }

    candidate_medium = {
        "url": "m1",
        "title": "Mixed Match",
        "author": "SuperAuthor",
        "fandoms": "FandomA",
        "tags": "OkayTrope",
    }

    candidate_zero = {
        "url": "z1",
        "title": "No Match",
        "author": "NewAuthor",
        "fandoms": "FandomB",
        "tags": "UnknownTrope",
    }

    fics_to_consider = [candidate_low, candidate_high, candidate_zero, candidate_medium]

    recommendations = engine.generate_recommendations(fics_to_consider)

    assert len(recommendations) == 4

    assert recommendations[0]["title"] == "Perfect Match"
    assert recommendations[1]["title"] == "Mixed Match"
    assert recommendations[2]["title"] == "Weak Match"
    assert recommendations[3]["title"] == "No Match"

    score_high = recommendations[0]["recommendation_score"]
    score_medium = recommendations[1]["recommendation_score"]
    score_low = recommendations[2]["recommendation_score"]
    score_zero = recommendations[3]["recommendation_score"]

    assert score_high > score_medium
    assert score_medium > score_low
    assert score_low > score_zero
    assert score_zero == 0.0

    assert "recommendation_score" in recommendations[0]
    assert "recommendation_score" in recommendations[1]
    assert "recommendation_score" in recommendations[2]
    assert "recommendation_score" in recommendations[3]
