"""Tests for the authentication gate."""


def test_root_redirects_to_login_when_anonymous(anon_client):
    resp = anon_client.get("/", follow_redirects=False, headers={"accept": "text/html"})
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/login")


def test_api_returns_401_when_anonymous(anon_client):
    resp = anon_client.get("/api/students")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Not authenticated"}


def test_htmx_request_returns_redirect_header(anon_client):
    resp = anon_client.get("/ui/students/list", headers={"HX-Request": "true"})
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect") == "/login"


def test_login_page_is_public(anon_client):
    resp = anon_client.get("/login")
    assert resp.status_code == 200
    assert "Inloggen" in resp.text


def test_static_files_are_public(anon_client):
    resp = anon_client.get("/static/css/style.css")
    assert resp.status_code in (200, 304)


def test_bad_password_returns_401(anon_client):
    resp = anon_client.post(
        "/login",
        data={"username": "test", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 401


def test_good_login_sets_session_and_redirects(anon_client):
    resp = anon_client.post(
        "/login",
        data={"username": "test", "password": "test"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    # Subsequent request should now be authenticated.
    resp2 = anon_client.get("/api/students")
    assert resp2.status_code == 200


def test_login_honours_safe_next(anon_client):
    resp = anon_client.post(
        "/login",
        data={"username": "test", "password": "test", "next": "/photos"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/photos"


def test_login_rejects_external_next(anon_client):
    resp = anon_client.post(
        "/login",
        data={"username": "test", "password": "test", "next": "//evil.example/x"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_logout_clears_session(client):
    # `client` is auto-logged-in. After logout, follow-up request should 401/303.
    resp = client.post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"

    resp2 = client.get("/api/students")
    assert resp2.status_code == 401
