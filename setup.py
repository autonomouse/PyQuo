from setuptools import setup, find_packages
import pyquo
from pyquo.__init__ import __version__

setup(
    name="pyquo",
    version=__version__,
    description="HTML generator",
    author="Darren Hoyland",
    author_email="<darren@hoyland.me>",
    url="https://github.com/autonomouse/PyQuo",
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python",
        "Topic :: Internet",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Intended Audience :: Developers"],
    entry_points={
        "console_scripts": [
            'pyquo = pyquo.pyquo:main',
        ]
    },
)
