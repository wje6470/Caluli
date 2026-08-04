"""管理端存取控制（tasks.md T011）。

★ 憲章原則 IV（NON-NEGOTIABLE）明列的必測情境
==============================================
「一般使用者存取管理端 API 被拒絕」。

第一輪已在 tests/unit/test_deps.py 測過 require_admin() 本身，但那證明的是
**函式邏輯正確**，不是**每一支端點都掛上了它**。本檔以真實 HTTP 請求逐一
驗證每支管理端端點，才是對「router 層統一掛載」（research.md R-02）是否
確實生效的檢查。

刻意獨立成檔（不併入 CRUD 測試），以便單獨執行與驗收：

    pytest tests/integration/test_admin_access_control.py -v

★ 本檔刻意**不依賴資料庫**
==========================
權限判斷只讀 user.role，不需要真實資料。若讓這些斷言依賴 testcontainers，
在沒有 Docker 的機器上它們會**靜默 skip**——憲章明列的必測情境變成沒測，
而測試結果仍是綠的。這正是最該避免的失敗模式，故此處以 stub session 取代
真實連線，讓它在任何環境都會實際執行。

需要驗證「被拒的寫入請求沒有副作用」時才需要真資料庫，那部分於 US2 加入
寫入端點後另行處理（見檔尾）。

★ 新增管理端端點時，必須把它加進下方的 ADMIN_ENDPOINTS
=======================================================
test_endpoint_registry_covers_every_mounted_admin_route() 會自動比對本清單
與 FastAPI 實際註冊的路由；漏加會讓該測試失敗。這道自動比對的存在，是為了
讓「忘記為新端點驗證權限」變成不可能，而不是仰賴開發者記得。
"""

import re
import uuid

import httpx
import pytest

from app.core.security import create_access_token
from app.db.models import ROLE_ADMIN, ROLE_USER, User
from app.db.session import get_db
from app.main import app

# 目前已實作的管理端端點。US2／US3／US4 每新增一支就必須補進來。
# 路徑參數一律寫成 {id}，實際請求時代入隨機 UUID——權限檢查發生在查資料
# 之前，故不存在的 id 仍應回 403 而非 404（若回 404，代表權限檢查掛在資料
# 查詢之後，等同向未授權者洩漏了「這筆資料不存在」）。
ADMIN_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/v1/admin/me"),
    # US2 店家維護
    ("GET", "/api/v1/admin/stores"),
    ("POST", "/api/v1/admin/stores"),
    ("GET", "/api/v1/admin/stores/{id}"),
    ("PATCH", "/api/v1/admin/stores/{id}"),
    ("DELETE", "/api/v1/admin/stores/{id}"),
]

GENERAL_SUB = "U11111111111111111111111111111111"
ADMIN_SUB = "U22222222222222222222222222222222"


def _make_user(line_sub: str, role: str) -> User:
    """在記憶體中建立使用者，不寫入資料庫。

    權限層只讀 role，不需要持久化。
    """
    user = User()
    user.id = uuid.uuid4()
    user.line_user_id = line_sub
    user.display_name = "測試使用者"
    user.role = role
    return user


class _StubSession:
    """只支援 db.get(User, pk) 的最小替身。

    get_current_user() 僅以此查出使用者；提供替身即可讓整條權限鏈在無
    資料庫的環境下完整執行。
    """

    def __init__(self, user: User | None):
        self._user = user

    def get(self, _model, pk):
        if self._user is not None and self._user.id == pk:
            return self._user
        return None


def _client_for(user: User | None) -> httpx.AsyncClient:
    app.dependency_overrides[get_db] = lambda: _StubSession(user)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def general_user() -> User:
    """一般使用者——持有**合法**登入狀態，這正是憲章要防的情境。"""
    return _make_user(GENERAL_SUB, ROLE_USER)


@pytest.fixture
def admin_user() -> User:
    return _make_user(ADMIN_SUB, ROLE_ADMIN)


def _resolve(path: str) -> str:
    return path.replace("{id}", str(uuid.uuid4()))


def _token_for(user: User) -> str:
    token, _ = create_access_token(user.id)
    return token


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
async def test_general_user_is_forbidden_on_every_admin_endpoint(general_user, method, path):
    """FR-014：持有效一般使用者登入狀態者，對任一管理端端點皆被拒。"""
    async with _client_for(general_user) as ac:
        response = await ac.request(
            method, _resolve(path), headers={"Authorization": f"Bearer {_token_for(general_user)}"}
        )

    assert response.status_code == 403, f"{method} {path} 未拒絕一般使用者"
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_forbidden_responses_are_byte_identical_across_endpoints(general_user):
    """FR-015：拒絕回應彼此完全一致，無法藉差異推測哪些功能存在。

    這是「不洩漏後台結構」唯一可自動化的驗證方式。任何為個別端點客製化
    錯誤訊息的做法（例如「您無權編輯店家」）都會讓這項失敗。
    """
    bodies: set[str] = set()
    statuses: set[int] = set()

    async with _client_for(general_user) as ac:
        for method, path in ADMIN_ENDPOINTS:
            response = await ac.request(
                method,
                _resolve(path),
                headers={"Authorization": f"Bearer {_token_for(general_user)}"},
            )
            bodies.add(response.text)
            statuses.add(response.status_code)

    assert statuses == {403}
    assert len(bodies) == 1, f"拒絕回應不一致，可藉差異推測端點存在：{bodies}"

    body = next(iter(bodies)).lower()
    # 回應不得帶任何可推知後台功能的字眼。
    for leaked in ("store", "店家", "menu", "餐點", "admin", "管理"):
        assert leaked not in body, f"拒絕回應洩漏了後台線索：{leaked}"


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
async def test_unauthenticated_request_returns_401_not_403(method, path):
    """FR-016：未登入者得到 401 而非 403。

    若未登入也回 403，等於告訴未驗證的來源「這裡有需要權限的東西」。
    """
    async with _client_for(None) as ac:
        response = await ac.request(method, _resolve(path))

    assert response.status_code == 401, f"{method} {path} 對未登入者回了 {response.status_code}"
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
async def test_invalid_token_returns_401(method, path, general_user):
    """偽造或過期的 token 不得通過。"""
    async with _client_for(general_user) as ac:
        response = await ac.request(
            method, _resolve(path), headers={"Authorization": "Bearer not-a-real-token"}
        )

    assert response.status_code == 401


async def test_token_carries_no_role_so_it_cannot_be_forged(general_user):
    """權限一律即時查資料庫，token 內不含 role，故無 role 可竄改。

    若哪天有人為了省一次查詢而把 role 塞進 token，這項會失敗——那是個
    看似無害、實則把授權決策交給客戶端持有物的改動。
    """
    import jwt

    from app.core.config import get_settings

    settings = get_settings()
    payload = jwt.decode(
        _token_for(general_user), settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )

    assert set(payload) == {"sub", "iat", "exp"}
    assert "role" not in payload
    assert "admin" not in str(payload).lower()


async def test_admin_passes_the_same_permission_layer(admin_user):
    """對照組：同一層對管理員必須放行。

    少了這項，上面的斷言全綠也可能只是因為「全部都擋掉」。
    """
    async with _client_for(admin_user) as ac:
        response = await ac.get(
            "/api/v1/admin/me", headers={"Authorization": f"Bearer {_token_for(admin_user)}"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == ROLE_ADMIN
    assert body["user_id"] == str(admin_user.id)
    # 回應不得夾帶 LINE 憑證或名單資訊（research R-11）。
    assert "line_user_id" not in body
    assert set(body) == {"user_id", "display_name", "role"}


async def test_role_change_takes_effect_without_reissuing_token(general_user):
    """FR-013：角色被撤銷後，既有 token 立即失去管理端存取能力。

    權限以後端當下的角色資料為準，不是以簽發 token 當下的狀態為準。
    """
    token = _token_for(general_user)

    general_user.role = ROLE_ADMIN
    async with _client_for(general_user) as ac:
        promoted = await ac.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {token}"})
    assert promoted.status_code == 200

    # 營運方撤銷其管理員身分；token 沒有重新簽發。
    general_user.role = ROLE_USER
    async with _client_for(general_user) as ac:
        revoked = await ac.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {token}"})
    assert revoked.status_code == 403, "撤銷後既有 token 仍可存取管理端"


def _normalize(path: str) -> str:
    """把所有路徑參數統一成 {id}，讓宣告與實際註冊的路由可直接比對。"""
    return re.sub(r"\{[^}]+\}", "{id}", path)


def test_endpoint_registry_covers_every_mounted_admin_route():
    """★ 防止「新增管理端端點卻忘了驗證權限」。

    比對 ADMIN_ENDPOINTS 與 FastAPI 實際註冊的 /api/v1/admin 路由。
    漏加會讓本測試失敗，而不是讓一支未受驗證的端點默默上線。
    """
    # 以 OpenAPI schema 列舉，而非走 app.routes：本版 FastAPI 的 app.routes
    # 存的是 _IncludedRouter 惰性包裝，並未攤平成 APIRoute，直接迭代會得到
    # 空集合而讓這道防線靜默失效。openapi() 的 paths 才是攤平且穩定的來源。
    mounted = {
        (method.upper(), _normalize(path))
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/v1/admin")
        for method in operations
        if method.upper() not in {"HEAD", "OPTIONS"}
    }
    declared = {(method, _normalize(path)) for method, path in ADMIN_ENDPOINTS}

    assert not (mounted - declared), (
        f"以下管理端端點未列入 ADMIN_ENDPOINTS，其權限未被驗證："
        f"{sorted(mounted - declared)}。請補進本檔頂端的清單。"
    )
    assert not (declared - mounted), (
        f"ADMIN_ENDPOINTS 列了不存在的端點（會使權限測試失去意義）：{sorted(declared - mounted)}"
    )


# ─────────────────────────────────────────────────────────────────────────
# US2／US3 加入寫入端點後補上（需要真實資料庫）：
#   FR-014 的「被拒的寫入請求不得造成任何資料變更」。
#   屆時以 db_session fixture 撰寫，放在 test_admin_stores.py，
#   因為它驗證的是資料副作用而非權限判斷本身。
# ─────────────────────────────────────────────────────────────────────────
