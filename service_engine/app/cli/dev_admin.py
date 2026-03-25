from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config

from app.core.settings import get_settings
from app.db.session import make_engine, make_session_factory
from app.modules.devtools import service as devtools_service

ROOT = Path(__file__).resolve().parents[2]


def _json_default(value):
    return str(value)


def _print_json(payload: dict[str, object], *, stream=None) -> None:
    target = stream or sys.stdout
    target.write(json.dumps(payload, sort_keys=True, default=_json_default))
    target.write("\n")


def _alembic_config() -> Config:
    get_settings.cache_clear()
    settings = get_settings()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def _build_session_factory():
    get_settings.cache_clear()
    settings = get_settings()
    engine = make_engine(settings.database_url, echo=settings.database_echo)
    return engine, make_session_factory(engine)


def _handle_error(exc: Exception) -> int:
    _print_json({"error": str(exc)}, stream=sys.stderr)
    return 1


def _command_migrate(_args: argparse.Namespace) -> int:
    try:
        command.upgrade(_alembic_config(), "head")
    except Exception as exc:  # noqa: BLE001
        return _handle_error(exc)
    _print_json({"action": "migrate", "revision": "head", "status": "ok"})
    return 0


def _command_seed_user(args: argparse.Namespace) -> int:
    engine, session_factory = _build_session_factory()
    try:
        with session_factory() as session:
            result = devtools_service.seed_user(
                session,
                email=args.email,
                nickname=args.nickname,
                initial_balance=args.initial_balance,
            )
    except Exception as exc:  # noqa: BLE001
        engine.dispose()
        return _handle_error(exc)
    engine.dispose()
    _print_json(
        {
            "action": "seed-user",
            "created_account": result.created_account,
            "created_user": result.created_user,
            "email": result.email,
            "nickname": result.nickname,
            "balance_units": result.balance_units,
            "reserved_units": result.reserved_units,
            "user_id": result.user_id,
        },
    )
    return 0


def _command_grant_credits(args: argparse.Namespace) -> int:
    engine, session_factory = _build_session_factory()
    try:
        with session_factory() as session:
            result = devtools_service.grant_credits(
                session,
                email=args.email,
                units=args.units,
            )
    except Exception as exc:  # noqa: BLE001
        engine.dispose()
        return _handle_error(exc)
    engine.dispose()
    _print_json(
        {
            "action": "grant-credits",
            "email": result.email,
            "balance_units": result.balance_units,
            "reserved_units": result.reserved_units,
            "user_id": result.user_id,
        },
    )
    return 0


def _command_reset_credits(args: argparse.Namespace) -> int:
    engine, session_factory = _build_session_factory()
    try:
        with session_factory() as session:
            result = devtools_service.reset_credits(
                session,
                email=args.email,
                balance=args.balance,
            )
    except Exception as exc:  # noqa: BLE001
        engine.dispose()
        return _handle_error(exc)
    engine.dispose()
    _print_json(
        {
            "action": "reset-credits",
            "email": result.email,
            "balance_units": result.balance_units,
            "reserved_units": result.reserved_units,
            "user_id": result.user_id,
        },
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Service engine developer admin CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate_parser = subparsers.add_parser("migrate", help="Apply Alembic migrations to head.")
    migrate_parser.set_defaults(handler=_command_migrate)

    seed_user_parser = subparsers.add_parser("seed-user", help="Create or update a dev user.")
    seed_user_parser.add_argument("--email", required=True)
    seed_user_parser.add_argument("--nickname")
    seed_user_parser.add_argument("--initial-balance", type=int, default=1000)
    seed_user_parser.set_defaults(handler=_command_seed_user)

    grant_credits_parser = subparsers.add_parser("grant-credits", help="Increase user credits.")
    grant_credits_parser.add_argument("--email", required=True)
    grant_credits_parser.add_argument("--units", type=int, required=True)
    grant_credits_parser.set_defaults(handler=_command_grant_credits)

    reset_credits_parser = subparsers.add_parser(
        "reset-credits",
        help="Set a user's balance to an exact value when no held credit exists.",
    )
    reset_credits_parser.add_argument("--email", required=True)
    reset_credits_parser.add_argument("--balance", type=int, required=True)
    reset_credits_parser.set_defaults(handler=_command_reset_credits)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

