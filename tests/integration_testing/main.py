from subtensor_setup import (
    Roles,
    add_stake_to_validator,
    create_subnet,
    get_subnet_info,
    has_sufficient_stake,
    initialize_roles,
    is_wallet_registered,
    register_miner_for_subnet,
    register_on_root_subnet,
    register_validator_for_subnet,
    transfer_funds_to_owner,
)

create_new_subnet = False  # Set this to your desired value


def main():
    roles = initialize_roles()
    print(f"roles {roles} \n")

    if create_new_subnet:
        transfer_funds_to_owner(roles)
        create_subnet(roles)

    owner_wallet = roles[Roles.SUBNET_OWNER.name].wallet
    print(f"Owner Wallet: {owner_wallet} \n")
    subnet_info = get_subnet_info(owner_wallet)

    print(f"Subnet info: {subnet_info} \n")

    if subnet_info:
        netuid = subnet_info.netuid
        print(f"Owner owns subnet uid: {netuid}")
        print(f"Subnet info: {subnet_info}")

        if not is_wallet_registered(Roles.SUBNET_VALI, roles):
            print(f"Registering validator for netuid: {netuid}")
            register_validator_for_subnet(netuid, roles)
        else:
            print(f"Validator already registered for netuid: {netuid}")

        if not is_wallet_registered(Roles.SUBNET_MINER, roles):
            print(f"Registering miner for netuid: {netuid}")
            register_miner_for_subnet(netuid, roles)
        else:
            print(f"Miner already registered for netuid: {netuid}")

    print("Registering on root subnet...")
    register_on_root_subnet(roles)

    if not has_sufficient_stake(roles):
        print("Adding stake to validator")
        add_stake_to_validator(roles)
    else:
        print("Validator already has sufficient stake")


if __name__ == "__main__":
    main()
