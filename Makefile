PRECOMMIT_VERSION="3.7.1"

.PHONY: hooks

hooks:
	@echo "Grabbing pre-commit version ${PRECOMMIT_VERSION} and installing pre-commit hooks"
	if [ ! -f pre-commit.pyz ]; then \
		wget -O pre-commit.pyz https://github.com/pre-commit/pre-commit/releases/download/v${PRECOMMIT_VERSION}/pre-commit-${PRECOMMIT_VERSION}.pyz; \
	fi
	python3 pre-commit.pyz clean
	python3 pre-commit.pyz uninstall --hook-type pre-commit --hook-type pre-push --hook-type commit-msg
	python3 pre-commit.pyz gc
	python3 pre-commit.pyz install --hook-type pre-commit --hook-type pre-push --hook-type commit-msg

update-submodules:
	@echo "Updating submodules"
	git fetch origin
	git fetch --tags
	git pull origin main
	git submodule update --init --recursive
	@echo "All submodules updated"

# Define the target for running the decentralised miner
miner-decentralised:
	@if [ "$(network)" = "mainnet" ]; then \
		docker compose -f docker-compose.miner.yaml up -d --build miner-mainnet-decentralised; \
	elif [ "$(network)" = "testnet" ]; then \
		docker compose -f docker-compose.miner.yaml up -d --build miner-testnet-decentralised; \
	else \
		echo "Please specify a valid network: mainnet or testnet"; \
	fi

# Define the target for running the centralised miner
miner-centralised:
	@if [ "$(network)" = "mainnet" ]; then \
		docker compose -f docker-compose.miner.yaml up --build -d miner-mainnet-centralised; \
	elif [ "$(network)" = "testnet" ]; then \
		docker compose -f docker-compose.miner.yaml up --build -d miner-testnet-centralised; \
	else \
		echo "Please specify a valid network: mainnet or testnet"; \
	fi

# Define the target for running the validator
validator:
	@if [ "$(network)" = "mainnet" ]; then \
		docker compose -f docker-compose.validator.yaml up --build -d validator-mainnet; \
	elif [ "$(network)" = "testnet" ]; then \
		docker compose -f docker-compose.validator.yaml up --build -d validator-testnet; \
	else \
		echo "Please specify a valid network: mainnet or testnet"; \
	fi
