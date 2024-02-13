# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 Opentensor Foundation

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

from enum import StrEnum
import os
from pathlib import Path
import torch
import argparse
import bittensor as bt
from loguru import logger

from commons.custom_exceptions import InvalidNeuronType, UnspecifiedNeuronType
from commons.reward_model.models import ModelZoo


class ScoringMethod(StrEnum):
    HF_MODEL = "hf_model"
    LLM_API = "llm_api"
    HUMAN_FEEDBACK = "human_feedback"


def check_config(config: bt.config):
    """Checks/validates the config namespace object."""
    bt.logging.check_config(config)

    full_path = os.path.expanduser(
        "{}/{}/{}/netuid{}/{}".format(
            config.logging.logging_dir,  # TODO: change from ~/.bittensor/miners to ~/.bittensor/neurons
            config.wallet.name,
            config.wallet.hotkey,
            config.netuid,
            config.neuron.name,
        )
    )
    config.neuron.full_path = os.path.expanduser(full_path)
    if not os.path.exists(config.neuron.full_path):
        os.makedirs(config.neuron.full_path, exist_ok=True)


def add_args(parser):
    """
    Adds relevant arguments to the parser for operation.
    """
    # Netuid Arg: The netuid of the subnet to connect to.
    parser.add_argument("--netuid", type=int, help="Subnet netuid", default=1)

    parser.add_argument(
        "--neuron.type",
        choices=["miner", "validator"],
        type=str,
        help="Whether running a miner or validator",
    )
    args, unknown = parser.parse_known_args()
    neuron_type = None
    if known_args := vars(args):
        # if "neuron.type" not in known_args:
        #     raise UnspecifiedNeuronType("neuron.type not specified during runtime")
        # if known_args["neuron.type"] not in ["miner", "validator"]:
        #     raise InvalidNeuronType(
        #         f"neuron.type must be either 'miner' or 'validator', got {known_args['neuron.type']}"
        #     )
        neuron_type = known_args["neuron.type"]

    print("neuron_type:", neuron_type)

    parser.add_argument(
        "--neuron.name",
        type=str,
        help="Trials for this neuron go in neuron.root / (wallet_cold - wallet_hot) / neuron.name. ",
        default=neuron_type,
    )

    parser.add_argument(
        "--neuron.device",
        type=str,
        help="Device to run on.",
        default="cpu",
    )

    parser.add_argument(
        "--neuron.epoch_length",
        type=int,
        help="The default epoch length (how often we set weights, measured in 12 second blocks).",
        default=100,
    )

    parser.add_argument(
        "--neuron.events_retention_size",
        type=str,
        help="Events retention size.",
        default="2 GB",
    )

    if neuron_type == "validator":
        parser.add_argument(
            "--data_manager.base_path",
            type=str,
            help="Base path to store data to.",
            default=Path.cwd(),
        )
        parser.add_argument(
            "--neuron.num_concurrent_forwards",
            type=int,
            help="The number of concurrent forwards running at any time.",
            default=1,
        )

        parser.add_argument(
            "--neuron.sample_size",
            type=int,
            help="The number of miners to query in a single step.",
            default=10,
        )

        parser.add_argument(
            "--neuron.disable_set_weights",
            action="store_true",
            help="Disables setting weights.",
            default=False,
        )

        parser.add_argument(
            "--neuron.moving_average_alpha",
            type=float,
            help="Moving average alpha parameter, how much to add of the new observation.",
            default=0.05,
        )

        parser.add_argument(
            "--neuron.axon_off",
            "--axon_off",
            action="store_true",
            # Note: the validator needs to serve an Axon with their IP or they may
            #   be blacklisted by the firewall of serving peers on the network.
            help="Set this flag to not attempt to serve an Axon.",
            default=False,
        )

        parser.add_argument(
            "--neuron.vpermit_tao_limit",
            type=int,
            help="The maximum number of TAO allowed to query a validator with a vpermit.",
            default=4096,
        )

        parser.add_argument(
            "--dendrite_timeout",
            type=int,
            help="Timeout for dendrite queries.",
            default=60,
        )

    elif neuron_type == "miner":
        parser.add_argument(
            "--scoring_method",
            help="Method to use for scoring completions.",
            choices=[str(method) for method in ScoringMethod],
        )
        parser.add_argument(
            "--blacklist.force_validator_permit",
            action="store_true",
            help="If set, we will force incoming requests to have a permit.",
            default=True,
        )

        parser.add_argument(
            "--blacklist.allow_non_registered",
            action="store_true",
            help="If set, miners will accept queries from non registered entities. (Dangerous!)",
            default=False,
        )
        parser.add_argument(
            "--reward_model",
            type=str,
            help="Name of the reward model from huggingface to use",
            default=ModelZoo.DEBERTA_V3_LARGE_V2,
        )


# singleton instance
_config = None


def get_config():
    """Returns the configuration object specific to this miner or validator after adding relevant arguments.
    Manage a global config instance to allow re-using in other parts of our code.
    """
    global _config
    if _config is not None:
        return _config
    parser = argparse.ArgumentParser()
    bt.wallet.add_args(parser)
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    bt.axon.add_args(parser)
    add_args(parser)
    _config = bt.config(parser)
    return _config
