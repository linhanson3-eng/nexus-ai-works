# Vendored Dependencies

## claw-code-agent

- **来源**: [HarnessLab/claw-code-agent](https://github.com/HarnessLab/claw-code-agent)
- **许可证**: MIT
- **版权**: Copyright (c) 2024-2025 HarnessLab
- **策略**: 零修改 vendor。所有适配通过 `factory/engine/bridge.py` 完成，这是项目中唯一允许导入 vendor 代码的模块。
- **更新**: 手动替换 `claw_code_agent/` 目录内容后运行全量测试 (`python3 -m pytest factory/ gateway/ -v`) 确认无回归。

## 关于 Nexus AI Works 的许可说明

Nexus AI Works 整体采用 MIT 许可证（见仓库根目录 `LICENSE` 文件）。

`factory/vendor/` 目录下的第三方代码保留其原始许可证和版权声明。本项目不主张对这些代码的版权。
