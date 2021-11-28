# coding:utf-8
import getpass
import os
import re
import tempfile
import time
from datetime import datetime as dt

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
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub("__([A-Z])", r"_\1", name)
    name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def _convert(source):
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
        converted[key] = value
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
        if not hasattr(self, "_instances"):
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
        self._rate_count = None

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
        session.headers.update(
            {
                "User-agent": "etherscan - python wrapper "
                "around etherscan.io (github.com/neoctobers/etherscan)"
            }
        )
        return session

    def _req(self):
        response = self.session.post(url=self._api_url, data=self._params).json()

        self._reset_params()

        if response["status"] == "0":
            print("--- Etherscan.io Message ---", response["message"])

        return response["result"]

    def _reset_params(self):
        self._params = {
            "apikey": self.api_key,
        }


class Accounts(BaseClient):
    def _reset_params(self):
        self._params = {"apikey": self.api_key, "module": "account"}

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
        start_block: int = 0,
        end_block: int = 999999999,
        page: int = 1,
        limit: int = 10000,
        sort: str = "asc",
    ):  # pylint: disable=too-many-arguments
        """Get transactions by address."""
        self._params["action"] = "txlist"
        self._params["address"] = address
        self._params["startblock"] = start_block
        self._params["endblock"] = end_block
        self._params["page"] = page
        self._params["offset"] = limit
        self._params["sort"] = sort

        response = self._req()

        transactions = []
        for transaction in response:
            transactions.append(_convert(transaction))

        return transactions

    def get_internal_transactions_by_address(
        self,
        address: str,
        start_block: int = 0,
        end_block: int = 999999999,
        page: int = 1,
        limit: int = 10000,
        sort: str = "asc",
    ):  # pylint: disable=too-many-arguments
        """Get transactions by address."""
        self._params["action"] = "txlistinternal"
        self._params["address"] = address
        self._params["startblock"] = start_block
        self._params["endblock"] = end_block
        self._params["page"] = page
        self._params["offset"] = limit
        self._params["sort"] = sort

        response = self._req()

        transactions = []
        for transaction in response:
            transactions.append(_convert(transaction))

        return transactions

    def get_token_transactions(
        self,
        contract_address: str = None,
        address: str = None,
        start_block: int = 0,
        end_block: int = 999999999,
        page: int = 1,
        limit: int = 10000,
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
            token_transactions.append(_convert(transaction))

        return token_transactions


class Contracts(BaseClient):
    def _reset_params(self):
        self._params = {"apikey": self.api_key, "module": "contract"}

    def get_abi(self, address):
        self._params["action"] = "getabi"
        self._params["address"] = address
        return self._req()

    def get_source_code(self, address):
        self._params["action"] = "getsourcecode"
        self._params["address"] = address
        return self._req()


class Transactions(BaseClient):
    def _reset_params(self):
        self._params = {"apikey": self.api_key, "module": "transaction"}

    def get_tx_receipt_status(self, tx_hash):
        self._params["action"] = "gettxreceiptstatus"
        self._params["txhash"] = tx_hash
        return self._req()


class Blocks(BaseClient):
    def _reset_params(self):
        self._params = {"apikey": self.api_key, "module": "block"}

    def get_block_countdown(self, block_no):
        self._params["action"] = "getblockcountdown"
        self._params["blockno"] = block_no
        return self._req()

    def get_block_no_by_time(self, timestamp, closest="before"):
        if closest not in ["before", "after"]:
            raise ValueError(f"Something went wrong: {closest}")
        self._params["action"] = "getblocknobytime"
        self._params["timestamp"] = timestamp
        self._params["closest"] = closest
        return int(self._req())

    @property
    def latest_block(self):
        return self.get_block_no_by_time(int(time.time()))


class Logs(BaseClient):
    def _reset_params(self):
        self._params = {"apikey": self.api_key, "module": "logs"}

    def get_logs(self, from_block, to_block, address, topic):
        self._params["action"] = "getlogs"
        self._params["fromBlock"] = from_block
        self._params["toBlock"] = to_block
        self._params["address"] = address
        self._params["topic0"] = topic
        return self._req()


class GethParityProxy(BaseClient):
    def _reset_params(self):
        self._params = {"apikey": self.api_key, "module": "proxy"}

    def get_block_number(self):
        """Get latest block number."""
        self._params["action"] = "eth_blockNumber"
        return int(self._req(), 16)

    def get_block_by_number(self, block_number, boolean=True):
        """Get block by number."""
        self._params["action"] = "eth_getBlockByNumber"
        self._params["tag"] = hex(block_number)
        self._params["boolean"] = boolean
        return self._req()

    def get_uncle_by_block_number_and_index(self, block_number):
        self._params["action"] = "eth_getUncleByBlockNumberAndIndex"
        self._params["tag"] = hex(block_number)
        return self._req()

    def get_block_transaction_count_by_number(self, block_number):
        self._params["action"] = "eth_getBlockTransactionCountByNumber"
        self._params["tag"] = hex(block_number)
        return self._req()

    def get_transaction_by_hash(self, tx_hash):
        self._params["action"] = "eth_getTransactionByHash"
        self._params["txhash"] = tx_hash
        return self._req()

    def get_transaction_by_block_number_and_index(self, block_number, index):
        self._params["action"] = "eth_getTransactionByBlockNumberAndIndex"
        self._params["tag"] = hex(block_number)
        self._params["index"] = hex(index)
        return self._req()

    def get_transaction_count(self, address, tag):
        if tag not in ["earlist", "pending", "latest"]:
            raise ValueError(f"Something went wrong: {tag}")
        self._params["action"] = "eth_getTransactionCount"
        self._params["address"] = address
        self._params["tag"] = tag
        return self._req()

    def send_raw_transaction(self, hex_):
        self._params["action"] = "eth_sendRawTransaction"
        self._params["hex"] = hex(hex_)
        return self._req()

    def get_transaction_receipt(self, tx_hash):
        self._params["action"] = "eth_getTransactionReceipt"
        self._params["txhash"] = tx_hash
        return self._req()

    def call(self, to_, data, tag):
        if tag not in ["earlist", "pending", "latest"]:
            raise ValueError(f"Something went wrong: {tag}")
        self._params["action"] = "eth_call"
        self._params["to"] = to_
        self._params["data"] = data
        self._params["tag"] = tag
        return self._req()

    def get_code(self, address, tag):
        if tag not in ["earlist", "pending", "latest"]:
            raise ValueError(f"Something went wrong: {tag}")
        self._params["action"] = "eth_getCode"
        self._params["address"] = address
        self._params["tag"] = tag
        return self._req()

    def get_storage_at(self, position, tag):
        if tag not in ["earlist", "pending", "latest"]:
            raise ValueError(f"Something went wrong: {tag}")
        self._params["action"] = "eth_getStorageAt"
        self._params["position"] = hex(position)
        self._params["tag"] = tag
        return self._req()

    def get_gas_price(self):
        """Get gas price."""
        self._params["action"] = "eth_gasPrice"
        return int(self._req(), 16)

    def estimate_gas(self):
        """Get gas price."""
        self._params["action"] = "eth_estimateGas"
        raise NotImplementedError()


class Tokens(BaseClient):
    def _reset_params(self):
        self._params = {"apikey": self.api_key, "module": "token"}


class GasTracker(BaseClient):
    def _reset_params(self):
        self._params = {"apikey": self.api_key, "module": "gas"}


class Stats(BaseClient):
    def _reset_params(self):
        self._params = {"apikey": self.api_key, "module": "stats"}

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


class Client(BaseClient):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self._start_time = None

    @property
    @single_excercise
    def accounts(self):
        return Accounts()

    @property
    @single_excercise
    def contracts(self):
        return Contracts()

    @property
    @single_excercise
    def transactions(self):
        return Transactions()

    @property
    @single_excercise
    def blocks(self):
        return Blocks()

    @property
    @single_excercise
    def logs(self):
        return Logs()

    @property
    @single_excercise
    def geth_parity_proxy(self):
        return GethParityProxy()

    @property
    @single_excercise
    def tokens(self):
        return Tokens()

    @property
    @single_excercise
    def gas_tracker(self):
        return GasTracker()

    @property
    @single_excercise
    def stats(self):
        return Stats()

    def get_transaction_history_by_address(self, address, start=None, end=None):

        form = "%m/%d/%Y"

        if start:
            self._start_time = start

        if not self._start_time:
            raise ValueError("Something went wrong")

        start_timestamp = int(dt.timestamp(dt.strptime(self._start_time, form)))

        if end:
            end_timestamp = int(dt.timestamp(dt.strptime(end, form)))
        else:
            end_timestamp = int(time.time())
            end = dt.strftime(dt.fromtimestamp(end_timestamp), form)

        if start_timestamp > end_timestamp:
            return

        twenty_four_hours = 60 * 60 * 24
        transactions = self.accounts.get_transactions_by_address(
            address,
            start_block=self.blocks.get_block_no_by_time(
                end_timestamp - twenty_four_hours
            ),
            end_block=self.blocks.get_block_no_by_time(end_timestamp),
        )

        yield transactions

        end_timestamp -= twenty_four_hours
        end = dt.strftime(dt.fromtimestamp(end_timestamp), form)
        self.get_transaction_history_by_address(address, end=end)
