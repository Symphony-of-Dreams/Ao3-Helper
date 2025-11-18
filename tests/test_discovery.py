import pytest

from ao3_helper.core.analysis_engine import AnalysisEngine
from ao3_helper.core.query_builder import build_discovery_query
from ao3_helper.workers.workers import AuthorRecsWorker


@pytest.fixture
def mock_user_profile():
    """Un profilo utente fittizio ma realistico per i test."""
    return {
        "authors": [
            {"name": "TopAuthor1", "tws": 100},
            {"name": "TopAuthor2", "tws": 80},
            {"name": "TopAuthor3", "tws": 60},
            {"name": "TopAuthor4", "tws": 40},
            {"name": "TopAuthor5", "tws": 20},
        ],
        "fandoms": [
            {"name": "Fandom A (Movie)", "tws": 200},
            {"name": "Fandom B", "tws": 150},
            {"name": "Fandom A (Book)", "tws": 100},
        ],
        "relationships": [
            {"name": "A/B", "tws": 90},
            {"name": "C/D", "tws": 70},
        ],
        "tags": [
            {"name": "Fluff", "tws": 120},
            {"name": "Angst", "tws": 110},
            {"name": "Slow Burn", "tws": 100},
            {"name": "Hurt/Comfort", "tws": 50},
            {"name": "Coffee Shops", "tws": 40},
            {"name": "Canon Divergence", "tws": 30},
        ],
        "characters": [
            {"name": "Character A", "tws": 85},
            {"name": "Character C", "tws": 75},
        ],
    }


def test_build_hybrid_query_logic(mocker, mock_user_profile):
    """
    Verifica che build_discovery_query costruisca una query ibrida corretta,
    controllando la selezione randomica.
    """

    mocker.patch(
        "ao3_helper.core.query_builder.random.choices",
        side_effect=[
            ["Fandom A (Movie)"],
            ["A/B"],
            ["Fluff", "Angst", "Slow Burn", "Hurt/Comfort", "Coffee Shops"],
        ],
    )
    mocker.patch("ao3_helper.core.query_builder.random.randint", return_value=2)

    search_params = {"strategy": "safe_bet"}

    search_query = build_discovery_query(mock_user_profile, search_params)

    assert search_query.fandoms == '"Fandom A (Movie)"'

    expected_query = '"A/B" "Fluff" "Angst" ("Slow Burn" OR "Hurt/Comfort" OR "Coffee Shops")'
    assert search_query.any_field == expected_query


def test_author_recs_worker_logic(mocker, mock_user_profile):
    """
    Verifica la logica completa dell'AuthorRecsWorker: selezione autori,
    campionamento bookmark, fetch, scoring e selezione finale.
    """

    def mock_get_bookmarks(author_name, num_to_sample):
        if author_name == "TopAuthor1":
            return [101, 102, 103]
        if author_name == "TopAuthor2":
            return [201, 202]
        if author_name == "TopAuthor3":
            return [301]
        return []

    mocker.patch("ao3_helper.workers.workers.ao3_client.get_random_bookmarks_from_author", side_effect=mock_get_bookmarks)

    mock_fics_data = {
        "https://archiveofourown.org/works/101": {
            "url": "https://archiveofourown.org/works/101",
            "title": "Fic A1",
            "tws_bait": 1000,
        },
        "https://archiveofourown.org/works/102": {
            "url": "https://archiveofourown.org/works/102",
            "title": "Fic A2",
            "tws_bait": 100,
        },
        "https://archiveofourown.org/works/201": {
            "url": "https://archiveofourown.org/works/201",
            "title": "Fic B1",
            "tws_bait": 50,
        },
        "https://archiveofourown.org/works/202": {
            "url": "https://archiveofourown.org/works/202",
            "title": "Fic B2",
            "tws_bait": 500,
        },
    }

    def mock_fetch_data(url):
        fic = mock_fics_data.get(url, {})

        fic["tags"] = f"TWS_BAIT_{fic.get('tws_bait', 0)}"
        return fic

    mocker.patch("ao3_helper.workers.workers.ao3_client.fetch_fic_data", side_effect=mock_fetch_data)

    mocker.patch("ao3_helper.workers.workers.get_existing_urls", return_value={"https://archiveofourown.org/works/301"})

    engine = AnalysisEngine()

    for author_data in mock_user_profile["authors"]:
        engine.author_scores[author_data["name"]]["tws"] = author_data["tws"]
        engine.author_scores[author_data["name"]]["fic_count"] = 1

    engine.tag_scores["TWS_BAIT_1000"]["tws"] = 1000
    engine.tag_scores["TWS_BAIT_500"]["tws"] = 500
    engine.tag_scores["TWS_BAIT_100"]["tws"] = 100
    engine.tag_scores["TWS_BAIT_50"]["tws"] = 50

    mocker.patch(
        "ao3_helper.workers.workers.random.choices",
        side_effect=[
            ["TopAuthor1"],
            ["TopAuthor2"],
            ["TopAuthor3"],
        ],
    )

    worker = AuthorRecsWorker(engine)

    results = []
    worker.finished.connect(results.append)

    worker.run()

    assert len(results) > 0, "Il worker non ha emesso alcun risultato"
    final_recs = results[0]

    assert len(final_recs) == 2, "Il numero di raccomandazioni finali non è corretto"

    titles_and_recommenders = {r["title"]: r["recommended_by"] for r in final_recs}

    assert "Fic A1" in titles_and_recommenders
    assert titles_and_recommenders["Fic A1"] == "TopAuthor1"

    assert "Fic B2" in titles_and_recommenders
    assert titles_and_recommenders["Fic B2"] == "TopAuthor2"

    assert "Fic A2" not in titles_and_recommenders
    assert "Fic B1" not in titles_and_recommenders