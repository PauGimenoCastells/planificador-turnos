import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def user(db):
    return User.objects.create_user(username="manolo", password="1234")


@pytest.mark.django_db
def test_r1_unauthenticated_home_shows_login_button():
    """R1: Cuando un usuario no autenticado accede a '/', visualiza un botón 'Iniciar sesión' hacia '/login/'."""
    client = Client()
    response = client.get("/")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Iniciar sesión" in content
    assert "/login/" in content


@pytest.mark.django_db
def test_r2_login_page_renders_form_and_accent_color():
    """R2: Cuando un usuario accede a '/login/', visualiza un formulario con campos y color de acento #00CCFF."""
    client = Client()
    response = client.get("/login/")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "<form" in content
    assert 'name="username"' in content
    assert 'name="password"' in content
    assert "#00CCFF" in content


@pytest.mark.django_db
def test_r3_login_valid_credentials_redirects_and_shows_username(user):
    """R3 (Portante): Introducir credenciales válidas inicia sesión, redirige a '/' con 'Hola, manolo' y botón 'Cerrar sesión'."""
    client = Client()
    response = client.post("/login/", {"username": "manolo", "password": "1234"}, follow=True)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Hola, manolo" in content
    assert "Cerrar sesión" in content
    assert "/logout/" in content


@pytest.mark.django_db
def test_r4_logout_ends_session_and_redirects_home(user):
    """R4: Cerrar sesión en '/logout/' finaliza la sesión y redirige a '/' mostrando el estado no autenticado."""
    client = Client()
    client.login(username="manolo", password="1234")
    # Comprobar que inicialmente está autenticado
    res_home = client.get("/")
    assert "Hola, manolo" in res_home.content.decode("utf-8")

    # Cerrar sesión vía GET
    response = client.get("/logout/", follow=True)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Hola, manolo" not in content
    assert "Iniciar sesión" in content


@pytest.mark.django_db
def test_r4_logout_post_also_supported(user):
    """R4: Cerrar sesión en '/logout/' vía POST también es soportado."""
    client = Client()
    client.login(username="manolo", password="1234")
    response = client.post("/logout/", follow=True)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Hola, manolo" not in content
    assert "Iniciar sesión" in content


@pytest.mark.django_db
def test_r5_login_invalid_credentials_shows_error(user):
    """R5: Credenciales incorrectas permanecen en '/login/' con mensaje de advertencia visible."""
    client = Client()
    response = client.post("/login/", {"username": "manolo", "password": "wrong_password"})
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert (
        "incorrectos" in content.lower()
        or "error" in content.lower()
        or "inválid" in content.lower()
    )
