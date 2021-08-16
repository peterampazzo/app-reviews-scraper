from setuptools import find_packages, setup
import setuptools

setup(
  name='app_scraper',
  version='1.0.0',
  packages=setuptools.find_packages(where="src"),
  package_dir={"": "src"}
#   entrypoints={
#     'console_scripts': [
#       'foo=src.main:main',
#     ],
#   },
)