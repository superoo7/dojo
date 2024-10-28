## Validating

> **Note:** To connect to testnet, uncomment the testnet related configuration, specifically `NETUID`, `SUBTENSOR_CHAIN_ENDPOINT` and `SUBTENSOR_NETWORK`

Copy the validator .env file and set up the .env file

```bash
# copy .env.validator.example
cp .env.validator.example .env.validator

# edit the .env file with vim, vi or nano

WALLET_COLDKEY=# the name of the coldkey
WALLET_HOTKEY=# the name of the hotkey

# head to https://wandb.ai/authorize to get your API key
WANDB_API_KEY="<wandb_key>"

# for dojo-synthetic-api
OPENROUTER_API_KEY="sk-or-v1-<KEY>"

# for langfuse, the free tier is more than enough
LANGFUSE_SECRET_KEY=# head to langfuse.com
LANGFUSE_PUBLIC_KEY=# head to langfuse.com
LANGFUSE_HOST="https://us.cloud.langfuse.com" # 🇺🇸 US region

# Other LLM API providers, Optional or if you've chosen it over Openrouter
TOGETHER_API_KEY=
OPENAI_API_KEY=

# postgres details for validator
DB_HOST=postgres-vali:5432
DB_NAME=db
DB_USERNAME=#set a non-default username
DB_PASSWORD=#generate and set a secure password
DATABASE_URL=postgresql://${DB_USERNAME}:${DB_PASSWORD}@${DB_HOST}/${DB_NAME}
```

> **Note:** To ensure your validator runs smoothly, enable the auto top-up feature for Openrouter, this ensures that your validator will not fail to call synthetic API during task generation. The estimate cost of generating a task is approximately $0.20 USD.

Start the validator

```bash
# To start the validator:
make validator
```

To start with autoupdate for validators (**strongly recommended**), see the [Auto-updater](#auto-updater) section.