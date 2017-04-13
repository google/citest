from setuptools import setup

setup(
  name = 'citest',
  version = '0.1.0-dev',
  author = 'Eric Wiseblatt',
  author_email = 'ewiseblatt@google.com',
  packages = ['citest'],
  license = 'APL2',
  install_requires = [
    "boto3",
    "google-api-python-client",
    "mock",
    "oauth2client",
    "pyyaml",
  ],
  long_description = open('README.md').read()
)
