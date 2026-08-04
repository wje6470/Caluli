# Specification Quality Checklist: 推薦餐廳（第二輪）

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-04
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- **已解決（2026-08-04）**：FR-020「附近」的距離範圍上限，經使用者決定為 **5 公里，超出者排除**。已回填至 FR-019／FR-020、US1 驗收情境 2-5、Edge Cases、FR-034 測試資料要求、SC-002 與 Assumptions（直線距離認定、固定值不動態放寬）。無 [NEEDS CLARIFICATION] 標記殘留。

- **共用契約同步（2026-08-04 第三輪交接）**：依交接說明更新 FR-016（地址為分店辨識依據）、新增 FR-016a（以 id 識別，名稱不唯一）、FR-018（無座標為常態資料，排除於排序但出現於全部清單）、新增 FR-018a（不得加軟刪除過濾）、FR-025（0 與缺值雙向區分）、FR-028（`menu_items` 補時間戳），以及 Edge Cases 與 Assumptions 對應段落。
  契約檔案已於 2026-08-04 同步（`menu_items` 時間戳已加入）。檔案僅載明欄位名稱，其餘語意約定以交接說明為準。
  仍未定案且需在任一方建表前確認：主鍵型別（OQ-1）、營養欄位是否允許 NULL（OQ-2b，為 FR-025 前半段的前提）。
- 資料表欄位維持共用契約原文（`stores` / `menu_items` 及其欄位名）屬跨分支合併契約，非實作細節，故保留於 FR-028。
- 「僅 LIFF 提供」的實作層級（UI 層限制、後端不分岔端點）已依專案憲章 III 與架構約束記於 Assumptions，未列為待釐清項。
- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
