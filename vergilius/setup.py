from setuptools import setup
from setuptools import find_packages

install_requires = [
    'acme',
    'letsencrypt',
    'python-consul',
    'tornado',
]

setup(
        name='vergilius_letsencrypt',
        description="Vergilius plugin for Let's Encrypt client",
        url='https://github.com/E96/vergilius',
        author="Vasiliy Ostanin",
        author_email='bazilio@e96.ru',
        license='Apache License 2.0',
        install_requires=install_requires,
        packages=find_packages(),
        scripts=['vergilius.py'],
)
