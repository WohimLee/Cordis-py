import cordis
from cordis.loader import ConfigReloader, Loader, YamlConfigParser


def test_package_is_importable() -> None:
    assert cordis.__version__ == "0.1.0"
    assert Loader.__module__ == "cordis.loader.runtime"
    assert ConfigReloader.__module__ == "cordis.loader.reloader"
    assert YamlConfigParser.__module__ == "cordis.loader.parser"
