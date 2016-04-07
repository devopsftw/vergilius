from setuptools import setup
from setuptools import find_packages

install_requires = [
    'python-consul',
    'tornado',
    'setuptools>=1.0',
    'zope.component',
    'zope.interface',
]

setup(
        name='vergilius',
        description="Vergilius self configuring web server",
        url='https://github.com/devopsftw/vergilius',
        author="Vasiliy Ostanin",
        author_email='bazilio91@gmail.ru',
        license='Apache License 2.0',
        install_requires=install_requires,
        # packages=['vergilius'],
        include_package_data=True,
)
