"""Load the shared app configuration independently of the working directory."""
from pathlib import Path

from pyhocon import ConfigFactory

APP_CONFIG = Path(__file__).resolve().parents[1] / 'app.conf'


def load_app_config(path=None):
    return ConfigFactory.parse_file(str(Path(path or APP_CONFIG).expanduser().resolve()))
