"""
The LLM part is orchestrated thanks to the LiteLLM package
that creates a common interface for every LLM model that the user chooses.
"""

from abc import ABC, abstractmethod
import os
import time

from agent_core.schemas import StepMetrics
from litellm.router import Router


class LLMError(Exception):
    pass


class AbstractLLM(ABC):
    """
    Interface for all LLMs.
    """

    @abstractmethod
    def get_response(self, step: int, prompt: str) -> StepMetrics:
        """
        This function returns the response from the LLM as a StepMetrics
        object. All LLM needs this function.
        """
        pass


class LLM(AbstractLLM):
    """
    Class used for LLM Inference
    """

    def __init__(self, model_name: str) -> None:
        """
        Initializes the LLM.
        """
        # Initialize basic informations
        self.__model_name = model_name
        self.__provider = model_name.split("/")[0]
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
            model_list.append(
                {
                    "model_name": self.__model_name.split("/")[1],
                    "litellm_params": {
                        "model": self.__model_name,
                        "api_key": api_key,
                    },
                }
            )

        # Create the router
        self.__router = Router(
            model_list=model_list,
            routing_strategy="usage-based-routing",
            allowed_fails=2,
            cooldown_time=5,
        )

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

    def get_response(self, step: int, prompt: str) -> StepMetrics:
        """Return the response from the LLM as a StepMetrics object.

        Args:
            step (int): Current step
        """
        # Query to the LLM to answer the prompt
        start_time = time.time_ns()
        llm_gen = self.__router.completion(
            model=self.__model_name,
            messages=[{"role": "system", "content": prompt}],
            stream=False,
        )
        end_time = time.time_ns()

        # Build StepMetrics output from the LLM's result
        llm_metrics = StepMetrics(
            step=step,
            input_tokens=llm_gen.usage.prompt_tokens,
            output_tokens=llm_gen.usage.completion_tokens,
            request_time_ms=(end_time - start_time) / 1000,
            api_url=llm_gen._hidden_params["api_base"],
            model_name=self.__model_name,
            llm_output=llm_gen.choices[0].message.content,
            # Implementation needed here !
            sandbox_input="NOT IMPLEMENTED",
            sandbox_output="NOT IMPLEMENTED",
            retries=9999999999,
        )

        return llm_metrics


if __name__ == "__main__":
    llm = LLM("deepseek/deepseek-v4-flash")
    print(llm.get_response(1, "Write a short poem about keroberos68"))
