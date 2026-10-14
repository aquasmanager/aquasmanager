from version import __version__


def test_version(api):
    info = api.get("/about/version")
    assert info["version"] == __version__ and info["build"]
