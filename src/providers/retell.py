import httpx

from src.config import settings
from src.models.retell import (
    CallObject,
    CallRequestModel,
    CallResponseModel,
    RetellErrorResponse,
)
from src.utils.logger import logger


# Best-effort decoding of Retell error bodies.
def _format_retell_error(response: httpx.Response) -> str:
    try:
        err = RetellErrorResponse.model_validate_json(response.text)
        return f"code={err.error_code} message={err.error_message}"
    except Exception:
        return f"body={response.text}"


# Provider Class for Retell AI - 2 main functions:
# 1. Place a phone call (POST /v2/create-phone-call)
# 2. Fetch a call's full execution record (GET /v2/get-call/{call_id})
class RetellProvider:
    def __init__(self) -> None:
        self.retell_url = settings.retell_base_url.rstrip("/")
        self.api_key = settings.retell_api_key
        self.default_from_number = settings.retell_from_number
        self.client = httpx.AsyncClient(
            base_url=self.retell_url,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )  # Initialize client up-front so per-request latency stays low

    async def close(self) -> None:
        await self.client.aclose()

    async def make_call(self, call_params: CallRequestModel) -> CallResponseModel:
        payload = call_params.model_dump(mode="json", exclude_none=True)
        # Retell requires from_number; fall back to the env default when caller omits it.
        if "from_number" not in payload:
            if not self.default_from_number:
                raise ValueError(
                    "from_number not provided and RETELL_FROM_NUMBER not set in environment"
                )
            payload["from_number"] = self.default_from_number

        logger.info(
            f"Initiating Retell call | override_agent_id={payload.get('override_agent_id')} "
            f"to={payload['to_number']} from={payload['from_number']}"
        )

        try:
            response = await self.client.post("/v2/create-phone-call", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Retell /v2/create-phone-call failed | to={payload.get('to_number')} "
                f"status={e.response.status_code} {_format_retell_error(e.response)}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(
                f"Retell /v2/create-phone-call transport error | to={payload.get('to_number')} error={e!r}"
            )
            raise

        data = response.json()
        logger.info(
            f"Retell call registered | call_id={data.get('call_id')} status={data.get('call_status')}"
        )
        return CallResponseModel.model_validate(data)

    async def get_call(self, call_id: str) -> CallObject:
        logger.info(f"Fetching Retell call | call_id={call_id}")

        try:
            response = await self.client.get(f"/v2/get-call/{call_id}")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Retell /v2/get-call failed | call_id={call_id} "
                f"status={e.response.status_code} {_format_retell_error(e.response)}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"Retell /v2/get-call transport error | call_id={call_id} error={e!r}")
            raise

        return CallObject.model_validate(response.json())
