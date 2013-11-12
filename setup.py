import os
import re
from setuptools import setup, find_packages

rel_file = lambda *args: os.path.join(os.path.dirname(os.path.abspath(__file__)), *args)

def read_from(filename):
    fp = open(filename)
    try:
        return fp.read()
    finally:
        fp.close()

def get_long_description():
    return read_from(rel_file('README.rst'))

def get_version():
    data = read_from(rel_file('stowaway', '__init__.py'))
    return re.search(r"__version__ = '([^']+)'", data).group(1)

setup(
    name='stowaway',
    description='Stowaway gives simple docker image deployment through vagrant provisioned machines.',
    long_description=get_long_description(),
    version=get_version(),
    scripts=['scripts/stowaway'],
    packages=find_packages(),
    include_package_data = True,
    url='https://github.com/zbyte64/stowaway/',
    author='Jason Kraus',
    author_email='zbyte64@gmail.com',
    license='BSD',
    install_requires=[
        "fabric",
        "python-vagrant",
        "PySO8601",
        "micromodels-ng==0.6.3",
        "microcollections==0.0.5",
        "pyyaml",
    ],
    tests_require=["nose"],
    test_suite = 'nose.collector',
    classifiers = [
        'Programming Language :: Python',
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: Public Domain',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
