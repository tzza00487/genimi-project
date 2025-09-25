# 資料庫遷移專案計畫

## 專案目標
將 MariaDB 資料庫 `tc_search_v15` 的內容遷移到 PostgreSQL 資料庫，並使用 Docker 容器化環境和 FastAPI 進行資料對接。

## 第一階段：系統性分析 (已完成)

### 1.1 環境與檔案分析
*   **專案根目錄:** `C:\gemini-project`
*   **資料庫配置檔案:** 
    *   `C:\gemini-project\vibecoding\mariadb\docker-compose.yml` (已移除，內容已整合)
    *   `C:\gemini-project\vibecoding\postgres\docker-compose.yml` (已移除，內容已整合)
    *   `C:\gemini-project\vibecoding\fastapi\docker-compose.yml` (已移除，內容已整合)
*   **整合後的 Docker Compose 檔案:** `C:\gemini-project\vibecoding\docker-compose.yml`
*   **FastAPI 應用程式檔案:** 
    *   `C:\gemini-project\vibecoding\fastapi\app\main.py`
    *   `C:\gemini-project\vibecoding\fastapi\requirements.txt`
    *   `C:\gemini-project\vibecoding\fastapi\Dockerfile`

### 1.2 MariaDB 資料結構分析
*   **資料庫名稱:** `tc_search_v15`
*   **主要資料表及其行數:** 
    *   `admin`: 23 行
    *   `album`: 8 行
    *   `api_keys`: 3 行
    *   `api_logs`: 81251 行 (大型資料表)
    *   `apply_meta`: 2043 行
    *   `apply_meta_assets`: 17624 行
    *   `asset`: 1940805 行 (非常大型資料表)
    *   `asset_file`: 3788638 行 (非常大型資料表)
    *   `asset_keywords`: 4448539 行 (非常大型資料表)
    *   `asset_logs`: 487523 行 (大型資料表)
    *   `attachment`: 0 行 (空資料表)
    *   `errata`: 182 行
    *   `feedback`: 62 行
    *   `hot_keyword`: 0 行 (空資料表)
    *   `log_api_called`: 0 行 (空資料表)
*   **觀察:** 存在多個大型資料表，需要考慮分塊遷移策略。

### 1.3 PostgreSQL 資料結構分析
*   **初始狀態:** 空資料庫，無現有資料表。

## 第二階段：深度分析 (已完成)

### 2.1 資料遷移策略評估
*   **選擇:** 使用 FastAPI 作為 ETL 編排器。
*   **原因:** 滿足使用者要求，靈活處理資料轉換，適合分塊遷移大型資料集。

### 2.2 FastAPI 整合設計
*   **FastAPI 應用程式:** `main.py` 包含連接 MariaDB 和 PostgreSQL 的函數，以及用於觸發結構和資料遷移的 API 端點。
*   **資料類型映射:** 已實作 MariaDB 到 PostgreSQL 的基本資料類型映射。
*   **分塊遷移:** 資料遷移端點支援分塊讀取和寫入，以處理大型資料表。

### 2.3 Docker 配置評估與修訂
*   **整合式 Docker Compose:** 所有服務 (MariaDB, PostgreSQL, FastAPI) 已整合到 `C:\gemini-project\vibecoding\docker-compose.yml` 單一檔案中。
*   **網路配置:** 所有服務都在 `migration_network` 內部網路中通訊。
*   **服務名稱:** 
    *   MariaDB 服務名稱: `mariadb`
    *   PostgreSQL 服務名稱: `postgresql`
    *   FastAPI 服務名稱: `fastapi_app`
*   **容器名稱:** 
    *   MariaDB 容器名稱: `mariadb-container`
    *   PostgreSQL 容器名稱: `postgresql-container`
    *   FastAPI 容器名稱: `fastapi-migration-app`
*   **FastAPI 應用程式更新:** `main.py` 中的資料庫連線主機已更新為服務名稱 (`mariadb`, `postgresql`)。

## 第三階段：全面性修復計畫制定 (進行中)

### 3.1 逐步遷移計畫

1.  **啟動整合後的 Docker 環境:** 
    *   **操作:** 導航到 `C:\gemini-project\vibecoding` 目錄。
    *   **命令:** 執行 `docker compose up -d --build`。
    *   **預期結果:** `mariadb-container`, `postgresql-container`, `fastapi-migration-app` 容器將會啟動並運行。

2.  **存取 FastAPI 應用程式:** 
    *   **URL:** `http://localhost:8000`
    *   **驗證:** 瀏覽器訪問此 URL，應看到 `{"message": "FastAPI Migration App is running!"}`。

3.  **觸發結構遷移:** 
    *   **目的:** 在 PostgreSQL 中建立 `tc_search_v15` 資料庫和所有資料表結構。
    *   **URL:** `http://localhost:8000/migrate_schema`
    *   **預期結果:** FastAPI 應用程式將連接到 MariaDB，讀取所有資料表結構，並在 PostgreSQL 中建立對應的資料庫和資料表。API 回應將包含每個資料表的結構遷移摘要。

4.  **觸發資料遷移 (可選：單一資料表或所有資料表):** 
    *   **目的:** 將 MariaDB 中的資料遷移到 PostgreSQL 中對應的資料表。
    *   **遷移單一資料表:** 
        *   **URL:** `http://localhost:8000/migrate_data/{table_name}` (將 `{table_name}` 替換為實際資料表名稱，例如 `admin`, `api_logs`, `asset` 等)。
        *   **預期結果:** API 將分塊遷移指定資料表的資料，並返回遷移的行數。
    *   **遷移所有資料表:** 
        *   **URL:** `http://localhost:8000/migrate_all_data`
        *   **預期結果:** API 將依序觸發所有資料表的資料遷移，並返回每個資料表的遷移摘要。

5.  **在 PostgreSQL 中驗證資料:** 
    *   **連接方式:** 使用 `psql` 命令列工具或任何 PostgreSQL GUI 工具 (例如 DBeaver, pgAdmin) 連接到 `localhost:5432`，使用者 `postgres`，密碼 `tc94800552`，資料庫 `tc_search_v15`。
    *   **驗證步驟:** 
        *   確認 `tc_search_v15` 資料庫已存在。
        *   列出所有資料表，確認與 MariaDB 中的資料表數量和名稱一致。
        *   對於每個資料表，比較行數是否與 MariaDB 中的原始行數一致。
        *   隨機查詢一些資料表，檢查資料內容是否正確遷移，特別是資料類型轉換是否正確。

### 3.2 驗證和測試策略

1.  **結構驗證:** 
    *   在執行 `/migrate_schema` 後，手動連接到 PostgreSQL，並使用 `\d {table_name}` (在 psql 中) 或 GUI 工具檢查每個資料表的欄位、資料類型、主鍵和索引是否與 MariaDB 一致。
    *   特別注意 `map_mariadb_to_postgres_type` 函數的轉換結果。

2.  **資料計數驗證:** 
    *   在執行資料遷移後，對於每個資料表，執行 `SELECT COUNT(*) FROM {table_name};` 並與 MariaDB 中的計數進行比較。

3.  **範例資料驗證:** 
    *   對於每個資料表，執行 `SELECT * FROM {table_name} LIMIT 10;` 並手動檢查資料內容，特別是日期、布林值和特殊字元。

4.  **錯誤處理監控:** 
    *   在 Docker Compose 啟動後，使用 `docker logs fastapi-migration-app` 命令監控 FastAPI 容器的日誌輸出，查看是否有任何錯誤訊息。
    *   API 端點的回應將提供遷移狀態和任何錯誤的詳細資訊。

### 3.3 文件記錄
*   本計畫的內容將儲存為 `C:\gemini-project\db_migration_plan.md`。
