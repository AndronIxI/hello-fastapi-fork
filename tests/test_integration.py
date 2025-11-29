import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import app, get_db
from database import Base
import models

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_db.sqlite"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def create_todo(title="Test todo", complete=False):
    db = TestingSessionLocal()
    todo = models.Todo(title=title, complete=complete)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    db.close()
    return todo


def test_home_returns_existing_todos():
    create_todo(title="First task")
    response = client.get("/")
    assert response.status_code == 200
    assert "First task" in response.text


def test_add_todo_creates_item_and_redirects():
    response = client.post("/add", data={"title": "New task"}, follow_redirects=False)
    assert response.status_code == 303
    db = TestingSessionLocal()
    todos = db.query(models.Todo).all()
    db.close()
    assert len(todos) == 1
    assert todos[0].title == "New task"
    assert todos[0].complete is False


def test_update_todo_toggles_complete_status():
    todo = create_todo(title="Toggle task", complete=False)
    response = client.get(f"/update/{todo.id}", follow_redirects=False)
    assert response.status_code == 303
    db = TestingSessionLocal()
    updated = db.query(models.Todo).filter(models.Todo.id == todo.id).first()
    db.close()
    assert updated.complete is True
    response = client.get(f"/update/{todo.id}", follow_redirects=False)
    assert response.status_code == 303
    db = TestingSessionLocal()
    updated_again = db.query(models.Todo).filter(models.Todo.id == todo.id).first()
    db.close()
    assert updated_again.complete is False


def test_delete_todo_removes_item():
    first = create_todo(title="First")
    second = create_todo(title="Second")
    response = client.get(f"/delete/{first.id}", follow_redirects=False)
    assert response.status_code == 303
    db = TestingSessionLocal()
    titles = [t.title for t in db.query(models.Todo).all()]
    db.close()
    assert "First" not in titles
    assert "Second" in titles


def test_add_todo_without_title_returns_validation_error():
    response = client.post("/add", data={}, follow_redirects=False)
    assert response.status_code == 422
