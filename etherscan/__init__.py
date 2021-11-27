# coding:utf-8
from .etherscan import *
import requests
from bs4 import BeautifulSoup
import os
import yaml

name = "etherscan"  # pylint: disable=invalid-name


def dir_abs_path():
    return os.path.abspath(os.path.dirname(__file__))


def _get_missing_calls():
    url = "https://docs.etherscan.io/api-endpoints/"
    url_methods = set()

    pages = [
        "accounts", "contracts", "transactions",
        "blocks", "logs", "geth-parity-proxy", 
        "tokens", "gas-tracker", "stats"
        ]

    for page in  pages:
        r = requests.get(url + page)
        soup = BeautifulSoup(r.content)
        for div in soup.find_all("div", dir="auto"):
            line = div.text.strip()
            if line and line.startswith("&action="):
                url_methods.add(line.split("=")[1])

    etherscan_file = os.path.join(dir_abs_path(), "etherscan.py")
    with open(etherscan_file, "r") as file_:
        data = file_.readlines()

    py_methods = set()
    for line in data:
        if not line.strip().startswith('self._params["action"]'):
            continue
        py_methods.add(line.strip().split("=")[1].strip()[1:-1])

    return url_methods - py_methods


def save_missing_calls():
    missing_calls_yaml = os.path.join(dir_abs_path(), "..", "tests", "data", "missing_calls.yaml"
    )
    with open(missing_calls_yaml, "w+") as file_:
        yaml.dump({"missing_calls": list(_get_missing_calls())}, file_)
