"""
The LLM part is orchestrated thanks to the LiteLLM package
that creates a common interface for every LLM model that the user chooses.
"""

from abc import ABC, abstractmethod
import os
import time

from agent_core.schemas import StepMetrics
from litellm.router import Router
import litellm
from litellm.types.utils import ModelResponse
from litellm.utils import CustomStreamWrapper


class LLMError(Exception):
    pass


class AbstractLLM(ABC):
    """
    Interface for all LLMs.
    """

    @abstractmethod
    def get_response(self, step: int, messages: list[dict]) -> StepMetrics:
        """
        This function returns the response from the LLM as a StepMetrics
        object. All LLM needs this function.
        """
        pass


class LLM(AbstractLLM):
    """
    Class used for LLM Inference
    """

    def __init__(
        self, model_name: str, provider_url: str | None = None
    ) -> None:
        """
        Initializes the LLM.
        """
        # Initialize basic informations
        if "/" not in model_name:
            raise LLMError(
                f"Invalid model name {model_name!r}: expected "
                f"'provider/model' format (e.g. 'openai/gpt-4')."
            )
        self.__model_name = model_name
        self.__provider = model_name.split("/")[0]
        self.__provider_url = provider_url
        self.__api_keys = self._get_keys_for_provider(self.__provider)

        # Raise exception if no keys were found
        if len(self.__api_keys) == 0:
            raise LLMError("Could not parse the API keys for the given model.")

        # Setup completion router for multiple API keys
        self._setup_router()

    def _setup_router(self) -> None:
        """
        Setup the LLM's router for using multiple keys.
        """
        # Create a model_list for the router to be based on
        model_list = []
        for api_key in self.__api_keys:
            litellm_params = {
                "model": self.__model_name,
                "api_key": api_key,
            }
            if self.__provider_url is not None:
                litellm_params["api_base"] = self.__provider_url
            model_list.append(
                {
                    "model_name": self.__model_name.split("/")[1],
                    "litellm_params": litellm_params,
                }
            )

        # Create the router
        self.__router = Router(
            model_list=model_list,
            routing_strategy="usage-based-routing",
            allowed_fails=len(model_list),
            cooldown_time=5,
        )

        # One id per key, captured once here. get_response() dispatches
        # retries directly by id (Router.has_model_id() short-circuits
        # straight to that exact deployment, bypassing cooldown/health/
        # usage-based selection entirely) instead of letting the Router
        # auto-pick a deployment on each retry — verified empirically
        # that auto-picking can retry an already-failed key more than
        # once before its cooldown is actually in effect (a race between
        # the failure callback and the very next call), sometimes never
        # reaching a working key within the retry budget. Dispatching by
        # id can't repeat a key already tried within the same call.
        self.__deployment_ids = [
            d["model_info"]["id"] for d in self.__router.model_list
        ]
        # Rotates which key each *new* get_response() call starts on, so
        # successful calls still spread load across the pool round-robin
        # instead of always hammering the same first key (dispatching by
        # id has no usage-based balancing of its own, unlike the auto-pick
        # this replaces).
        self.__next_deployment_index = 0

        return None

    def _get_keys_for_provider(self, provider: str) -> list[str]:
        """
        Search all the API keys for a given provider in the env variables.
        """
        provider_upper = provider.upper()
        possible_vars = [
            f"{provider_upper}_API_KEY",
            f"{provider_upper}_API_KEYS",
        ]

        # Check all possible vars
        found_keys: list[str] = []
        for var_name in possible_vars:
            val = os.getenv(var_name, "")
            if val:
                # Split the variable content with ','
                keys = val.split(",")
                for key in keys:
                    # Save key
                    found_keys.append(key)

        return list(set(found_keys))

    def get_response(self, step: int, messages: list[dict]) -> StepMetrics:
        """Return the response from the LLM as a StepMetrics object.

        Tries each configured key once, in a round-robin order that
        starts on a different key each call (see _setup_router), before
        raising LLMError — a failing key can never be retried twice in
        the same call while another, untried key sits skipped.

        Args:
            step (int): Current step
            messages (list[dict]): Full conversation so far, OpenAI-style
                (e.g. [{"role": "system", "content": ...}, ...])
        """
        # Query to the LLM to answer the prompt
        start_time = time.time_ns()
        start = self.__next_deployment_index
        n = len(self.__deployment_ids)
        self.__next_deployment_index = (start + 1) % n
        order = self.__deployment_ids[start:] + self.__deployment_ids[:start]

        last_error: Exception | None = None
        retries = 0
        llm_gen: ModelResponse | CustomStreamWrapper | None = None
        for deployment_id in order:
            try:
                llm_gen = self.__router.completion(
                    model=deployment_id,
                    messages=messages,
                    stream=False,
                )
                break
            except Exception as e:
                last_error = e
                retries += 1

        if llm_gen is None:
            raise LLMError(
                f"LLM call failed for model {self.__model_name!r} after "
                f"{n} attempt(s) across {len(self.__api_keys)} key(s): "
                f"{last_error}"
            ) from last_error
        end_time = time.time_ns()

        # stream=False guarantees a ModelResponse at runtime, but the
        # return type is still `ModelResponse | CustomStreamWrapper` —
        # make that explicit instead of assuming it silently.
        if not isinstance(llm_gen, ModelResponse):
            raise LLMError(
                f"Expected a ModelResponse (stream=False), got "
                f"{type(llm_gen).__name__}"
            )

        # litellm's own source shows `usage` can be None even when
        # stream=False (not just a stub gap — a real runtime case), and
        # not every free-tier provider reports it. getattr() also sidesteps
        # a stub gap where ModelResponse doesn't statically declare
        # `.usage` even though it's set dynamically at construction.
        usage = getattr(llm_gen, "usage", None)
        input_tokens = usage.prompt_tokens if usage is not None else 0
        output_tokens = usage.completion_tokens if usage is not None else 0

        # Build StepMetrics output from the LLM's result
        llm_metrics = StepMetrics(
            step=step,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            usage_reported=usage is not None,
            request_time_ms=(end_time - start_time) / 1_000_000,
            api_url=llm_gen._hidden_params.get("api_base") or "",
            model_name=self.__model_name,
            llm_output=llm_gen.choices[0].message.content or "",
            # sandbox_input/sandbox_output/retries are unknown at this
            # point (no code has been executed yet) and are left to their
            # StepMetrics defaults; the caller (agent_core.loop) fills
            # them in once the sandbox has actually run.
        )

        return llm_metrics


if __name__ == "__main__":
    llm = LLM("deepseek/deepseek-v4-flash")
    print(
        llm.get_response(
            1,
            [
                {
                    "role": "system",
                    "content": "Write a short poem about keroberos68",
                }
            ],
        )
    )
