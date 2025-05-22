# Discord Summarizer Bot

A Discord bot that uses Claude AI to summarize channel messages.

## Features
- 🤖 AI-powered summaries using Claude 3.5 Sonnet
- 📊 Multiple summary styles (comprehensive, brief, bullet, participants)
- 🎯 Channel-specific summaries
- ⏰ Flexible time ranges
- 🔒 Secure environment variable configuration

## Commands
- `!summarize [hours] [limit] [style]` - Summarize current channel
- `!summarize_channel <channel> [hours] [limit] [style]` - Summarize specific channel
- `!help_summarizer` - Show help and available commands

## Summary Styles
- **comprehensive** - Detailed analysis with topics, decisions, and sentiment
- **brief** - Concise overview under 200 words
- **bullet** - Organized bullet point format
- **participants** - Focus on participant activity and engagement

## Setup
1. Create Discord Application and Bot at https://discord.com/developers/applications
2. Get Anthropic API key from https://console.anthropic.com/settings/keys
3. Deploy to Railway with environment variables:
   - `ANTHROPIC_API_KEY` - Your Anthropic API key
   - `DISCORD_BOT_TOKEN` - Your Discord bot token

## Permissions Required
- Read Messages/View Channels
- Send Messages
- Read Message History
- Message Content Intent (in Discord Developer Portal)

## Example Usage
```
!summarize
!summarize 12 50 brief
!summarize_channel general 6 100 bullet
!summarize 24 100 participants
```

Powered by Claude AI 🧠