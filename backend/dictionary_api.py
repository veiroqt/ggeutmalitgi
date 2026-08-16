"""국립국어원 표준국어대사전 Open API 연동.

API 키는 https://opendict.korean.go.kr 에서 무료로 발급받아
환경변수 KOREAN_DICT_API_KEY 로 설정한다.
"""

import json
import os

import httpx

API_URL = "https://stdict.korean.go.kr/api/search.do"
_TIMEOUT = 5.0

# 같은 게임 서버 프로세스 내에서 반복 조회를 줄이기 위한 단순 캐시.
# word -> {"valid": bool, "definition": str | None}
_cache: dict[str, dict] = {}


class DictionaryAPIError(Exception):
    """사전 API 요청 자체가 실패했을 때 (네트워크 오류, 키 누락 등)."""


async def _lookup(word: str) -> dict:
    if word in _cache:
        return _cache[word]

    api_key = os.environ.get("KOREAN_DICT_API_KEY")
    if not api_key:
        raise DictionaryAPIError(
            "사전 API 키가 설정되지 않았습니다. opendict.korean.go.kr에서 키를 발급받아 "
            "KOREAN_DICT_API_KEY 환경변수에 설정해주세요."
        )

    params = {"key": api_key, "q": word, "req_type": "json"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
            body = response.text.strip()
    except httpx.HTTPError as exc:
        raise DictionaryAPIError("사전 API 요청 중 오류가 발생했습니다.") from exc

    if not body:
        # 검색 결과가 없을 때 API가 빈 응답 본문을 돌려주는 경우가 있다.
        result = {"valid": False, "definition": None}
        _cache[word] = result
        return result

    try:
        data = json.loads(body)
    except ValueError as exc:
        raise DictionaryAPIError("사전 API 응답을 해석할 수 없습니다.") from exc

    channel = data.get("channel", {})
    error = data.get("error")
    if error:
        raise DictionaryAPIError(f"사전 API 오류: {error.get('message', '알 수 없는 오류')}")

    items = channel.get("item", [])
    if isinstance(items, dict):
        items = [items]

    # 합성어는 형태소 경계를 붙임표(-)로 표시해 내려온다 (예: 자동차 -> "자동-차").
    matches = [item for item in items if item.get("word", "").replace("-", "") == word]

    definition = None
    if matches:
        definition = matches[0].get("sense", {}).get("definition")

    result = {"valid": bool(matches), "definition": definition}
    _cache[word] = result
    return result


async def is_valid_word(word: str) -> bool:
    """단어가 표준국어대사전에 존재하는지 확인한다.

    Raises:
        DictionaryAPIError: API 요청이 실패하거나 키가 설정되지 않은 경우.
    """
    result = await _lookup(word)
    return result["valid"]


def get_cached_definition(word: str) -> str | None:
    """is_valid_word() 호출로 캐시된 단어의 뜻을 반환한다 (없으면 None)."""
    entry = _cache.get(word)
    return entry["definition"] if entry else None
