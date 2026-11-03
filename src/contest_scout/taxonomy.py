"""분야 태그 정규화.

소스마다 분야 표기가 다르다. 씽굿은 ``contest_field_nm`` 에 "영상/UCC" 처럼 적고,
링커리어는 카테고리를 아예 안 주는 경우도 있다. UI 필터가 소스별 표기에 끌려가지
않도록, 제목·분야·키워드에서 **공통 태그**를 뽑아낸다.

점수 계산과 분리돼 있다는 점이 중요하다. 여기서 하는 일은 분류일 뿐이고,
가중치 판단은 :mod:`contest_scout.evaluators` 몫이다.
"""

from __future__ import annotations

from contest_scout.models import Contest

#: (표시 이름, 매칭 토큰). 위에서부터 검사하며, 겹쳐도 모두 붙인다.
TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("AI", ("ai", "인공지능", "생성형", "chatgpt", "머신러닝", "딥러닝", "genai")),
    ("영상", ("영상", "비디오", "video", "ucc", "필름", "영화", "다큐", "모션", "애니메이션")),
    ("숏폼", ("숏폼", "쇼츠", "shorts", "릴스", "reels", "틱톡", "tiktok", "short-form")),
    ("광고", ("광고", "cf", "advertis", "카피", "공익광고")),
    ("마케팅", ("마케팅", "marketing", "홍보", "프로모션", "캠페인")),
    ("브랜딩", ("브랜드", "브랜딩", "brand", "네이밍", "슬로건", "ci", "bi")),
    ("디자인", ("디자인", "design", "그래픽", "패키지", "편집디자인", "일러스트")),
    ("포스터", ("포스터", "poster", "웹툰", "카드뉴스", "인포그래픽")),
    ("캐릭터·굿즈", ("캐릭터", "굿즈", "이모티콘", "마스코트")),
    ("사진", ("사진", "포토", "photo")),
    ("기획·아이디어", ("기획", "아이디어", "제안", "정책제안", "아이디어톤")),
    ("문학", ("문학", "수기", "백일장", "독후감", "수필", "소설", "시화", "글짓기")),
    ("논문·학술", ("논문", "학술", "리서치", "연구")),
    ("개발·SW", ("소프트웨어", "코딩", "알고리즘", "프로그래밍", "앱 개발", "해커톤", "데이터 분석")),
    ("건축·공간", ("건축", "도시설계", "조경", "공간디자인", "인테리어")),
    ("창업", ("창업", "스타트업", "비즈니스모델", "사업화")),
]

FALLBACK_TAG = "기타"

#: Discover 화면에서 기본으로 보여줄 순서.
DISPLAY_ORDER = [name for name, _ in TAG_RULES] + [FALLBACK_TAG]


def tags_for(contest: Contest) -> list[str]:
    """제목·분야·키워드만 본다. 본문까지 뒤지면 주제어에 오염된다."""
    haystack = contest.topic_haystack()
    tags = [name for name, tokens in TAG_RULES if any(t in haystack for t in tokens)]
    return tags or [FALLBACK_TAG]


__all__ = ["DISPLAY_ORDER", "FALLBACK_TAG", "TAG_RULES", "tags_for"]
