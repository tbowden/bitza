"""
Asset Management CLI

Usage:
    python -m app.cli create-superuser
"""
import asyncio

import typer

app = typer.Typer(
    name="bitza",
    help="Bitza asset management API — administrative CLI",
    add_completion=False,
)


@app.callback()
def callback() -> None:
    """
    Bitza asset management API — administrative CLI.

    This empty callback is required to keep Typer in multi-command mode.
    Without it, Typer collapses a single-command app into a top-level
    command and stops expecting a subcommand name on the command line —
    i.e. `python -m app.cli create-superuser` would fail with
    "unexpected extra argument". Keeping this callback (even as a no-op)
    means the subcommand name stays required, and any future commands
    added here will work the same way.
    """
    pass


@app.command("create-superuser")
def create_superuser() -> None:
    """
    Create the single application superuser.

    If a superuser already exists, you will be asked whether to delete it
    and create a replacement. This is a destructive, two-step confirmation
    action — the existing superuser's refresh tokens are also removed
    (via cascade delete), which immediately revokes any active sessions.
    """
    from app.core.exceptions import ConflictError
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

            # --- Check for an existing superuser before prompting for anything ---
            existing = service.get_superuser()
            if existing:
                typer.echo(
                    f"A superuser already exists:\n"
                    f"    Email:        {existing.email}\n"
                    f"    Username:     {existing.username}\n"
                    f"    Display name: {existing.display_name}\n"
                )
                replace = typer.confirm(
                    "Delete this superuser and create a new one?",
                    default=False,
                )
                if not replace:
                    typer.echo("No changes made.")
                    return

                confirm_again = typer.confirm(
                    f"This is permanent and will revoke '{existing.username}'s "
                    f"active sessions. Are you sure?",
                    default=False,
                )
                if not confirm_again:
                    typer.echo("No changes made.")
                    return

                service.delete_superuser()
                typer.echo(f"✅  Deleted existing superuser '{existing.username}'.\n")

            # --- Collect details for the new superuser ---
            email = typer.prompt("Email")
            username = typer.prompt("Username")
            display_name = typer.prompt("Display name")
            password = typer.prompt(
                "Password (min 12 chars, must pass strength check)",
                hide_input=True,
                confirmation_prompt=True,
            )

            try:
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
