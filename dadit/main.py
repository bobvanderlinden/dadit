import argparse
from .commands.patch import subparser as patch_subparser


def main():
    parser = argparse.ArgumentParser(
        prog="dadit",
        add_help=True,
    )
    subparsers = parser.add_subparsers(dest="subcommand")
    patch_subparser(subparsers)

    args = parser.parse_args()
    kwargs = vars(args)
    subcommand = kwargs.pop("subcommand")
    subcommand(**kwargs)
