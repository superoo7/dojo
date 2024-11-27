import asyncio

from bittensor.btlogging import logging as logger

from commons.objects import ObjectManager
from dojo.utils.config import source_dotenv

source_dotenv()


async def main():
    miner = ObjectManager.get_miner()
    log_task = asyncio.create_task(miner.log_miner_status())
    run_task = asyncio.create_task(miner.run())

    await asyncio.gather(log_task, run_task)
    logger.info("Exiting main function.")


if __name__ == "__main__":
    asyncio.run(main())

"""
python main_miner.py --netuid 1 --subtensor.network ws://13.213.1.80:9944 --wallet.name ck_26nov --wallet.hotkey hk_26nov --logging.debug --axon.port 9005 --neuron.type miner --env_file .env.miner --ignore_min_stake
"""