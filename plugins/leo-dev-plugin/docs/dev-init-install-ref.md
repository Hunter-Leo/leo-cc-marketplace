# dev-init: 工具安装参考

本文件提供 `/dev-init` 命令中涉及的所有工具的官方安装方式。

## CLI 工具

### uv (Python 包管理器)

```bash
# macOS (Homebrew)
brew install uv

# Linux / WSL
curl -LsSf https://astral.sh/uv/install.sh | sh

# 验证
uv --version
```

### nvm (Node.js 版本管理器)

```bash
# 安装
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

# 加载到 shell (安装脚本通常自动写入 .zshrc)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# 安装 Node.js LTS
nvm install --lts

# 验证
nvm --version
node --version
```

### bun (JS 运行时)

```bash
# macOS / Linux
curl -fsSL https://bun.sh/install | bash

# 或通过 npm
npm install -g bun

# 验证
bun --version
```

### gh (GitHub CLI)

```bash
# macOS
brew install gh

# Linux (Debian/Ubuntu)
(type -p wget >/dev/null || sudo apt install wget -y) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && sudo apt update \
  && sudo apt install gh -y

# 验证
gh --version
```

## Plugins (Claude Code 插件市场)

### oh-my-claudecode (OMC 多代理编排)

方式一：插件市场安装（推荐）
```text
/plugin marketplace add https://github.com/Yeachan-Heo/oh-my-claudecode
```
然后在插件界面选择 oh-my-claudecode 进行安装。

方式二：CLI 安装
```text
/plugin install oh-my-claudecode@omc
```

### superpowers (工作流技能框架)

官方市场：`claude-plugins-official`

```text
/plugin install superpowers@claude-plugins-official
```

### skill-creator (技能创建工具)

官方市场：`claude-plugins-official`

```text
/plugin install skill-creator@claude-plugins-official
```

### pyright-lsp (Python LSP)

官方市场：`claude-plugins-official`
需要系统已安装 `pyright` 或 `pyright-langserver` 二进制。

```text
/plugin install pyright-lsp@claude-plugins-official
```

前置依赖：
```bash
# 通过 npm 安装 pyright
npm install -g pyright

# 或通过 pip
pip install pyright
```

## Skills (独立的 Agent 技能)

### deli-autoresearch (自主调研框架)

当前已安装在 `~/.claude/skills/deli-autoresearch/`。

如果缺失，安装方式：

方式一：插件市场安装
```text
/plugin marketplace add nanawanzii/deli-autoresearch-skill-protocol
/plugin install deli-autoresearch@deli-autoresearch
```

方式二：npx skills 安装
```text
npx skills add ziwangprincex/deli-autoresearch-skill-protocol --skill deli-autoresearch -g -a claude-code
```

### colab-session-operator (Google Colab 环境操作)

```text
npx skills add https://github.com/googlecolab/google-colab-cli --skill colab-session-operator -g -a claude-code
```

## MCP Servers

### context7 (SDK 文档查询)

方式一：通过 npm 全局安装
```bash
npm install -g @anthropic-ai/claude-code-addon-context7
```

然后在 `settings.json` 中配置：
```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/claude-code-addon-context7"]
    }
  }
}
```

方式二：在项目中直接运行
```bash
npx -y @anthropic-ai/claude-code-addon-context7
```

### anysearch (搜索工具)

anysearch 需要依据其官方文档配置。通常在 Claude Code 环境中已自动注入。
检查 `~/.claude/settings.json` 或项目 `.claude/settings.json` 中是否存在对应 MCP server 配置。

如果缺失，参考 anysearch 官方文档进行配置安装。

## CLAUDE.md 基线内容

非 OMC 部分的 CLAUDE.md 基线内容包括：
1. Coding Guidelines（编码指南）
2. RTK.md（Rust Token Killer 引用）

CLAUDE.md 中 OMC 区块（`<!-- OMC:START -->...<!-- OMC:END -->`）由 OMC 插件自身管理，不在此命令的操作范围内。
