
from database import (
    add_fic,
    assign_tag_to_fic,
    create_user_tag,
    delete_user_tag,
    get_all_user_tags,
    get_tags_for_fic,
    remove_tag_from_fic,
)

FIC_URL = "https://archiveofourown.org/works/1"
FIC_DATA = {"url": FIC_URL, "title": "Test Fic", "author": "Test Author"}


def test_create_and_get_tags(db_connection):
    """
    Verifica che possiamo creare nuovi tag e recuperarli tutti.
    """
    tag1_id = create_user_tag("Da rileggere")
    tag2_id = create_user_tag("Preferiti del 2025")

    assert tag1_id is not None
    assert tag2_id is not None
    assert tag1_id != tag2_id

    duplicate_id = create_user_tag("Da rileggere")
    assert duplicate_id is None, "La creazione di un tag duplicato dovrebbe ritornare None."

    all_tags = get_all_user_tags()
    assert len(all_tags) == 2
    assert (tag1_id, "Da rileggere") in all_tags
    assert (tag2_id, "Preferiti del 2025") in all_tags


def test_assign_and_get_tags_for_fic(db_connection):
    """
    Verifica che possiamo assegnare tag a una fic e recuperarli.
    """
    add_fic(FIC_DATA)
    tag1_id = create_user_tag("Angst")
    tag2_id = create_user_tag("Fluff")
    create_user_tag("Irrilevante")

    assign_tag_to_fic(FIC_URL, tag1_id)
    assign_tag_to_fic(FIC_URL, tag2_id)

    fic_tags = get_tags_for_fic(FIC_URL)
    assert len(fic_tags) == 2
    assert (tag1_id, "Angst") in fic_tags
    assert (tag2_id, "Fluff") in fic_tags


def test_remove_tag_from_fic(db_connection):
    """
    Verifica che possiamo rimuovere un'associazione tra fic e tag.
    """
    add_fic(FIC_DATA)
    tag_id = create_user_tag("Da rimuovere")
    assign_tag_to_fic(FIC_URL, tag_id)
    assert len(get_tags_for_fic(FIC_URL)) == 1

    remove_tag_from_fic(FIC_URL, tag_id)
    assert len(get_tags_for_fic(FIC_URL)) == 0


def test_delete_tag_cascades_to_fic_tags(db_connection):
    """
    Verifica che la cancellazione di un tag rimuova le associazioni.
    """
    add_fic(FIC_DATA)
    fic2_url = "https://archiveofourown.org/works/2"
    add_fic({"url": fic2_url, "title": "Fic 2", "author": "Author 2"})

    tag_to_delete_id = create_user_tag("Temporaneo")
    tag_to_keep_id = create_user_tag("Permanente")

    assign_tag_to_fic(FIC_URL, tag_to_delete_id)
    assign_tag_to_fic(fic2_url, tag_to_delete_id)
    assign_tag_to_fic(FIC_URL, tag_to_keep_id)

    assert len(get_tags_for_fic(FIC_URL)) == 2
    assert len(get_tags_for_fic(fic2_url)) == 1

    delete_user_tag(tag_to_delete_id)

    assert len(get_all_user_tags()) == 1, "Il tag 'Temporaneo' dovrebbe essere stato cancellato."
    fic1_tags = get_tags_for_fic(FIC_URL)
    assert len(fic1_tags) == 1
    assert fic1_tags[0][1] == "Permanente"
    assert len(get_tags_for_fic(fic2_url)) == 0
