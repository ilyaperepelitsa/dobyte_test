import click
import logging

logging.basicConfig(level=logging.INFO)

@click.group()
def cli():
    pass

if __name__ == "__main__":
    cli()
