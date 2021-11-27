import importlib.util
import os.path
from setuptools import setup, find_packages


HERE = os.path.abspath(os.path.dirname(__file__))

version_spec = importlib.util.spec_from_file_location(
    'version', os.path.join(HERE, 'falcon_sqla', 'version.py'))
version_mod = importlib.util.module_from_spec(version_spec)
version_spec.loader.exec_module(version_mod)
VERSION = version_mod.__version__

DESCRIPTION = 'Middleware for integrating Falcon applications with SQLAlchemy.'
with open(os.path.join(HERE, 'README.rst')) as readme_file:
    LONG_DESCRIPTION = readme_file.read()

REQUIRES = [
    'falcon >= 2.0.0',
    'SQLAlchemy >= 1.3.0',
]
EXTRAS_REQUIRE = {
    'docs': [
        'Sphinx >= 3.1.0',
        'sphinx-rtd-theme >= 0.5.0',
    ],
    'test': [
        'pytest',
        'pytest-cov',
    ],
}


setup(
    name='falcon-sqla',
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Database :: Front-Ends',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Programming Language :: Python',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    keywords='falcon wsgi database middleware orm sqlalchemy',
    author='Vytautas Liuolia',
    author_email='vytautas.liuolia@gmail.com',
    url='https://github.com/vytas7/falcon-sqla',
    license='Apache 2.0',
    packages=find_packages(exclude=['tests']),
    python_requires='>=3.6',
    install_requires=REQUIRES,
    extras_require=EXTRAS_REQUIRE,
)
