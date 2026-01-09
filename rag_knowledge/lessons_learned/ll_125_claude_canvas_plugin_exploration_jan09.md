# Lesson Learned #125: Claude Canvas Plugin - Terminal UI for Personal Tasks

**Date**: January 9, 2026
**Category**: Tools & Plugins
**Source**: YouTube - "Claude Now Builds Custom Interfaces to Plan Your Life"
**URL**: https://youtu.be/jRBiWoSKpIo
**Author**: CEO of Glide Apps

## Summary

Claude Canvas is an open-source plugin for Claude Code that provides an "external display" within the terminal to handle personal tasks like previewing emails, booking flights, and scheduling meetings.

## Key Technical Details

### Architecture
- **Display**: Uses TMUX to create split-pane displays
- **Runtime**: Bun to execute CLI TypeScript files
- **UI Framework**: Ink (React-based library for CLIs)
- **Communication**: Interprocess Communication (IPC) for bidirectional data flow

### Installation Requirements
1. Must run Claude Code inside a TMUX session
2. Bun runtime required for TypeScript execution
3. Install as a Claude Code plugin

### Built-in Skills
1. **Flight** - Flight booking interface
2. **Document** - Document preview/editing
3. **Calendar** - Scheduling interface

### Usage
- Trigger with "spawn" keyword: "Preview it using canvas spawn"
- Arrow Keys: Navigate lists
- Tab: Switch between sections
- Spacebar: Confirm selection

### Extensibility
- Connect to MCP servers (Gmail, Google Calendar) for live data
- Community forks support: Ghosty, iTerm, Apple Terminal (no TMUX required)

## Potential Applications for Trading System

1. **Portfolio Dashboard**: Real-time portfolio visualization in terminal
2. **Trade Confirmation UI**: Interactive trade preview before execution
3. **Options Chain Display**: Visual options chain selection
4. **Alert Management**: Interactive alert configuration

## Action Items

- [ ] Evaluate if terminal UI would benefit trading workflow
- [ ] Check GitHub repo for implementation details
- [ ] Consider fork for trading-specific interfaces

## Tags
#claude-code #plugins #terminal-ui #ink #tmux #mcp #personal-assistant
