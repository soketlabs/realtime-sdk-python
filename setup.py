import os
import re

import setuptools
from setuptools import setup

_PACKAGE_NAME = 'soket-realtime'
_PACKAGE_DIR = 'realtime'
_REPO_REAL_PATH = os.path.dirname(os.path.realpath(__file__))
_PACKAGE_REAL_PATH = os.path.join(_REPO_REAL_PATH, _PACKAGE_DIR)

# Read the repo version
# We can't use `.__version__` from the library since it's not installed yet
with open(os.path.join(_PACKAGE_REAL_PATH, '__init__.py')) as f:
    content = f.read()
# regex: '__version__', whitespace?, '=', whitespace, quote, version, quote
# we put parens around the version so that it becomes elem 1 of the match
#expr = re.compile(r"""^__version__\W+=\W+['"]([0-9\.]*)['"]""", re.MULTILINE)
#repo_version = expr.findall(content)[0]

# Use repo README for PyPi description
with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

# Hide the content between <!-- SETUPTOOLS_LONG_DESCRIPTION_HIDE_BEGIN --> and
# <!-- SETUPTOOLS_LONG_DESCRIPTION_HIDE_END --> tags in the README
while True:
    start_tag = '<!-- SETUPTOOLS_LONG_DESCRIPTION_HIDE_BEGIN -->'
    end_tag = '<!-- SETUPTOOLS_LONG_DESCRIPTION_HIDE_END -->'
    start = long_description.find(start_tag)
    end = long_description.find(end_tag)
    if start == -1:
        assert end == -1, 'there should be a balanced number of start and ends'
        break
    else:
        assert end != -1, 'there should be a balanced number of start and ends'
        long_description = long_description[:start] + long_description[
            end + len(end_tag):]

classifiers = [
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
]

install_requires = [
    'websockets',
    'numpy',
]

extra_deps = {}

# extra_deps['all'] = set(dep for deps in extra_deps.values() for dep in deps)

setup(
    name=_PACKAGE_NAME,
    version="0.0.1",
    author='SoketLabs',
    author_email='reachout@soket.ai',
    description='Realtime',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/soketlabs/realtime-sdk-python',
    package_data={
        'pragna': ['py.typed'],
    },
    packages=setuptools.find_packages(
        exclude=['.github*', 'cli*', 'scripts*', 'tests*']),
    classifiers=classifiers,
    install_requires=install_requires,
    # extras_require=extra_deps,
    python_requires='>=3.7',
)
