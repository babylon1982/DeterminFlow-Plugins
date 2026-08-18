# 笔枢公益模型 Plugin

这是一个面向 DeterminFlow Windows 桌面版的可选 Plugin，用于登录笔枢公益模型服务、
获取可用模型与额度状态，并把服务凭据注册为普通 Provider（供应商）。未安装或未启用时，
DeterminFlow Core 不加载公益模型逻辑。

## 开源边界

- 本目录只包含桌面客户端 Plugin：登录跳转、凭据申请与续签、动态模型目录、额度状态、
  独立公告、当前余额档位和 Core Provider API 适配。
- 账号、额度核算、服务治理和模型转发由独立服务端承担，其实现、部署配置与密钥不在本仓库。
- Plugin 只调用 Core 的稳定 HTTP API，不导入 Core 的模型管理内部实现。
- 登录在系统默认浏览器中完成，Plugin 不收集账号密码；本地只保存受限的桌面会话，
  状态文件不重复保存模型 Key。
- 模型、价格、额度和充值入口均由服务端动态返回；安装 Plugin 不代表服务或额度已开放。
- 公益模型公告由独立公告接口下发，并与长期服务风险说明分区；页面只以纯文本展示标题和正文，
  不渲染 HTML。
- 登录用户按当前充值余额显示免费或充值模型组；余额用尽立即回到免费模型组，历史充值
  不会永久保留充值模型权限。
- 当前正式服务只面向 Windows 桌面客户端，其他运行环境默认保持禁用。

## 安装

在 DeterminFlow 的官方 Plugin Catalog 中安装 `public-api`，启用后按界面提示重启 Core。
Plugin 页面提供服务状态、模型目录、登录、续签和退出操作。

## 本地开发

非 Windows 环境只允许通过显式开发开关测试客户端逻辑：

```bash
DETERMINFLOW_PUBLIC_API_DEVELOPMENT=1 .venv/bin/uvicorn src.web_server:app \
  --host 127.0.0.1 --port 8020
```

该开关仅绕过客户端平台门禁，并允许 loopback（本机回环）HTTP 地址；不会启用或替代
任何正式服务。正式构建和部署不得设置该变量。
