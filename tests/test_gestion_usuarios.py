from io import StringIO

import pytest
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client


@pytest.fixture
def usuarios(db):
    user_pau, _ = User.objects.get_or_create(
        username="pau",
        defaults={"is_superuser": True, "is_staff": True},
    )
    user_pau.set_password("paupass123")
    user_pau.save()

    user_pol, _ = User.objects.get_or_create(
        username="pol",
        defaults={"is_superuser": False, "is_staff": False},
    )
    user_pol.set_password("polpass123")
    user_pol.save()

    return {
        "pau": user_pau,
        "pol": user_pol,
    }


@pytest.mark.django_db
def test_r1_pau_superusuario_accede_con_status_200(usuarios):
    """R1: Pau (superusuario) accede a /turnos/usuarios/ con status 200."""
    client = Client()
    client.force_login(usuarios["pau"])
    resp = client.get("/turnos/usuarios/")
    assert resp.status_code == 200
    assert "turnos/usuarios.html" in [t.name for t in resp.templates if t.name]


@pytest.mark.django_db
def test_r1_pol_solicitante_recibe_403(usuarios):
    """R1: pol (solicitante) recibe 403 al acceder a /turnos/usuarios/."""
    client = Client()
    client.force_login(usuarios["pol"])
    resp = client.get("/turnos/usuarios/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_r1_anonimo_redirige_a_login(db):
    """R1: anónimo redirige a login (302)."""
    client = Client()
    resp = client.get("/turnos/usuarios/")
    assert resp.status_code == 302
    assert "/login/" in resp.headers.get("Location", "")


@pytest.mark.django_db
def test_r2_pau_cambia_password_de_pol(usuarios):
    """R2: Pau puede cambiar la contraseña de pol via POST con accion=cambiar_password."""
    client = Client()
    client.force_login(usuarios["pau"])
    resp = client.post(
        "/turnos/usuarios/",
        {"accion": "cambiar_password", "user_id": usuarios["pol"].id, "nueva_password": "nueva_clave_secreta_123"},
    )
    assert resp.status_code == 200
    usuarios["pol"].refresh_from_db()
    assert check_password("nueva_clave_secreta_123", usuarios["pol"].password)
    assert not check_password("polpass123", usuarios["pol"].password)


@pytest.mark.django_db
def test_r3_pau_crea_nuevo_usuario_solicitante(usuarios):
    """R3: Pau puede crear un nuevo usuario solicitante via POST con accion=crear_usuario."""
    client = Client()
    client.force_login(usuarios["pau"])
    resp = client.post(
        "/turnos/usuarios/",
        {"accion": "crear_usuario", "username": "companero_nuevo", "password": "companero_pass_456"},
    )
    assert resp.status_code == 200
    nuevo = User.objects.get(username="companero_nuevo")
    assert nuevo.is_staff is False
    assert nuevo.is_superuser is False
    assert check_password("companero_pass_456", nuevo.password)


@pytest.mark.django_db
def test_r5_crear_usuario_duplicado_muestra_error(usuarios):
    """R5: crear usuario duplicado muestra error descriptivo."""
    client = Client()
    client.force_login(usuarios["pau"])
    resp = client.post(
        "/turnos/usuarios/",
        {"accion": "crear_usuario", "username": "pol", "password": "alguna_pass_123"},
    )
    assert resp.status_code == 200
    contenido = resp.content.decode("utf-8")
    assert "ya existe" in contenido.lower() or "duplicado" in contenido.lower() or "error" in contenido.lower()


@pytest.mark.django_db
def test_r5_crear_usuario_password_vacia_muestra_error(usuarios):
    """R5: crear usuario con password vacía muestra error descriptivo."""
    client = Client()
    client.force_login(usuarios["pau"])
    resp = client.post(
        "/turnos/usuarios/",
        {"accion": "crear_usuario", "username": "usuario_sin_pass", "password": ""},
    )
    assert resp.status_code == 200
    assert not User.objects.filter(username="usuario_sin_pass").exists()
    contenido = resp.content.decode("utf-8")
    assert "contraseña" in contenido.lower() or "password" in contenido.lower() or "error" in contenido.lower()


@pytest.mark.django_db
def test_r1_pol_no_puede_hacer_post_cambiar_password_ni_crear_usuario(usuarios):
    """R1: pol no puede hacer POST de cambiar_password ni crear_usuario (403)."""
    client = Client()
    client.force_login(usuarios["pol"])

    resp_cambiar = client.post(
        "/turnos/usuarios/",
        {"accion": "cambiar_password", "user_id": usuarios["pol"].id, "nueva_password": "hack"},
    )
    assert resp_cambiar.status_code == 403

    resp_crear = client.post(
        "/turnos/usuarios/",
        {"accion": "crear_usuario", "username": "hacker", "password": "hackpassword"},
    )
    assert resp_crear.status_code == 403
    assert not User.objects.filter(username="hacker").exists()


@pytest.mark.django_db
def test_r4_comando_poblar_usuarios_crea_cuentas_deterministas():
    """R4: comando poblar_usuarios crea pau, pol, manolo, paco, random."""
    User.objects.all().delete()
    out = StringIO()
    call_command("poblar_usuarios", stdout=out)
    output = out.getvalue()
    assert "completada con éxito" in output.lower()

    pau = User.objects.get(username="pau")
    assert pau.is_superuser is True
    assert pau.is_staff is True

    for u_name in ("pol", "manolo", "paco", "random"):
        u = User.objects.get(username=u_name)
        assert u.is_superuser is False
        assert u.is_staff is False
        assert u.has_usable_password()

    # Re-ejecutar sin reset mantiene usuarios
    out2 = StringIO()
    call_command("poblar_usuarios", stdout=out2)
    assert "ya existente" in out2.getvalue().lower()

    # Re-ejecutar con --reset-passwords regenera contraseñas
    out3 = StringIO()
    call_command("poblar_usuarios", "--reset-passwords", stdout=out3)
    assert "actualizada clave" in out3.getvalue().lower()

