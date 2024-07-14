import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

import bittensor
from bittensor.cli import (
    RegisterCommand,
    RegisterSubnetworkCommand,
    RootRegisterCommand,
    StakeCommand,
    TransferCommand,
    WalletBalanceCommand,
)
from substrateinterface import Keypair


@dataclass
class RoleInfo:
    keypair: Keypair
    wallet: bittensor.wallet
    exec_command: callable


class Roles(Enum):
    SUBNET_OWNER = "//Alice"
    SUBNET_VALI = "//Bob"
    SUBNET_MINER = "//Charlie"


default_netuid = 4
subtensor_network = "***REMOVED***"
# subtensor_network = "ws://127.0.0.1:9946"
default_wallet_path = "~/.bittensor/wallets"
# Get the directory of the current script file
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define the wallet path using the script directory
wallet_path = os.path.join(script_dir, ".bittensor", "wallets")
base_args = [
    "--no_prompt",
    "--wallet.path",
    wallet_path,
    "--subtensor.network",
    subtensor_network,
]
transfer_to_subnet_owner_amt = 500
validator_stake_amt = 100
coldkey_format = "do_not_use_{}"


def get_coldkey_name(uri: str):
    return coldkey_format.format(uri.strip("/"))


def setup_wallet(uri: str, coldkey_name: str) -> RoleInfo:
    keypair = Keypair.create_from_uri(uri)
    wallet = bittensor.wallet(path=wallet_path, name=coldkey_name)

    wallet.set_coldkey(keypair=keypair, encrypt=False, overwrite=True)
    wallet.set_coldkeypub(keypair=keypair, encrypt=False, overwrite=True)
    wallet.set_hotkey(keypair=keypair, encrypt=False, overwrite=True)

    parser = bittensor.cli.__create_parser__()

    def exec_command(command, extra_args: List[str]):
        cli_instance = bittensor.cli(
            bittensor.config(
                parser=parser,
                args=extra_args + base_args,
            )
        )
        command.run(cli_instance)

    return RoleInfo(keypair, wallet, exec_command)


def initialize_roles() -> dict[str, RoleInfo]:
    roles = {}
    for r in Roles:
        role_info = setup_wallet(r.value, get_coldkey_name(r.name))
        roles[r.name] = role_info
    return roles


def transfer_funds_to_owner(roles: Dict[str, RoleInfo]):
    owner_wallet = roles[Roles.SUBNET_OWNER.name].wallet
    for r in Roles:
        if r == Roles.SUBNET_OWNER:
            continue

        exec_command = roles[r.name].exec_command
        coldkey_name = get_coldkey_name(r.name)
        exec_command(
            TransferCommand,
            [
                "wallet",
                "transfer",
                "--dest",
                str(owner_wallet.hotkey.ss58_address),
                "--amount",
                str(transfer_to_subnet_owner_amt),
                "--wallet.name",
                coldkey_name,
            ],
        )
        print(
            f"Transferred from {owner_wallet.hotkey.ss58_address} {transfer_to_subnet_owner_amt} to {coldkey_name}"
        )
        exec_command(
            WalletBalanceCommand,
            ["wallet", "balance", "--wallet.name", coldkey_name],
        )


def create_subnet(roles: Dict[str, RoleInfo]):
    owner_exec = roles[Roles.SUBNET_OWNER.name].exec_command
    owner_exec(
        RegisterSubnetworkCommand,
        [
            "subnet",
            "create",
            "--wallet.name",
            get_coldkey_name(Roles.SUBNET_OWNER.name),
        ],
    )


def get_subnet_info(
    wallet: bittensor.wallet, netuid: int = default_netuid
) -> bittensor.SubnetInfo:
    tmp_args = [
        "subnet",
        "list",
        "--no_prompt",
        "--subtensor.network",
        subtensor_network,
    ]
    tmp_config = bittensor.config(
        parser=bittensor.cli.__create_parser__(), args=tmp_args
    )
    subtensor = bittensor.subtensor(config=tmp_config)

    subnet_infos: List[bittensor.SubnetInfo] = subtensor.get_all_subnets_info()
    for info in subnet_infos:
        print(f"subnet_infos...... {info} \n")
        if info.owner_ss58 == wallet.coldkey.ss58_address and info.netuid == netuid:
            return info
    return None


def register_validator_for_subnet(netuid: int, roles: Dict[str, RoleInfo]):
    vali_exec = roles[Roles.SUBNET_VALI.name].exec_command
    vali_exec(
        RegisterCommand,
        [
            "subnet",
            "register",
            "--netuid",
            str(netuid),
            "--wallet.name",
            get_coldkey_name(Roles.SUBNET_VALI.name),
            "--wallet.hotkey",
            "default",
        ],
    )


def register_miner_for_subnet(netuid: int, roles: Dict[str, RoleInfo]):
    miner_exec = roles[Roles.SUBNET_MINER.name].exec_command
    miner_exec(
        RegisterCommand,
        [
            "subnet",
            "register",
            "--netuid",
            str(netuid),
            "--wallet.name",
            get_coldkey_name(Roles.SUBNET_MINER.name),
            "--wallet.hotkey",
            "default",
        ],
    )


def register_on_root_subnet(roles: Dict[str, RoleInfo]):
    vali_exec = roles[Roles.SUBNET_VALI.name].exec_command
    vali_exec(
        RootRegisterCommand,
        [
            "root",
            "register",
            "--wallet.name",
            get_coldkey_name(Roles.SUBNET_VALI.name),
            "--wallet.hotkey",
            "default",
        ]
        + base_args,
    )


def add_stake_to_validator(roles: Dict[str, RoleInfo]):
    vali_exec = roles[Roles.SUBNET_VALI.name].exec_command
    vali_exec(
        StakeCommand,
        [
            "stake",
            "add",
            "--wallet.name",
            get_coldkey_name(Roles.SUBNET_VALI.name),
            "--wallet.hotkey",
            "default",
            "--amount",
            str(validator_stake_amt),
        ]
        + base_args,
    )


def is_wallet_registered(roleType: Roles, roles: Dict[str, RoleInfo]) -> bool:
    wallet = roles[roleType.name].wallet
    subtensor = bittensor.subtensor(network=subtensor_network)
    return subtensor.is_hotkey_registered_on_subnet(
        wallet.hotkey.ss58_address, default_netuid
    )


def has_sufficient_stake(roles: dict[str, RoleInfo]):
    vali_wallet = roles[Roles.SUBNET_VALI.name].wallet
    subtensor = bittensor.subtensor(network=subtensor_network)
    stake_amount = subtensor.get_total_stake_for_hotkey(vali_wallet.hotkey.ss58_address)
    if stake_amount is None:
        raise ValueError(
            f"No stake amount found for wallet: {vali_wallet.hotkey.ss58_address}"
        )

    return stake_amount.tao >= validator_stake_amt
