// Agents and tools that install with a single shell command, offered by the
// install menu in the terminal header. The command is typed into the shell of
// the sandbox, so it runs as the user there and needs curl or npm in the image.

const NEEDS_NODE = 'Needs Node.js (install "Node.js" first).'

export const TOOLS = [
  // Coding agents
  { name: 'Claude Code', group: 'Agents', keywords: 'claude anthropic', description: 'Anthropic\'s coding agent', command: 'curl -fsSL https://claude.ai/install.sh | bash' },
  { name: 'Codex CLI', group: 'Agents', keywords: 'codex-cli openai', description: `OpenAI's coding agent. ${NEEDS_NODE}`, command: 'npm install -g @openai/codex' },
  { name: 'Gemini CLI', group: 'Agents', keywords: 'gemini-cli google', description: `Google's coding agent. ${NEEDS_NODE}`, command: 'npm install -g @google/gemini-cli' },
  { name: 'Pi', group: 'Agents', keywords: 'pi-coding-agent', description: `Minimal coding agent. ${NEEDS_NODE}`, command: 'npm install -g @mariozechner/pi-coding-agent' },
  { name: 'OpenCode', group: 'Agents', keywords: 'opencode sst', description: 'Open source coding agent', command: 'curl -fsSL https://opencode.ai/install | bash' },
  { name: 'Cursor CLI', group: 'Agents', keywords: 'cursor-agent', description: 'Cursor\'s coding agent', command: 'curl -fsSL https://cursor.com/install | bash' },
  { name: 'Amp', group: 'Agents', keywords: 'amp sourcegraph ampcode', description: 'Sourcegraph\'s coding agent', command: 'curl -fsSL https://ampcode.com/install.sh | bash' },
  { name: 'GitHub Copilot CLI', group: 'Agents', keywords: 'copilot github', description: `GitHub's coding agent. ${NEEDS_NODE}`, command: 'npm install -g @github/copilot' },
  { name: 'Qwen Code', group: 'Agents', keywords: 'qwen-code alibaba', description: `Qwen's coding agent. ${NEEDS_NODE}`, command: 'npm install -g @qwen-code/qwen-code' },
  { name: 'Crush', group: 'Agents', keywords: 'crush charm', description: `Charm's coding agent. ${NEEDS_NODE}`, command: 'npm install -g @charmland/crush' },
  { name: 'Goose', group: 'Agents', keywords: 'goose block', description: 'Block\'s open source agent', command: 'curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | CONFIGURE=false bash' },
  { name: 'Aider', group: 'Agents', keywords: 'aider aider-chat', description: 'AI pair programming in the terminal', command: 'curl -LsSf https://aider.chat/install.sh | sh' },
  { name: 'Factory Droid', group: 'Agents', keywords: 'droid factory', description: 'Factory\'s coding agent', command: 'curl -fsSL https://app.factory.ai/cli | sh' },
  // Languages and package managers
  { name: 'uv', group: 'Tools', keywords: 'python astral pip', description: 'Python package and project manager', command: 'curl -LsSf https://astral.sh/uv/install.sh | sh' },
  { name: 'Node.js', group: 'Tools', keywords: 'node npm nvm javascript', description: 'Latest LTS via nvm', command: 'curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash && . "$HOME/.nvm/nvm.sh" && nvm install --lts' },
  { name: 'Bun', group: 'Tools', keywords: 'bun javascript', description: 'JavaScript runtime and package manager', command: 'curl -fsSL https://bun.sh/install | bash' },
  { name: 'Deno', group: 'Tools', keywords: 'deno javascript typescript', description: 'JavaScript and TypeScript runtime', command: 'curl -fsSL https://deno.land/install.sh | sh -s -- -y' },
  { name: 'pnpm', group: 'Tools', keywords: 'pnpm javascript', description: 'JavaScript package manager', command: 'curl -fsSL https://get.pnpm.io/install.sh | sh -' },
  { name: 'Rust', group: 'Tools', keywords: 'rustup cargo', description: 'Rust toolchain via rustup', command: 'curl --proto \'=https\' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y' },
  { name: 'Ruff', group: 'Tools', keywords: 'ruff python lint astral', description: 'Python linter and formatter', command: 'curl -LsSf https://astral.sh/ruff/install.sh | sh' },
  { name: 'Pixi', group: 'Tools', keywords: 'pixi conda prefix', description: 'Conda package manager', command: 'curl -fsSL https://pixi.sh/install.sh | sh' },
  { name: 'mise', group: 'Tools', keywords: 'mise rtx asdf', description: 'Version manager for many languages', command: 'curl -fsSL https://mise.run | sh' },
  { name: 'SDKMAN!', group: 'Tools', keywords: 'sdkman java kotlin gradle', description: 'Version manager for Java and the JVM', command: 'curl -s "https://get.sdkman.io" | bash' },
  { name: 'Homebrew', group: 'Tools', keywords: 'brew homebrew linuxbrew', description: 'Package manager', command: 'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"' },
  // Other
  { name: 'Ollama', group: 'Other', keywords: 'ollama llm local models', description: 'Run language models locally', command: 'curl -fsSL https://ollama.com/install.sh | sh' },
  { name: 'Docker', group: 'Other', keywords: 'docker container', description: 'Container engine', command: 'curl -fsSL https://get.docker.com | sh' },
  { name: 'Tailscale', group: 'Other', keywords: 'tailscale vpn', description: 'Private network', command: 'curl -fsSL https://tailscale.com/install.sh | sh' },
  { name: 'zoxide', group: 'Other', keywords: 'zoxide cd', description: 'Smarter cd', command: 'curl -sSfL https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh | sh' },
  { name: 'Atuin', group: 'Other', keywords: 'atuin history shell', description: 'Searchable shell history', command: 'curl --proto \'=https\' --tlsv1.2 -LsSf https://setup.atuin.sh | sh' },
  { name: 'Starship', group: 'Other', keywords: 'starship prompt', description: 'Shell prompt', command: 'curl -sS https://starship.rs/install.sh | sh -s -- -y' },
]

/** Whether `tool` matches every word of `query` in its name, keywords or description. */
export function matchesTool(tool, query) {
  const text = `${tool.name} ${tool.keywords} ${tool.description}`.toLowerCase()
  return (query ?? '').toLowerCase().split(/\s+/).every(word => text.includes(word))
}
