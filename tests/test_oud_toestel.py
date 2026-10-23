"""Een oud toestel registreren dat nooit in het systeem stond.

Tijdens de overgang naar nieuwe toestellen krijgt iemand eerst een nieuw toestel
en levert het oude pas later in. Dat oude toestel wordt op dat moment meteen als
ingeleverd vastgelegd: het is dus nooit actief geweest en botst daardoor niet met
het nieuwe toestel dat al aan dezelfde persoon hangt.
"""

from datetime import date, timedelta

from app.models.laptop_issue import LaptopIssue
from app.models.student import Student


def _add_student(session, stamnummer: str, naam: str = "Doe", voornaam: str = "John") -> Student:
    student = Student(stamnummer=stamnummer, naam=naam, voornaam=voornaam, klas="3A")
    session.add(student)
    session.commit()
    return student


def _register_old(client, stamnummer: str, serial: str, **extra):
    payload = {"serial_number": serial, "stamnummer": stamnummer}
    payload.setdefault("unlinked_at", date.today().isoformat())
    payload.update(extra)
    return client.post("/api/laptops", json=payload)


# ── Kernscenario ──────────────────────────────────────────────────────────────

def test_oud_toestel_naast_het_actieve_nieuwe_toestel(client, db_session):
    """Het oude toestel mag erbij, ook al heeft de persoon al een actief toestel."""
    _add_student(db_session, "S900")
    nieuw = client.post(
        "/api/laptops/link",
        json={"stamnummer": "S900", "serial_number": "NIEUW-900"},
    )
    assert nieuw.status_code == 200

    resp = _register_old(client, "S900", "OUD-900")

    assert resp.status_code == 200
    assert resp.json()["unlinked_at"] is not None

    laptops = {lap["serial_number"]: lap for lap in client.get("/api/laptops").json()}
    assert laptops["NIEUW-900"]["is_active"] is True
    assert laptops["OUD-900"]["is_active"] is False


def test_koppeldatum_mag_onbekend_blijven(client, db_session):
    _add_student(db_session, "S901")

    resp = _register_old(client, "S901", "OUD-901")

    assert resp.status_code == 200
    body = resp.json()
    assert body["linked_at"] is None
    assert body["unlinked_at"] is not None


def test_koppeldatum_wordt_bewaard_als_die_wel_bekend_is(client, db_session):
    _add_student(db_session, "S902")
    toen = date.today() - timedelta(days=400)

    resp = _register_old(client, "S902", "OUD-902", linked_at=toen.isoformat())

    assert resp.status_code == 200
    assert resp.json()["linked_at"].startswith(toen.isoformat())


# ── Accessoires ───────────────────────────────────────────────────────────────

def test_ontbrekende_oplader_maakt_een_issue_aan(client, db_session):
    _add_student(db_session, "S903")

    resp = _register_old(client, "S903", "OUD-903", oplader_ingeleverd=False)

    assert resp.status_code == 200
    assert resp.json()["oplader_ingeleverd"] is False
    issue = db_session.query(LaptopIssue).filter_by(serial_number="OUD-903").one()
    assert "oplader" in issue.description
    assert "hoes" not in issue.description


def test_volledig_ingeleverd_maakt_geen_issue_aan(client, db_session):
    _add_student(db_session, "S904")

    _register_old(client, "S904", "OUD-904")

    assert db_session.query(LaptopIssue).filter_by(serial_number="OUD-904").count() == 0


# ── Validatie ─────────────────────────────────────────────────────────────────

def test_inleverdatum_in_de_toekomst_wordt_geweigerd(client, db_session):
    _add_student(db_session, "S905")
    morgen = date.today() + timedelta(days=1)

    resp = _register_old(client, "S905", "OUD-905", unlinked_at=morgen.isoformat())

    assert resp.status_code == 422


def test_inleverdatum_voor_koppeldatum_wordt_geweigerd(client, db_session):
    _add_student(db_session, "S906")

    resp = _register_old(
        client,
        "S906",
        "OUD-906",
        linked_at=date.today().isoformat(),
        unlinked_at=(date.today() - timedelta(days=5)).isoformat(),
    )

    assert resp.status_code == 422


def test_reservetoestel_kan_niet_als_ingeleverd_worden_aangemaakt(client):
    resp = client.post(
        "/api/laptops",
        json={
            "serial_number": "OUD-907",
            "is_reserve": True,
            "alias": "Reserve-oud",
            "unlinked_at": date.today().isoformat(),
        },
    )

    assert resp.status_code == 422


# ── Zichtbaarheid in de UI en de geschiedenis ────────────────────────────────

def test_oud_toestel_staat_als_inactief_in_het_beheeroverzicht(client, db_session):
    _add_student(db_session, "S908", naam="Peeters", voornaam="An")
    _register_old(client, "S908", "OUD-908", hoes_ingeleverd=False)

    html = client.get("/ui/laptops/manage", params={"c_serial": "OUD-908"}).text

    assert "OUD-908" in html
    assert "Inactief" in html
    assert "hoes" in html


def test_serienummer_blijft_opnieuw_toekenbaar_na_registratie(client, db_session):
    """Het oude toestel is ingeleverd, dus het serienummer is weer vrij."""
    _add_student(db_session, "S909")
    _add_student(db_session, "S910")
    _register_old(client, "S909", "OUD-909")

    resp = client.post(
        "/api/laptops/link",
        json={"stamnummer": "S910", "serial_number": "OUD-909"},
    )

    assert resp.status_code == 200


def test_oud_toestel_verschijnt_in_de_tijdlijn_van_het_serienummer(client, db_session):
    """Kernvraag: de geschiedenis per toestel moet het oude gebruik tonen."""
    from app.services.laptop_service import get_assignment_history

    _add_student(db_session, "S911", naam="Jansen", voornaam="Lotte")
    _register_old(client, "S911", "OUD-911")

    history = get_assignment_history(db_session, "OUD-911")

    assert len(history) == 1
    assert history[0]["stamnummer"] == "S911"
    assert history[0]["naam"] == "Jansen"
    assert history[0]["is_active"] is False


def test_oud_toestel_werkt_ook_voor_een_leerkracht(client, db_session):
    """Leerkrachten staan in dezelfde tabel; de sleutel is hun gebruikersnaam."""
    client.post(
        "/api/students/import?leerkracht=true",
        files={"file": ("l.csv", b"Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n", "text/csv")},
    )

    resp = _register_old(client, "an.peeters", "OUD-LK-1")

    assert resp.status_code == 200, resp.text
    assert resp.json()["stamnummer"] == "an.peeters"
    assert resp.json()["unlinked_at"] is not None
