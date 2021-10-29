from typing import List

import setuptools

from local_metaflow_deployment import __version__


def get_long_description() -> str:
    with open('README.md') as fh:
        return fh.read()


def get_required() -> List[str]:
    with open('requirements.txt') as fh:
        return fh.read().splitlines()


setuptools.setup(
    name='local_metaflow_deployment',
    packages=setuptools.find_packages(),
    version=__version__,
    license='Apache',
    description="A module to setup a local docker setup of Metaflow's " 
                "metadata service, Metaflow ui and Metaflow UI service. ",
    author='Valay Dave',
    include_package_data=True,
    author_email='valaygaurang@gmail.com',
    
    long_description=get_long_description(),
    long_description_content_type='text/markdown',
    keywords=["machine learning"],
    install_requires=get_required(),
    python_requires='>=3.6',
    entry_points={
        'console_scripts': ['local-metaflow-deployment=local_metaflow_deployment.__main__:deployment_cli'],
    }
)