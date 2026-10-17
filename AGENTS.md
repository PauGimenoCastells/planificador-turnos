# AGENTS.md — planificador-turnos

Repo de código de «Planificador Académico y Turnos Laborales». Se orquesta desde su meta-repo (la carpeta padre; ver `repos.yaml` allí). Aquí solo vive el código de la aplicación.

## Comandos (literales, probados; los usa el método en cada cierre)

| Para… | Comando |
|---|---|
| Levantar el entorno desde cero | `python -m venv .venv && .venv\Scripts\pip install -r requirements-dev.txt` |
| Correr la suite completa | `scripts/ci/full-suite` |
| Correr los linters | `scripts/ci/lint` |
| Lanzar una instancia para que la use el usuario | `python manage.py runserver` → `http://127.0.0.1:8000/` |
| Comprobación de seguridad | `scripts/ci/security` |
| Parar / limpiar | `Ctrl+C` |

### Solo si los planos declaran `pruebas_e2e`

| Para… | Comando |
|---|---|
| Preparar identidades y datos E2E | `scripts/ci/provision-e2e` |
| Correr solo los end-to-end | `scripts/ci/e2e` |

- Documenta los aliases sintéticos estables como `pau-usuario · rol admin · turno rotativo`; nunca emails de acceso, contraseñas ni tokens.
- `scripts/ci/provision-e2e` es explícito e idempotente; solo admite local/test/E2E, verifica además una base, tenant o instancia inequívocamente de pruebas y rechaza producción antes de escribir. Ningún seed se ejecuta al arrancar, migrar o desplegar ni imprime credenciales.
- La secuencia es única: `scripts/ci/full-suite` invoca `scripts/ci/e2e`; `e2e` invoca `scripts/ci/provision-e2e` antes de ejecutar los tests y propaga cualquier rojo.

## Qué necesita esta máquina

- Python 3.13 con venv
- Navegadores Playwright (`playwright install chromium`)
- SQLite con soporte WAL

## Estructura

- `planificador_turnos/`: Proyecto Django principal (`settings.py`, `urls.py`, `views.py`, `wsgi.py`).
- `templates/`: Plantillas HTML del servidor con Tailwind CSS.
- `scripts/ci/`: Scripts de verificación local y CI (`full-suite`, `lint`, `security`, `provision-e2e`, `e2e`).
- `tests/`: Suite de tests unitarios, integración y E2E con pytest y Playwright.

## Reglas de este repo

- Los secretos van en `.env` (fuera de git) y **el `.env` está en `.dockerignore`**: un secreto horneado en una imagen es un secreto publicado.
- Las dependencias de desarrollo y test están separadas de las de producción (`requirements.txt` y `requirements-dev.txt`).
- Los tests se escriben antes que el código y no se debilitan para que pase la suite.
- Los scripts obligatorios de `scripts/ci/` —los tres base, cinco cuando se conserva el bloque E2E— preparan su entorno, usan herramientas fijadas y propagan cualquier rojo. Prohibido `|| true` o dar verde por no encontrar tests.
- La suite, el lint y la seguridad se ejecutan en local antes de fusionar; anota arriba los comandos probados para que cualquier agente pueda repetirlos.
