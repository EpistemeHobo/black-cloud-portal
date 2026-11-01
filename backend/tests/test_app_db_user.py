import pytest
from sqlalchemy import create_engine, func, select

from app.app_db_user import copy_rows
from app.db import Base, engine
from app.models import GuideDoc, Person, System


def test_copying_into_a_new_database_keeps_everything(tmp_path, system, owner):
    owner.post(f"/api/systems/{system['id']}/docs", json={"question": "how", "filename": "a.md", "content": "# A"})
    target = create_engine(f"sqlite:///{(tmp_path / 'new.db').as_posix()}")
    Base.metadata.create_all(target)

    counts = copy_rows(engine, target)

    for model in (Person, System, GuideDoc):
        with engine.connect() as old, target.connect() as new:
            assert new.scalar(select(func.count()).select_from(model)) == old.scalar(select(func.count()).select_from(model)) > 0
    assert counts["checklist_item"] > 0 and counts["change_log"] > 0
    with target.connect() as new:
        assert new.scalar(select(Person.email).where(Person.name == "Owner")) == "owner@example.org"

    # Never on top of existing rows: a second run stops instead of duplicating.
    with pytest.raises(SystemExit):
        copy_rows(engine, target)
