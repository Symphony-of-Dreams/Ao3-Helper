import pytest

from ao3_helper.core.ao3_manager import parse_ao3_url


@pytest.mark.parametrize(
    "url, expected_type, expected_id",
    [
        ("https://archiveofourown.org/works/12345", "work", "12345"),
        ("http://archiveofourown.org/works/12345/chapters/67890", "work", "12345"),
        ("archiveofourown.org/works/12345", "work", "12345"),
        ("https://archiveofourown.org/users/TestUser/works", "author", "TestUser"),
        ("http://archiveofourown.org/users/TestUser/series", "author", "TestUser"),
        ("https://archiveofourown.org/users/TestUser", "author", "TestUser"),
        ("https://archiveofourown.org/series/54321", "series", "54321"),
        ("http://www.archiveofourown.org/series/54321", "series", "54321"),
        ("https://archiveofourown.org/collections/MyFaves", "collection", "MyFaves"),
        (
            "https://archiveofourown.org/collections/MyFaves/works/12345",
            "collection",
            "MyFaves",
        ),
        ("https://archiveofourown.org/tags/Fluff", "unknown", None),
        ("https://www.google.com", "unknown", None),
        ("just some random string", "unknown", None),
        ("", "unknown", None),
    ],
)
def test_parse_ao3_url(url, expected_type, expected_id):
    """
    Verifica che parse_ao3_url identifichi correttamente tipo e ID da vari formati di URL.
    """
    url_type, identifier = parse_ao3_url(url)
    assert url_type == expected_type
    assert identifier == expected_id
