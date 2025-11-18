from datetime import datetime

from peewee import (
    AutoField,
    BooleanField,
    CharField,
    CompositeKey,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    Model,
    Proxy,
    TextField,
)

from ao3_helper import constants as const

db = Proxy()


class BaseModel(Model):
    class Meta:
        database = db


class Author(BaseModel):
    name = CharField(unique=True)


class Fandom(BaseModel):
    name = CharField(unique=True)


class Character(BaseModel):
    name = CharField(unique=True)


class Relationship(BaseModel):
    name = CharField(unique=True)


class ContentTag(BaseModel):
    """Tag originali di AO3 (Freeforms)"""

    name = CharField(unique=True)


class Category(BaseModel):
    name = CharField(unique=True)


class Fic(BaseModel):
    url = CharField(primary_key=True, max_length=255)
    title = CharField()

    author = CharField(null=True)
    fandoms = TextField(null=True)
    tags = TextField(null=True)
    category = CharField(null=True)
    relationships = TextField(null=True)
    characters = TextField(null=True)

    rating = CharField(null=True)
    word_count = IntegerField(null=True)
    summary = TextField(null=True)
    status = CharField(default=const.STATUS_TO_READ)
    date_added = DateTimeField(default=datetime.now)
    user_notes = TextField(null=True)
    user_rating = IntegerField(null=True, default=0)

    is_complete = BooleanField(default=False)
    status_verified = BooleanField(default=False)

    series_name = CharField(null=True)
    series_url = CharField(null=True)
    series_part = IntegerField(null=True)

    chapters = CharField(null=True)
    date_published = CharField(null=True)
    date_updated = CharField(null=True)
    source = CharField(default="manual")
    language = CharField(null=True)

    hits = IntegerField(null=True)
    kudos = IntegerField(null=True)
    bookmarks = IntegerField(null=True)
    comments = IntegerField(null=True)

    is_in_library = BooleanField(default=False)
    is_in_history = BooleanField(default=False)
    last_visit_date = CharField(null=True)
    visit_count = IntegerField(null=True)

    is_in_reading_queue = BooleanField(default=False)
    queue_order = IntegerField(null=True)

    class Meta:
        table_name = "fics"


class FicAuthor(BaseModel):
    fic = ForeignKeyField(Fic, backref="authors_join", on_delete="CASCADE")
    author = ForeignKeyField(Author, backref="fics", on_delete="CASCADE")

    class Meta:
        primary_key = CompositeKey("fic", "author")


class FicFandom(BaseModel):
    fic = ForeignKeyField(Fic, backref="fandoms_join", on_delete="CASCADE")
    fandom = ForeignKeyField(Fandom, backref="fics", on_delete="CASCADE")

    class Meta:
        primary_key = CompositeKey("fic", "fandom")


class FicCharacter(BaseModel):
    fic = ForeignKeyField(Fic, backref="characters_join", on_delete="CASCADE")
    character = ForeignKeyField(Character, backref="fics", on_delete="CASCADE")

    class Meta:
        primary_key = CompositeKey("fic", "character")


class FicRelationship(BaseModel):
    fic = ForeignKeyField(Fic, backref="relationships_join", on_delete="CASCADE")
    relationship = ForeignKeyField(Relationship, backref="fics", on_delete="CASCADE")

    class Meta:
        primary_key = CompositeKey("fic", "relationship")


class FicContentTag(BaseModel):
    fic = ForeignKeyField(Fic, backref="tags_join", on_delete="CASCADE")
    tag = ForeignKeyField(ContentTag, backref="fics", on_delete="CASCADE")

    class Meta:
        primary_key = CompositeKey("fic", "tag")


class FicCategory(BaseModel):
    fic = ForeignKeyField(Fic, backref="categories_join", on_delete="CASCADE")
    category = ForeignKeyField(Category, backref="fics", on_delete="CASCADE")

    class Meta:
        primary_key = CompositeKey("fic", "category")


class UserTag(BaseModel):
    tag_id = AutoField()
    name = CharField(unique=True)

    class Meta:
        table_name = "user_tags"


class FicTag(BaseModel):
    fic = ForeignKeyField(
        Fic,
        backref="tags_junction",
        column_name="fic_url",
        on_delete="CASCADE",
    )
    tag = ForeignKeyField(
        UserTag,
        backref="fics_junction",
        column_name="tag_id",
        on_delete="CASCADE",
    )

    class Meta:
        table_name = "fic_tags"
        primary_key = CompositeKey("fic", "tag")


class Notification(BaseModel):
    id = AutoField()
    message = TextField()
    timestamp = CharField()
    is_read = BooleanField(default=False)
    related_url = CharField(null=True)

    class Meta:
        table_name = "notifications"


class Achievement(BaseModel):
    id = CharField(primary_key=True)
    unlocked_date = CharField()

    class Meta:
        table_name = "achievements"


class SavedFilter(BaseModel):
    id = AutoField()
    name = CharField(unique=True)
    filter_data = TextField()

    class Meta:
        table_name = "saved_filters"
