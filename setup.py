# coding:utf-8
import os

from setuptools import find_packages, setup

NAME = "etherscan"

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as f:
    REQUIREMENTS = f.read().split("\n")

with open("test-requirements.txt", "r") as f:
    TEST_REQUIREMENTS = f.read().split("\n")


def package_files(package, directory):
    paths = []
    for (path, _, filenames) in os.walk(os.path.join(package, directory)):
        for filename in filenames:
            paths.append(os.path.join(path, filename))
    return paths


if __name__ == "__main__":
    setup(
        name=NAME,
        version="0.2.3",
        author="@neoctobers",
        author_email="neoctobers@gmail.com",
        description="Etherscan.io API wrapper",
        long_description=long_description,
        long_description_content_type="text/markdown",
        url="https://github.com/neoctobers/etherscan",
        package_dir={"": NAME},
        packages=find_packages(NAME, exclude=["tests*"]),
        package_data={NAME: package_files(NAME, ".")},
        classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
        install_requires=REQUIREMENTS + TEST_REQUIREMENTS,
    )
