"""
Asset Management CLI

Usage:
    python -m app.cli create-superuser
"""
import asyncio

import typer

app = typer.Typer(
    name="assetmgmt",
    help="Asset Management API — administrative CLI",
    add_completion=False,
)


@app.command("create-superuser")
def create_superuser(
    email: str = typer.Option(..., prompt=True, help="Superuser email address"),
    username: str = typer.Option(..., prompt=True, help="Superuser username"),
    display_name: str = typer.Option(..., prompt=True, help="Superuser display name"),
    password: str = typer.Option(
        ...,
        prompt=True,
        confirmation_prompt=True,
        hide_input=True,
        help="Password (min 12 chars, must pass strength check)",
    ),
) -> None:
    """
    Create the single application superuser.

    Enforces the same password policy as the API (zxcvbn score >= 3,
    12–128 characters). Run once after the initial migration:

        python -m app.cli create-superuser
    """
    from app.core.exceptions import ConflictError, SuperuserExistsError
    from app.db.session import SessionLocal
    from app.repositories.token_repository import TokenRepository
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    async def _run() -> None:
        db = SessionLocal()
        try:
            user_repo = UserRepository(db)
            token_repo = TokenRepository(db)
            service = UserService(db=db, user_repo=user_repo, token_repo=token_repo)
            user = await service.create_superuser(
                email=email,
                username=username,
                display_name=display_name,
                password=password,
            )
            typer.echo(
                f"\n✅  Superuser created successfully.\n"
                f"    ID:           {user.id}\n"
                f"    Email:        {user.email}\n"
                f"    Username:     {user.username}\n"
                f"    Display name: {user.display_name}"
            )
        except SuperuserExistsError:
            typer.echo(
                "❌  A superuser already exists.\n"
                "    To reset the superuser, delete the existing record from the DB first.",
                err=True,
            )
            raise typer.Exit(code=1)
        except ConflictError as exc:
            typer.echo(f"❌  Conflict: {exc.detail}", err=True)
            raise typer.Exit(code=1)
        except Exception as exc:
            typer.echo(f"❌  {exc}", err=True)
            raise typer.Exit(code=1)
        finally:
            db.close()

    asyncio.run(_run())


if __name__ == "__main__":
    app()
