# SailCloth-01 · 帆布浸渍防水台

帆布间布卷与浸渍固化台账基线项目（Django 5 + DRF + Vue 3 SPA）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Django 5 · DRF · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端反代 `/api`） |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01`
- **前端**：http://localhost:3740
- **API**：http://localhost:8740
- **PostgreSQL**：localhost:6140

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。后端 entrypoint 执行 migrate + seed。

## 业务规则

布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。

规则实现：`backend/core/rules.py`

### 树脂累计一致性

- 每卷的**树脂累计** = 库内该卷各次浸渍 `resinPct` 的算术合计（数据库聚合，非前端估算）。
- 晾晒架挂签上的**累计角标**（`Σ n`）与 **`/resin` 树脂累计专页**的合计取自同一聚合：布卷接口的 `resinTotal` / `dipCount` 字段与 `GET /api/resin/` 返回的每卷合计永远相等；从无浸渍的卷合计为 `0`。
- 顺着晾晒架面板再登一笔浸渍后，角标与专页合计随下一次加载一起增加（两处均实时取自服务端，不存在单边缓存）。

### 浸渍登记并发（防交叉重复入库）

`POST /api/dips/` 接受可选字段 `expectedDipCount`（提交人看到的该卷当前浸渍笔数）。服务器在事务中锁定该布卷并核对实际笔数：

- 一致 → 正常入库（201）。
- 不一致 → 返回 **409**（响应含最新 `dipCount`），不入库。

因此两名浸胶工基于同一旧笔数交叉给同一卷登记两笔时，只有先到的一笔入库；另一笔收到 409，前端会刷新数据并提示，角标与专页仍只跟入库的这一笔对齐。前端晾晒架面板与浸渍台账表单都会自动携带 `expectedDipCount`。

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

- **登录** → 进入主工作面
- **完整顶栏**：晾晒架 `/`、树脂累计 `/resin`、布卷台账 `/rolls`、浸渍台账 `/dips`、退出登录
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`，右上角标 `Σ` 显示该卷树脂累计）；点击打开右侧面板登记 `DipRun`、切换固化状态；架下为浸渍流水次要信息流
- **`/resin` 树脂累计专页**：按帆布间与布卷筛选；每卷列出历史浸渍的树脂百分比明细并给出算术合计，合计与挂签角标一致
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD，顶栏降级为「台账」入口，非主路径

## API 契约

- 认证：SimpleJWT（`/api/auth/token/`、`/api/auth/token/refresh/`、`/api/auth/me/`）
- 资源：`/api/lofts/`、`/api/rolls/`（含只读 `resinTotal`、`dipCount`）、`/api/dips/`（创建支持 `expectedDipCount` 乐观并发，冲突返回 409）
- 聚合：`/api/dashboard/`、`/api/resin/`（支持 `?loftId=`、`?rollId=` 筛选，返回每卷浸渍明细与树脂算术合计）

## 本地跑后端测试

无需 Postgres（使用内存 SQLite）：

```bash
cd backend
python manage.py test --settings=config.test_settings
```

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
