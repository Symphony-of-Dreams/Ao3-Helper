import pytest
from unittest.mock import patch, MagicMock
from src.ao3_helper.core.query_builder import _normalize_fandom_name, build_discovery_query

def test_normalize_fandom_name():
    """Test that _normalize_fandom_name correctly cleans up fandom names."""
    assert _normalize_fandom_name("Fandom Name (Manga)") == "fandom name"
    assert _normalize_fandom_name("  Another Fandom (TV)  ") == "another fandom"
    assert _normalize_fandom_name("Fandom without parens") == "fandom without parens"

@pytest.fixture
def sample_profile_and_params():
    profile = {
        "fandoms": [{"name": "Fandom 1 (Manga)", "tws": 100}, {"name": "Fandom 2", "tws": 50}],
        "relationships": [{"name": "Rel 1", "tws": 20}],
        "characters": [{"name": "Char 1", "tws": 30}],
        "tags": [{"name": "Tag 1", "tws": 10}, {"name": "Tag 2", "tws": 5}, {"name": "Tag 3", "tws": 2}, {"name": "Tag 4", "tws": 1}, {"name": "Tag 5", "tws": 1}, {"name": "Tag 6", "tws": 1}],
    }
    search_params = {"strategy": "safe_bet", "word_count": ">1000", "is_complete": True, "sort_by": "kudos_count"}
    return profile, search_params

@patch("src.ao3_helper.core.query_builder.AO3.Search")
@patch("random.choices")
@patch("random.randint")
def test_build_discovery_query_safe_bet(mock_randint, mock_choices, mock_search, sample_profile_and_params):
    mock_choices.side_effect = [["Fandom 1 (Manga)"], ["Char 1"], ["Tag 1", "Tag 2", "Tag 3", "Tag 4", "Tag 5"]]
    mock_randint.return_value = 2
    profile, search_params = sample_profile_and_params
    search_query = build_discovery_query(profile, search_params)
    mock_search.assert_called_with(fandoms='"Fandom 1 (Manga)"', word_count=">1000", sort_column="kudos_count")
    assert search_query.complete is True
    assert search_query.any_field == '"Char 1" "Tag 1" "Tag 2" ("Tag 3" OR "Tag 4" OR "Tag 5")'

@patch("src.ao3_helper.core.query_builder.AO3.Search")
@patch("random.choices")
@patch("random.randint")
def test_build_discovery_query_hidden_gem(mock_randint, mock_choices, mock_search, sample_profile_and_params):
    mock_choices.side_effect = [["Fandom 2"], ["Rel 1"], ["Tag 1", "Tag 2"]]
    mock_randint.return_value = 1
    profile, search_params = sample_profile_and_params
    search_params["strategy"] = "hidden_gem"
    search_query = build_discovery_query(profile, search_params)
    mock_search.assert_called_with(fandoms='"Fandom 2"', word_count=">1000", sort_column="kudos_count")
    assert search_query.any_field == '("Rel 1" "Tag 1" ("Tag 2")) kudos:<300'

@patch("src.ao3_helper.core.query_builder.AO3.Search")
@patch("random.choices")
@patch("random.sample")
def test_build_discovery_query_wildcard(mock_sample, mock_choices, mock_search, sample_profile_and_params):
    mock_choices.side_effect = [["Fandom 1 (Manga)"], ["Char 1"], ["Tag 1", "Tag 2", "Tag 3", "Tag 4", "Tag 5"]]
    mock_sample.return_value = ["Char 1", "Rel 1"]
    profile, search_params = sample_profile_and_params
    search_params["strategy"] = "wildcard"
    search_query = build_discovery_query(profile, search_params)
    mock_search.assert_called_with(fandoms='"Fandom 1 (Manga)"', word_count=">1000", sort_column="kudos_count")
    assert search_query.any_field == '"Char 1" "Rel 1"'

def test_build_discovery_query_no_fandoms(sample_profile_and_params):
    profile, search_params = sample_profile_and_params
    profile["fandoms"] = []
    with pytest.raises(ValueError, match="Cannot build query: user profile has no fandoms."):
        build_discovery_query(profile, search_params)

def test_build_discovery_query_no_anchors(sample_profile_and_params):
    profile, search_params = sample_profile_and_params
    profile["relationships"] = []
    profile["characters"] = []
    with pytest.raises(ValueError, match="Not enough profile data \\(anchors/context\\) to build a hybrid query."):
        build_discovery_query(profile, search_params)
