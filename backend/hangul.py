"""두음법칙(頭音法則) 처리.

끝말잇기에서는 앞 단어의 마지막 글자가 한자어의 첫음절 위치에 오면 소리가 바뀌는
두음법칙을 인정한다 (예: "쾌락" -> "낙원", "인력" -> "역도").

- ㄹ + (아/애/오/외/우/으) -> ㄴ + 동일 모음  (라/래/로/뢰/루/르 -> 나/내/노/뇌/누/느)
- ㄹ + (야/얘/여/예/요/유/의/이) -> ㅇ + 동일 모음  (랴/례/료/류/리 등 -> 야/예/요/유/이 등)
- ㄴ + (야/얘/여/예/요/유/의/이) -> ㅇ + 동일 모음  (냐/녀/뇨/뉴/니 등 -> 야/여/요/유/이 등)
"""

CHO_N = 2  # ㄴ
CHO_R = 5  # ㄹ
CHO_IEUNG = 11  # ㅇ

# 종성 없이(홀소리로 끝나지 않는 것과 무관) 모음에 따라 분류.
_GROUP_A_JUNG = {0, 1, 8, 11, 13, 18}  # 아 애 오 외 우 으
_GROUP_B_JUNG = {2, 3, 6, 7, 12, 17, 19, 20}  # 야 얘 여 예 요 유 의 이


def _decompose(ch: str):
    code = ord(ch) - 0xAC00
    if code < 0 or code > 11171:
        return None
    cho = code // (21 * 28)
    jung = (code % (21 * 28)) // 28
    jong = code % 28
    return cho, jung, jong


def _compose(cho: int, jung: int, jong: int) -> str:
    return chr(cho * 21 * 28 + jung * 28 + jong + 0xAC00)


def dueum_form(ch: str) -> str | None:
    """두음법칙을 적용했을 때의 글자를 반환한다. 적용 대상이 아니면 None."""
    decomposed = _decompose(ch)
    if decomposed is None:
        return None
    cho, jung, jong = decomposed

    new_cho = None
    if cho == CHO_R:
        if jung in _GROUP_A_JUNG:
            new_cho = CHO_N
        elif jung in _GROUP_B_JUNG:
            new_cho = CHO_IEUNG
    elif cho == CHO_N:
        if jung in _GROUP_B_JUNG:
            new_cho = CHO_IEUNG

    if new_cho is None:
        return None
    return _compose(new_cho, jung, jong)


def chain_start_options(last_char: str) -> set[str]:
    """앞 단어의 마지막 글자 뒤에 올 수 있는 다음 단어의 첫 글자 후보 (원음 + 두음법칙 적용음)."""
    options = {last_char}
    transformed = dueum_form(last_char)
    if transformed:
        options.add(transformed)
    return options
