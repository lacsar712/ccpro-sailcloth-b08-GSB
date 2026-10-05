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

树脂累计口径：每卷累计 = 库内该卷各次 `resinPct` 算术相加（`RESIN_TOTAL` 注解，见 `backend/core/views.py`）；晾晒架挂签角标与 `/resin` 专页合计共用此口径，无浸渍的卷显示算出的 0。

浸渍登记幂等：同一卷同一 `startedAt` 只入库一笔（唯一约束 `uniq_dip_roll_started`）；两名浸胶工交叉提交同一浸渍事件时，后到的一笔命中已有记录并原样返回（HTTP 200），角标与专页合计只跟这一笔对齐。

## SPA 信息架构

- **登录** → 进入主工作面
- **完整顶栏**：`/` 晾晒架 · `/resin` 树脂累计 · 台账（`/rolls`、`/dips`）· 退出
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`，角标显示该卷树脂累计）；点击打开右侧面板登记 `DipRun`、切换固化状态；架下为浸渍流水次要信息流
- **`/resin` 树脂累计专页**：列出每卷历史浸渍的树脂百分比并给出算术合计，可按帆布间与布卷筛选；合计与挂签角标同口径
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD

API：JWT、`/api/lofts|rolls|dips|dashboard|resin/`。

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
