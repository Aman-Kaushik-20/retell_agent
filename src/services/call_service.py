from src.models.retell import CallObject, CallRequestModel, CallResponseModel
from src.providers.retell import RetellProvider
from src.utils.logger import logger


# Service for placing calls and fetching call status against Retell.
class CallService:
    def __init__(self, retell: RetellProvider) -> None:
        self.retell = retell

    async def initiate_call(self, call_params: CallRequestModel) -> CallResponseModel:
        logger.info(
            f"CallService.initiate_call | to={call_params.to_number} "
            f"override_agent_id={call_params.override_agent_id}"
        )
        return await self.retell.make_call(call_params)

    async def get_call(self, call_id: str) -> CallObject:
        logger.info(f"CallService.get_call | call_id={call_id}")
        return await self.retell.get_call(call_id)
