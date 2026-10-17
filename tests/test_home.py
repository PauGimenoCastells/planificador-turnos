import pytest
from django.test import Client


@pytest.mark.django_db
def test_home_page_returns_200_and_renders_tailwind():
    """R1: La ruta raíz responde con HTTP 200 y una pantalla de bienvenida estilizada con Tailwind CSS."""
    client = Client()
    response = client.get("/")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Planificador de Turnos" in content
    assert "tailwindcss" in content.lower() or "bg-" in content or "text-" in content
