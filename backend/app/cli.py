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


@app.command("create-root")
def create_root() -> None:
    """
    Create the single, permanent root of the bitza tree.

    There is exactly one root bitza in the whole system — everything else
    lives underneath it. Unlike create-superuser, this has no
    delete-and-replace flow: the root is meant to be created once, at
    deployment time, and never touched again. If one already exists, this
    just prints its details and exits.
    """
    from app.core.exceptions import RootBitzaExistsError
    from app.db.session import SessionLocal
    from app.models.team import Team
    from app.repositories.audit_repository import AuditRepository
    from app.repositories.bitza_image_repository import BitzaImageRepository
    from app.repositories.bitza_repository import BitzaRepository
    from app.repositories.category_repository import CategoryRepository
    from app.repositories.checkout_repository import CheckoutRepository
    from app.repositories.stock_log_repository import StockLogRepository
    from app.repositories.system_config_repository import SystemConfigRepository
    from app.repositories.team_repository import TeamRepository
    from app.repositories.user_repository import UserRepository
    from app.services.bitza_service import BitzaService

    db = SessionLocal()
    try:
        service = BitzaService(
            db=db,
            bitza_repo=BitzaRepository(db),
            team_repo=TeamRepository(db),
            category_repo=CategoryRepository(db),
            user_repo=UserRepository(db),
            checkout_repo=CheckoutRepository(db),
            stock_log_repo=StockLogRepository(db),
            image_repo=BitzaImageRepository(db),
            audit_repo=AuditRepository(db),
            system_config_repo=SystemConfigRepository(db),
        )

        # --- Check for an existing root before prompting for anything ---
        existing = service.get_root_bitza()
        if existing:
            typer.echo(
                f"A root bitza already exists:\n"
                f"    ID:   {existing.id}\n"
                f"    Name: {existing.name}\n\n"
                f"There can only be one — no changes made."
            )
            return

        # --- Find or create the team the root will be responsible-to ---
        team_repo = TeamRepository(db)
        team_name = typer.prompt("Responsible team name (e.g. your club or household name)")
        team = team_repo.get_by_name(team_name)
        if not team:
            create_team = typer.confirm(
                f"No team named '{team_name}' exists yet. Create it?", default=True
            )
            if not create_team:
                typer.echo("No changes made.")
                return
            team = team_repo.create(Team(name=team_name))
            db.commit()
            typer.echo(f"✅  Created team '{team.name}'.\n")

        # --- Collect the root bitza's own name ---
        name = typer.prompt(
            "Root bitza name (e.g. your club or household name — this is the "
            "one permanent top-level container everything else lives under)",
            default=team_name,
        )

        try:
            root = service.create_root_bitza(name=name, responsible_team_id=team.id)
            typer.echo(
                f"\n✅  Root bitza created successfully.\n"
                f"    ID:   {root.id}\n"
                f"    Name: {root.name}"
            )
        except RootBitzaExistsError as exc:
            typer.echo(f"❌  Conflict: {exc.detail}", err=True)
            raise typer.Exit(code=1) from exc
        except Exception as exc:
            typer.echo(f"❌  {exc}", err=True)
            raise typer.Exit(code=1) from exc
    finally:
        db.close()


if __name__ == "__main__":
    app()
