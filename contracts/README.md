# contracts/ — Mnesis 跨仓契约单一真值目录

> **本目录是 Mnesis 所有跨仓接口契约的权威来源（单一真值）。**
> 各仓下的镜像文件（如 Daedalus `docs/integration/XR_ROBOT_CONTRACT.md`）为**只读复制**，改契约只在本仓改。

## 规则

1. **改契约只在本仓**：任何跨仓接口的契约变更，先在本目录修改、版本号升级，再通知消费方同步。
2. **各仓镜像只读**：其他仓库中存放的契约副本是只读镜像，修改时通过 PR 指向本仓的更新。
3. **`contracts.lock` 防篡改**：每份契约文件的 SHA-256 校验和记录在 `contracts.lock` 中，CI 自动校验——篡改任一契约文件即 CI 失败。
4. **契约登记簿**：跨仓关系总览见 [`CONTRACTS.md`](../CONTRACTS.md)（本仓根目录）。

## 文件清单

| 文件 | 对应契约 | 说明 |
|---|---|---|
| `XR_ROBOT_CONTRACT.md` | C3 — xr_bridge WS | VR↔机器人实时遥操作契约（帧协议/急停/重连/看门狗） |
| `xr_bridge_SPEC.md` | C3 附属 | xr_bridge WebSocket 消息 SPEC 摘要（消息类型/载荷/时序） |
| `canonical_frame_schema_REFERENCE.md` | C1 — Canonical Frame Schema | 指回本仓 `mnesis_canonical/canonical_frame.schema.json` 的引用说明 |
| `README.md` | — | 本文件（目录说明） |

## 校验

```bash
# 从项目根目录运行
python -m mnesis_canonical.contracts_check

# 输出示例
# contracts/XR_ROBOT_CONTRACT.md  ... OK
# contracts/xr_bridge_SPEC.md     ... OK
# contracts/contracts.lock        ... OK
# All contracts pass integrity check.
```

篡改任一契约文件后运行该校验将非零退出并报告具体文件。

## 相关

- 跨仓契约登记簿：`CONTRACTS.md`（根目录）
- 本仓数据标准 SPEC：`SPEC.md`（根目录）
- 参考实现：`mnesis_canonical/`