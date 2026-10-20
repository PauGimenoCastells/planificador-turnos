import secrets

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Crea o actualiza los usuarios iniciales (pau y sus 4 compañeros) con contraseñas seguras."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Fuerza la regeneración de contraseñas incluso si los usuarios ya existen.",
        )

    def handle(self, *args, **options):
        reset_passwords = options.get("reset_passwords", False)

        cuentas = [
            {"username": "pau", "is_superuser": True, "is_staff": True},
            {"username": "pol", "is_superuser": False, "is_staff": False},
            {"username": "manolo", "is_superuser": False, "is_staff": False},
            {"username": "paco", "is_superuser": False, "is_staff": False},
            {"username": "random", "is_superuser": False, "is_staff": False},
        ]

        self.stdout.write(self.style.NOTICE("Iniciando población de usuarios del sistema..."))

        for cuenta in cuentas:
            username = cuenta["username"]
            is_superuser = cuenta["is_superuser"]
            is_staff = cuenta["is_staff"]

            user = User.objects.filter(username=username).first()
            if not user:
                password = secrets.token_urlsafe(12)
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    is_superuser=is_superuser,
                    is_staff=is_staff,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f" [+] Creado usuario '{username}' (super={is_superuser}, staff={is_staff}) - Clave: {password}"
                    )
                )
            else:
                user.is_superuser = is_superuser
                user.is_staff = is_staff
                if reset_passwords:
                    password = secrets.token_urlsafe(12)
                    user.set_password(password)
                    user.save()
                    self.stdout.write(
                        self.style.WARNING(
                            f" [*] Actualizada clave de '{username}' (--reset-passwords) - Nueva clave: {password}"
                        )
                    )
                else:
                    user.save()
                    self.stdout.write(
                        self.style.NOTICE(
                            f" [=] Usuario '{username}' ya existente. Roles confirmados (clave conservada)."
                        )
                    )

        self.stdout.write(self.style.SUCCESS("Población de usuarios completada con éxito."))
