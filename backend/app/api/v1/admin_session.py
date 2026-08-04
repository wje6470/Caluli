"""管理端身分確認（spec FR-010～FR-017）。

★ 權限檢查掛在 router 建構參數，不掛在端點函式簽章
====================================================
    APIRouter(..., dependencies=[Depends(require_admin)])

這樣掛的理由是：**新增端點時不可能忘記加權限**。若改成逐支端點寫
`admin: AdminUser` 參數，漏寫一支就是一個完全敞開的管理端點，而這種疏漏
在 review 時極易滑過。憲章「架構約束」也明令不得在各端點內重複手寫判斷
邏輯。

第一輪已建好 require_admin()（core/deps.py），本輪**不修改它**，直接使用。

★ 這支端點存在的理由（research.md R-11）
========================================
前端後台守衛需要判斷「目前使用者是不是管理員」。兩種做法：

  a. 在既有的 /me 回應加 role 欄位
  b. 呼叫一支受保護的端點，看它通不通過   ← 採用

選 b 的理由有二：
  1. FR-043 要求不改動第一輪既有 API；在 UserOut 加欄位會動到既有契約，
     且會讓每位一般使用者的 /me 都帶著角色資訊，沒必要擴大暴露面。
  2. 更重要的是——用「呼叫受保護端點」來判斷權限，與後端實際的授權判斷
     走的是**同一條路徑**。若前端改讀 /me 的 role 自行判斷，就出現了第二
     套判斷邏輯，兩者可能不一致。

這支同時也是整個管理端 router 群組的健康檢查：它通過即代表權限層掛載正確。
"""

from fastapi import APIRouter, Depends

from app.core.deps import AdminUser, require_admin
from app.schemas.admin import AdminSessionOut

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    # ★ 整個 router 的每一支端點都會先經過這道檢查。
    dependencies=[Depends(require_admin)],
)


@router.get("/me", response_model=AdminSessionOut)
def get_admin_session(admin: AdminUser) -> AdminSessionOut:
    """確認目前登入者具備管理員身分。

    非管理員根本到不了這裡（router 層的依賴已擋下），故回應中的 role
    必然為 'admin'。

    刻意**不回傳任何 LINE 憑證或管理員名單資訊**——前端只需要知道
    「你是管理員」這一件事。
    """
    return AdminSessionOut(user_id=admin.id, display_name=admin.display_name, role="admin")
