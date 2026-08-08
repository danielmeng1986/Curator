"""Run the Curator Backend or a supported local administration command."""

from .auth_cli import main as auth_cli_main
from .server import main


if __name__ == "__main__":
    cli_result = auth_cli_main()
    if cli_result is None:
        main()
    raise SystemExit(cli_result)
