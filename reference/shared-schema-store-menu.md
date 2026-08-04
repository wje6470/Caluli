【店家/餐點資料表 — 第二輪與第三輪共用契約，兩邊都以此為準，不得自行更改欄位】

stores 表：
- id
- name（店家名稱）
- address（地址）
- latitude, longitude（經緯度）
- created_at, updated_at

menu_items 表：
- id
- store_id（外鍵，關聯 stores）
- name（餐點名稱）
- calories
- protein_g
- carbs_g
- fat_g
- created_at, updated_at