import os
import re
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


def read(f):

    return open(os.path.join(os.path.dirname(__file__), f)).read().strip()

try:

    version = re.findall(r"""^__version__ = "([^']+)"\r?$""",
                         read(os.path.join("sioinstagram", "__init__.py")),
                         re.M)[0]

except IndexError:

    raise RuntimeError("Unable to determine version.")


setup(
    name="sioinstagram",
    version=version,
    description=("Sans io instagram api with couple io backends"),
    long_description=read("readme.md"),
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
    author="pohmelie",
    author_email="multisosnooley@gmail.com",
    url="https://github.com/pohmelie/sioinstagram",
    license="WTFPL",
    packages=find_packages(),
    install_requires=[],
    include_package_data=True,
)
