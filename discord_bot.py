import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import os
from typing import List
import anthropic
from anthropic import AsyncAnthropic

# Create bot with minimal required intents
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Claude
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

class MessageSummarizer:
    def __init__(self, anthropic_api_key: str = None):
        """Initialize the summarizer with Anthropic Claude"""
        self.anthropic_api_key = anthropic_api_key
        # Use synchronous client only to avoid httpx compatibility issues
        self.client = anthropic.Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None
    
    async def summarize_messages(self, messages: List[str], channel_name: str, summary_style: str = "comprehensive") -> str:
        """Summarize a list of messages using Claude"""
        if not messages:
            return "No messages to summarize."
        
        # If no API key, fall back to simple summary
        if not self.client:
            return self._create_simple_summary(messages, channel_name)
        
        # Combine messages into a single text
        combined_text = "\n".join(messages)
        
        # Create appropriate prompt based on summary style
        prompt = f"""Please provide a comprehensive summary of these Discord messages from #{channel_name}. 

Include:
- Main topics discussed
- Key decisions or conclusions
- Important announcements or updates
- Notable questions and answers
- Overall tone and sentiment of the conversation

Messages:
{combined_text}

Please format your response clearly with appropriate sections."""
        
        try:
            # Call Claude API
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            summary = response.content[0].text
            
            # Add metadata header
            header = f"🤖 **Claude Summary of #{channel_name}**\n"
            header += f"📊 {len(messages)} messages analyzed\n"
            header += f"⏰ Generated at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            
            return header + summary
            
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return f"❌ **Error generating AI summary**: {str(e)}\n\n" + \
                   self._create_simple_summary(messages, channel_name)
    
    def _create_simple_summary(self, messages: List[str], channel_name: str) -> str:
        """Fallback summary when AI is not available"""
        if len(messages) <= 5:
            return f"**Summary of #{channel_name}** ({len(messages)} messages):\n\n" + \
                   "This was a brief conversation with the following key messages:\n" + \
                   "\n".join([f"• {msg[:100]}..." if len(msg) > 100 else f"• {msg}" for msg in messages[:3]])
        
        # Extract participants
        participants = set()
        for msg in messages:
            if ':' in msg:
                participants.add(msg.split(':')[0])
        
        return f"**Summary of #{channel_name}** ({len(messages)} messages):\n\n" + \
               f"🗣️ **Participants**: {', '.join(list(participants)[:5])}\n" + \
               f"📅 **Time Range**: Recent activity\n" + \
               f"💬 **Activity Level**: {len(messages)} messages exchanged\n\n" + \
               "⚠️ *Detailed AI summary unavailable - Claude API key not configured*"

# Initialize summarizer
summarizer = MessageSummarizer(ANTHROPIC_API_KEY)

async def fetch_recent_messages(channel, hours: int = 24, limit: int = 100) -> List[str]:
    """Fetch recent messages from a channel"""
    messages = []
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        async for message in channel.history(limit=limit, after=cutoff_time):
            if not message.author.bot:  # Skip bot messages
                # Format: "Username: Message content"
                formatted_msg = f"{message.author.display_name}: {message.content}"
                messages.append(formatted_msg)
        
        # Reverse to get chronological order
        messages.reverse()
        return messages
        
    except discord.Forbidden:
        print(f"No permission to read messages in #{channel.name}")
        return []
    except Exception as e:
        print(f"Error fetching messages: {e}")
        return []

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    print(f'Bot ID: {bot.user.id}')
    print(f'Message Content Intent: {bot.intents.message_content}')
    
    # Debug: Print registered commands
    print("Registered commands:")
    for command in bot.commands:
        print(f"  - {command.name}")

@bot.event
async def on_message(message):
    # Debug: Print all messages the bot sees
    if message.author != bot.user:
        print(f"Received message: '{message.content}' from {message.author}")
        
        # Check if it's a command
        if message.content.startswith('!'):
            print(f"Processing potential command: {message.content}")
    
    # Process commands
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    print(f"Command error: {error}")
    print(f"Command: {ctx.command}")
    print(f"Message: {ctx.message.content}")
    await ctx.send(f"❌ Error: {error}")

@bot.event
async def on_command(ctx):
    """Called when a command is successfully invoked"""
    print(f"Command invoked: {ctx.command} by {ctx.author}")

@bot.command(name='ping')
async def ping_command(ctx):
    """Simple test command"""
    await ctx.send("🏓 Pong! Bot is working!")
    print(f"Ping command executed by {ctx.author}")

@bot.command(name='test')
async def test_command(ctx):
    """Another test command"""
    await ctx.send("✅ Test command working!")
    print(f"Test command executed by {ctx.author}")

@bot.command(name='help_summarizer')
async def help_command(ctx):
    """Show available commands"""
    help_text = """
🤖 **Discord Summarizer Bot with Claude AI**

**Commands:**

`!ping` - Test if bot is working
`!test` - Another test command
`!help_summarizer` - Show this help message
`!summarize [hours] [limit]` - Summarize recent messages in current channel
`!summarize_channel <channel_name> [hours] [limit]` - Summarize messages from specific channel

**Examples:**
• `!ping` - Test the bot
• `!summarize` - Summarize last 24 hours
• `!summarize 12 50` - Summarize last 12 hours, max 50 messages
• `!summarize_channel general 6` - Summarize #general from last 6 hours

**Powered by Claude AI** 🧠
    """
    await ctx.send(help_text)

@bot.command(name='summarize')
async def summarize_command(ctx, hours: int = 24, limit: int = 100):
    """Summarize recent messages in the current channel"""
    await ctx.send(f"📊 Fetching messages from the last {hours} hours...")
    
    messages = await fetch_recent_messages(ctx.channel, hours, limit)
    
    if not messages:
        await ctx.send("No messages found in the specified time period.")
        return
    
    await ctx.send(f"🤖 Claude is analyzing {len(messages)} messages...")
    
    summary = await summarizer.summarize_messages(messages, ctx.channel.name, "comprehensive")
    
    # Split long summaries if needed
    if len(summary) > 2000:
        chunks = [summary[i:i+2000] for i in range(0, len(summary), 2000)]
        for chunk in chunks:
            await ctx.send(chunk)
    else:
        await ctx.send(summary)

@bot.command(name='summarize_channel')
async def summarize_channel_command(ctx, channel_name: str, hours: int = 24, limit: int = 100):
    """Summarize messages from a specific channel"""
    channel = discord.utils.get(ctx.guild.channels, name=channel_name)
    
    if not channel:
        await ctx.send(f"Channel '{channel_name}' not found.")
        return
    
    if not isinstance(channel, discord.TextChannel):
        await ctx.send(f"'{channel_name}' is not a text channel.")
        return
    
    await ctx.send(f"📊 Fetching messages from #{channel_name} (last {hours} hours)...")
    
    messages = await fetch_recent_messages(channel, hours, limit)
    
    if not messages:
        await ctx.send(f"No messages found in #{channel_name} for the specified time period.")
        return
    
    await ctx.send(f"🤖 Claude is analyzing {len(messages)} messages from #{channel_name}...")
    
    summary = await summarizer.summarize_messages(messages, channel.name, "comprehensive")
    
    if len(summary) > 2000:
        chunks = [summary[i:i+2000] for i in range(0, len(summary), 2000)]
        for chunk in chunks:
            await ctx.send(chunk)
    else:
        await ctx.send(summary)

# Main execution
async def main():
    # Configuration
    DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    if not DISCORD_TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        return
    
    if not ANTHROPIC_API_KEY:
        print("Warning: ANTHROPIC_API_KEY environment variable not set")
        print("Bot will run but summaries will be basic without Claude AI")
    
    # Run the bot
    try:
        await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("Invalid Discord token")
    except Exception as e:
        print(f"Error running bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
