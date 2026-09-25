"""Tests for the /health endpoint and log masking."""

from app.logging_config import mask_url
from app.services.student_import import import_students_from_stream
import io


def test_mask_url_hides_password():
    masked = mask_url("mysql+pymysql://root:sup3rgeheim@db:3306/laptops")

    assert "sup3rgeheim" not in masked
    assert masked == "mysql+pymysql://root:***@db:3306/laptops"


def test_mask_url_handles_empty_password():
    assert mask_url("mysql+pymysql://root:@db:3306/laptops") == (
        "mysql+pymysql://root:***@db:3306/laptops"
    )


def test_health_is_public(client):
    """Must work without a session so it can be curl'ed on the server."""
    client.post("/logout")

    resp = client.get("/health")

    assert resp.status_code in (200, 503)


def test_health_reports_version_and_counts(client, db_session):
    import_students_from_stream(
        db_session, io.StringIO("Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n"),
        is_leerkracht=True,
    )

    body = client.get("/health").json()

    assert body["version"]
    assert body["database"]["ok"] is True
    assert body["counts"]["leerkrachten"] == 1


def test_health_never_leaks_the_password(client):
    body = client.get("/health").json()

    assert "***" in body["database"]["url"]
    assert "@" in body["database"]["url"]
