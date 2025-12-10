# Claude Desktop MCP Setup Instructions

## What This Does

This MCP (Model Context Protocol) configuration enables Claude Desktop to:

1. **Trade via Alpaca**: Execute stock/options orders, manage positions, get market data via the Alpaca MCP server
2. **Read RSS Feeds**: Consume crypto newsletters (like CoinSnacks) and market analysis content

## Available MCP Servers

### 1. Alpaca Trading MCP Server (`@ideadesignmedia/alpaca-mcp`)

Full trading and market data access via Alpaca APIs:

**Trading Tools**:
- `alpaca.create_order` - Place stock/options orders
- `alpaca.list_positions` - View current positions
- `alpaca.get_position` - Get specific position details
- `alpaca.close_position` / `alpaca.close_all_positions` - Close positions
- `alpaca.list_orders` / `alpaca.get_order` - View order status
- `alpaca.cancel_order` / `alpaca.cancel_all_orders` - Cancel orders
- `alpaca.get_account` / `alpaca.account_overview` - Account info
- `alpaca.get_clock` / `alpaca.get_calendar` - Market hours
- `alpaca.get_portfolio_history` - Historical performance

**Market Data Tools**:
- `alpaca.data.stocks.latest_bar` / `alpaca.data.stocks.latest_quote` - Real-time prices
- `alpaca.data.stocks.bars` / `alpaca.data.stocks.quotes` - Historical data
- `alpaca.data.options.chain` / `alpaca.data.options.snapshots` - Options data
- `alpaca.data.news` - Market news
- `alpaca.get_stock_info` - Comprehensive stock summary

**Configuration**: Requires `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` environment variables.

### 2. RSS Feed MCP Server (`@veithly/rss-mcp`)

Read RSS feeds for crypto newsletters and market analysis.

### 3. Microsoft Learn MCP Server (HTTP-based)

Real-time access to official Microsoft documentation for .NET, Azure, C#, and more.

**Available Tools**:
- `microsoft_docs_search` - Semantic search across Microsoft Learn documentation
- `microsoft_docs_fetch` - Retrieve and convert documentation pages to markdown
- `microsoft_code_sample_search` - Find official code snippets with language filtering

**Key Benefits**:
- No API keys, logins, or sign-ups required - free service
- Real-time documentation access (always up-to-date)
- Only accesses official first-party Microsoft documentation
- Great for .NET, Azure, C#, ASP.NET Core, and other Microsoft technologies

**Configuration**: Uses HTTP transport (no local installation needed):
```json
"microsoft-learn": {
  "type": "http",
  "url": "https://learn.microsoft.com/api/mcp",
  "description": "Microsoft Learn MCP Server - Real-time access to official Microsoft documentation"
}
```

**Claude Code Installation** (alternative):
```bash
claude mcp add --transport http microsoft-learn https://learn.microsoft.com/api/mcp
```

## Installation Steps

### 1. Locate Your Claude Desktop Config File

**macOS**:
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows**:
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux**:
```bash
~/.config/Claude/claude_desktop_config.json
```

### 2. Copy MCP Configuration

#### Option A: Merge with Existing Config (Recommended)

If you already have a `claude_desktop_config.json` file:

1. Open your existing config file
2. Open `.claude/mcp_config.json` (in this repo)
3. Copy the `"rss"` section from `mcpServers`
4. Paste it into your existing `mcpServers` section

Example of merged config:
```json
{
  "mcpServers": {
    "your-existing-server": {
      ...
    },
    "alpaca": {
      "command": "npx",
      "args": ["-y", "@ideadesignmedia/alpaca-mcp", "--paper"],
      "description": "Alpaca Trading MCP Server - stocks, options, and market data",
      "env": {
        "ALPACA_KEY_ID": "${ALPACA_API_KEY}",
        "ALPACA_SECRET_KEY": "${ALPACA_SECRET_KEY}",
        "ALPACA_PAPER": "true"
      }
    },
    "rss": {
      "command": "npx",
      "args": ["-y", "@veithly/rss-mcp"],
      "description": "RSS feed reader for consuming crypto newsletters and market analysis",
      "env": {
        "RSS_FEEDS": "https://medium.com/feed/coinsnacks"
      }
    }
  }
}
```

**Important**: For live trading, remove `"--paper"` from args and set `"ALPACA_PAPER": "false"`.

#### Option B: Fresh Installation

If you DON'T have a config file yet:

1. Copy the entire `.claude/mcp_config.json` file to the location above
2. Rename it to `claude_desktop_config.json`

### 3. Restart Claude Desktop

**Important**: You MUST completely quit and restart Claude Desktop for MCP changes to take effect.

**macOS**:
- Cmd+Q to quit Claude Desktop (or right-click dock icon → Quit)
- Reopen Claude Desktop from Applications

**Windows**:
- Right-click Claude in system tray → Exit
- Reopen Claude Desktop from Start menu

**Linux**:
- Kill the Claude Desktop process
- Restart from your launcher

### 4. Verify Installation

After restarting Claude Desktop, open a new conversation and ask:

```
What MCP servers are available? Can you read RSS feeds?
```

If successful, Claude will confirm the RSS MCP server is available and list available tools.

## Testing RSS Feed Access

Once installed, you can test by asking:

```
Read the latest posts from the CoinSnacks Medium feed
```

or

```
What are the recent articles from CoinSnacks?
```

Claude will be able to fetch and summarize the RSS feed content directly.

## Adding More RSS Feeds

To add additional feeds, edit the `RSS_FEEDS` environment variable in your config:

```json
"env": {
  "RSS_FEEDS": "https://medium.com/feed/coinsnacks,https://example.com/feed.xml,https://another-feed.com/rss"
}
```

Multiple feeds should be comma-separated.

## Troubleshooting

### MCP Server Not Showing Up

1. **Check config location**: Ensure the file is in the correct directory
2. **Check JSON syntax**: Use a JSON validator (like jsonlint.com) to verify no syntax errors
3. **Check permissions**: Ensure the config file is readable
4. **Restart again**: Sometimes requires a second restart
5. **Check Claude Desktop logs**:
   - macOS: `~/Library/Logs/Claude/`
   - Windows: `%APPDATA%\Claude\logs\`
   - Linux: `~/.config/Claude/logs/`

### npx Command Fails

Ensure Node.js is installed:
```bash
node --version
npm --version
```

If not installed, download from: https://nodejs.org/

### RSS Feed Not Loading

- Check the feed URL is valid (test in browser)
- Ensure Medium feed is accessible (not behind paywall)
- Try running manually: `npx -y @veithly/rss-mcp`

## Package Information

### Alpaca Trading MCP Server
**Package**: `@ideadesignmedia/alpaca-mcp`
**npm**: https://www.npmjs.com/package/@ideadesignmedia/alpaca-mcp
**Features**: Trading v2 API, Market Data for stocks & options, news, corporate actions
**License**: MIT

### RSS Feed MCP Server
**Package**: `@veithly/rss-mcp`
**Repository**: https://github.com/veithly/rss-mcp
**License**: MIT

## Security Notes

- MCP servers run locally on your machine
- RSS feeds are fetched directly from the source
- No data is sent to third parties (beyond Claude's normal API usage)
- All feed data is processed within Claude Desktop context

## Benefits for Trading System

Once configured, you can:

### Alpaca Trading Benefits
1. **Execute Trades**: Place stock/options orders directly from Claude conversations
2. **Portfolio Management**: View positions, account balances, and P/L in real-time
3. **Market Data**: Get real-time quotes, historical bars, and options chains
4. **News Integration**: Access market news alongside trading decisions
5. **Account Overview**: Quick snapshot of account, open orders, and positions

### RSS Feed Benefits
1. **Daily Newsletter Digest**: Ask Claude to summarize today's CoinSnacks newsletter
2. **Market Sentiment Analysis**: Extract key themes and sentiment from recent posts
3. **Integration with Research**: Use newsletter insights during trading research phase
4. **Automated Monitoring**: Schedule daily checks of new content (via Claude conversations)

### Microsoft Learn Benefits
1. **Up-to-date Documentation**: Access latest .NET, Azure, and C# docs during development
2. **Code Samples**: Find official code snippets for implementing trading features
3. **No Hallucination Risk**: AI responses backed by trusted Microsoft documentation
4. **Zero Configuration**: Free service with no API keys or authentication required

## Next Steps

After installation, consider:

1. Adding more crypto/finance RSS feeds (Decrypt, CoinDesk, The Block, etc.)
2. Creating a daily routine to review newsletters with Claude
3. Integrating newsletter insights into your trading research workflow
4. Building a custom skill to automate newsletter summarization

## Support

If you encounter issues:

1. Check Claude Desktop documentation: https://docs.anthropic.com/
2. Check MCP specification: https://spec.modelcontextprotocol.io/
3. Review `@veithly/rss-mcp` package issues: https://github.com/veithly/rss-mcp/issues
4. Ask Claude for help troubleshooting in a conversation
