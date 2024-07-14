import pytest
from subtensor_setup import (
    Roles,
    get_subnet_info,
    has_sufficient_stake,
    initialize_roles,
    is_wallet_registered,
)


@pytest.fixture
def roles():
    return initialize_roles()


def test_subnet_owner_exists(roles):
    owner_wallet = roles[Roles.SUBNET_OWNER.name].wallet
    subnet_info = get_subnet_info(owner_wallet)
    assert subnet_info is not None, "Subnet owner does not exist"


def test_validator_registered(roles):
    assert is_wallet_registered(Roles.SUBNET_VALI, roles), "Validator not registered"


def test_miner_registered(roles):
    assert is_wallet_registered(Roles.SUBNET_MINER, roles), "Miner not registered"


def test_validator_stake_added(roles):
    assert has_sufficient_stake(roles), "Stake not added for the validator"
