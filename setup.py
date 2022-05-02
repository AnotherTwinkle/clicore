#!/usr/bin/env python

from setuptools import setup, find_packages

requirements = []
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(name = "clicore",
        version = "0.4",
        author = "AnotherTwinkle",
        url = "https://www.github.com/AnotherTwinkle/clicore",
        packages = ["clicore"],
        install_requires = requirements,
        include_package_data = True,
        )
        
