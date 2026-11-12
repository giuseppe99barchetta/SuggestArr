"""An empty or refused LLM answer is an invalid answer, not a crash; a silent provider cannot hold a job for ten minutes."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_service.services.llm import llm_service
from api_service.services.llm.llm_service import LLMValidationError, _call_with_validation
from api_service.services.llm.schemas import RecommendationList

VALID = json.dumps({'recommendations': [{'title': 'Dune', 'year': 2021, 'rationale': 'r', 'source_title': None}]})


def answer(content):
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


def client_returning(*responses):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=list(responses))
    return client


async def call(client):
    return await _call_with_validation(client=client, model='m', messages=[{'role': 'user', 'content': 'x'}],
                                       schema_cls=RecommendationList, max_retries=1)


@pytest.mark.asyncio
async def test_an_empty_answer_is_retried_and_the_next_one_is_used():
    client = client_returning(answer(None), answer(VALID))
    result = await call(client)
    assert result.recommendations[0].title == 'Dune'
    assert client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('empty', [answer(None), answer(''), MagicMock(choices=[])])
async def test_answers_that_stay_empty_end_as_a_validation_error(empty):
    with pytest.raises(LLMValidationError):
        await call(client_returning(empty, empty))


def test_the_client_gives_up_on_a_silent_provider():
    with patch.object(llm_service.ConfigService, 'get_runtime_config', return_value={'OPENAI_API_KEY': 'k'}):
        client = llm_service.get_llm_client()
    assert client.timeout == llm_service._LLM_TIMEOUT_SECONDS == 120
