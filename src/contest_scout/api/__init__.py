"""HTTP API 레이어.

여기에는 **수집 로직이 없다**. 전부 :mod:`contest_scout.services` 와
:mod:`contest_scout.repository` 를 호출할 뿐이다. API를 걷어내도 CLI는 그대로
동작한다.
"""

from contest_scout.api.app import create_app

__all__ = ["create_app"]
