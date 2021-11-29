import pathlib
import re
import setuptools


if __name__ == '__main__':
    # NOTE(vytas): It is unfortunate to resort to the below regex, but
    #   apparently attribute lookup via setup.cfg is very fragile otherwise.
    here = pathlib.Path(__file__).parent
    with open(here / 'falcon_sqla' / 'version.py') as version_py:
        match = re.search(r"^__version__ = \'(.+)\'$", version_py.read(), re.M)
        assert match, 'Could not extract module version'
        version = match.group(1)

    setuptools.setup(name='falcon-sqla', version=version)
