# coding:utf-8
import getpass
import os
import re
import tempfile

import requests_cache
from errors import EtherscanIoException


def _bool(text: str):
    """Convert str to bool"""
    if text.lower() in ["0", "false", "none", "null", "n/a", ""]:
        return False
    return True


def to_snake_case(name):
    if name == "timeStamp":
        return "timestamp"
    if name == "txreceipt_status":
        return "tx_receipt_status"
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub('__([A-Z])', r'_\1', name)
    name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)
    return name.lower()


def __convert(source):
    converted = {}
    for key, value in source.items():
        key = to_snake_case(key)
        if key.startswith("is_") or key.endswith("_status"):
            converted[key] = _bool(value)
            continue
        if value == "":
            converted[key] = None
            continue
        if value.isdigit():
            converted[key] = int(value)
            continue
        raise ValueError("something went wrong - key: {key}, value: {value}")
    return source


def shared(func):
    shared.instances = {}

    def getinstance(self, *args, **kwargs):
        if func.__name__ not in shared.instances:
            shared.instances[func.__name__] = func(self, *args, **kwargs)
        return shared.instances[func.__name__]
    return getinstance


def single_excercise(func):
    # pylint: disable=protected-access
    def inner(self, *args, **kwargs):
        if not hasattr(self, '_instances'):
            setattr(self, "_instances", {})
        if func.__name__ not in self._instances:
            self._instances[func.__name__] = func(self, *args, **kwargs)
        return self._instances[func.__name__]
    # pylint: enable=protected-access
    return inner


class BaseClient:
    def __init__(
        self,
        api_key=None,
        network=None,
        cache_backend="sqlite",
        cache_expire_after=5,
    ):

        # API URL
        self._api_url = "https://api.etherscan.io/api"

        # API Key
        self._api_key = api_key

        # Network
        if network:
            if network not in ["ropsten", "kovan", "rinkeby"]:
                raise Exception(
                    "network could only be None(mainnet) /ropsten/kovan/rinkeby"
                )

            self._api_url = "https://api-{network}.etherscan.io/api".format(
                network=network
            )

        # params
        self._reset_params()

        # session & cache
        self._cache_backend = cache_backend
        self._cache_expire_after = cache_expire_after

    @property
    @shared
    def api_key(self):
        if self._api_key:
            os.environ["ETHERSCAN_KEY"] = self._api_key
            return self._api_key
        self._api_key = os.getenv("ETHERSCAN_KEY")
        if not self._api_key:
            self._api_key = getpass.getpass("Input etherscan key: ")
            os.environ["ETHERSCAN_KEY"] = self._api_key
        return self._api_key

    @property
    @shared
    def cache_name(self):
        return os.path.join(tempfile.gettempdir(), "etherscan_cache")

    @property
    @shared
    def session(self):
        session = requests_cache.core.CachedSession(
            cache_name=self.cache_name,
            backend=self._cache_backend,
            expire_after=self._cache_expire_after,
        )
        session.headers.update({
            "User-agent": "etherscan - python wrapper "
            "around etherscan.io (github.com/neoctobers/etherscan)"
        })
        return session

    def _req(self):
        response = self.session.post(url=self._api_url, data=self._params).json()

        self._reset_params()

        if response["status"] == "0":
            print("--- Etherscan.io Message ---", response["message"])

        return response["result"]

    def _reset_params(self):
        self._params = {
            "apikey": self._api_key,
        }


class ProxyClient(BaseClient):

    def _reset_params(self):
        self._params = {
            "apikey": self._api_key,
            "module": "proxy"
        }

    def get_gas_price(self):
        """Get gas price."""
        self._params["action"] = "eth_gasPrice"
        return int(self._req(), 16)

    def get_block_number(self):
        """Get latest block number."""
        self._params["action"] = "eth_blockNumber"
        return int(self._req(), 16)

    def get_block_by_number(self, block_number):
        """Get block by number."""
        self._params["action"] = "eth_getBlockByNumber"
        self._params["tag"] = hex(block_number)
        self._params["boolean"] = True
        return self._req()


class StatsClient(BaseClient):
    def _reset_params(self):
        self._params = {
            "apikey": self._api_key,
            "module": "stats"
        }

    def get_eth_price(self):
        """Get ETH price."""
        self._params["action"] = "ethprice"
        response = self._req()
        return {
            "ethbtc": float(response["ethbtc"]),
            "ethbtc_timestamp": int(response["ethbtc_timestamp"]),
            "ethusd": float(response["ethusd"]),
            "ethusd_timestamp": int(response["ethbtc_timestamp"]),
        }

    def get_eth_supply(self):
        self._params["action"] = "ethsupply"
        return int(self._req())


class AccountClient(BaseClient):
    def _reset_params(self):
        self._params = {
            "apikey": self._api_key,
            "module": "account"
        }

    def get_eth_balance(self, address: str):
        """Get ETH balance by address."""
        self._params["action"] = "balance"
        self._params["address"] = address

        return int(self._req())

    def get_eth_balances(self, addresses: list):
        """Get ETH balances by addresses list."""
        self._params["action"] = "balancemulti"
        self._params["address"] = ",".join(addresses)

        balances = {}
        for row in self._req():
            balances[row["account"]] = int(row["balance"])

        return balances

    def get_transactions_by_address(
        self,
        address: str,
        type_: str = "normal",
        start_block: int = 0,
        end_block: int = 999999999,
        page: int = 1,
        limit: int = 1000,
        sort: str = "asc",
    ):  # pylint: disable=too-many-arguments
        """Get transactions by address."""
        types = {
            "normal": "txlist",
            "internal": "txlistinternal",
        }
        if type_ not in types:
            raise Exception('param `type_` must be "normal" or "internal"')
        self._params["action"] = types[type_]
        self._params["address"] = address
        self._params["startblock"] = start_block
        self._params["endblock"] = end_block
        self._params["page"] = page
        self._params["offset"] = limit
        self._params["sort"] = sort

        response = self._req()

        transactions = []
        for transaction in response:
            transactions.append(__convert(transaction))

        return transactions

    def get_token_transactions(
        self,
        contract_address: str = None,
        address: str = None,
        start_block: int = 0,
        end_block: int = 999999999,
        page: int = 1,
        limit: int = 1000,
        sort: str = "asc",
    ):  # pylint: disable=too-many-arguments
        """Get ERC20 token transactions by contract address."""
        if contract_address is None and address is None:
            raise EtherscanIoException(
                "Param `contract_address` and `address` cannot be None at the same time."
            )

        self._params["action"] = "tokentx"

        if contract_address:
            self._params["contractaddress"] = contract_address

        if address:
            self._params["address"] = address

        self._params["startblock"] = start_block
        self._params["endblock"] = end_block
        self._params["page"] = page
        self._params["offset"] = limit
        self._params["sort"] = sort

        response = self._req()

        token_transactions = []
        for transaction in response:
            token_transactions.append(__convert(transaction))

        return token_transactions


class Client(BaseClient):
    @property
    @single_excercise
    def account(self):
        return AccountClient()

    @property
    @single_excercise
    def stats(self):
        return StatsClient()

    @property
    @single_excercise
    def proxy(self):
        return ProxyClient()
