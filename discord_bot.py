import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import os
from typing import List, Optional
import json
import anthropic
from anthropic import AsyncAnthropic

# You'll need to install: pip install discord.py anthropic

class MessageSummarizer:
    def __init__(self, anthropic_api_key: str = None):
        """Initialize the summarizer with Anthropic Claude"""
        self.anthropic_api_key = anthropic_api_key
        self.client = AsyncAnthropic(api_key=anthropic_api_key) if anthropic_api_key else None
    
    async def summarize_messages(self, messages: List[str], channel_name: str, summary_style: str = "comprehensive") -> str:
        """
        Summarize a list of messages using Claude
        """
        if not messages:
            return "No messages to summarize."
        
        # If no API key, fall back to simple summary
        if not self.client:
            return self._create_simple_summary(messages, channel_name)
        
        # Combine messages into a single text
        combined_text = "\n".join(messages)
        
        # Create appropriate prompt based on summary style
        prompts = {
            "comprehensive": f"""Please provide a comprehensive summary of these Discord messages from #{channel_name}. 

Include:
- Main topics discussed
- Key decisions or conclusions
- Important announcements or updates
- Notable questions and answers
- Overall tone and sentiment of the conversation

Messages:
{combined_text}

Please format your response clearly with appropriate sections.""",
            
            "brief": f"""Please provide a brief, concise summary of these Discord messages from #{channel_name}.

Focus on:
- Main topics (1-2 sentences each)
- Key takeaways
- Important decisions or announcements

Keep it under 200 words.

Messages:
{combined_text}""",
            
            "bullet": f"""Please summarize these Discord messages from #{channel_name} in bullet point format.

Create organized bullet points covering:
- Main topics discussed
- Key decisions or outcomes
- Important announcements
- Notable questions/issues raised

Messages:
{combined_text}""",
            
            "participants": f"""Please analyze these Discord messages from #{channel_name} with focus on participant activity and engagement.

Include:
- Who were the main contributors
- What topics each person focused on
- Overall conversation dynamics
- Key interactions between participants

Messages:
{combined_text}"""
        }
        
        prompt = prompts.get(summary_style, prompts["comprehensive"])
        
        try:
            # Call Claude API
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",  # Latest Claude model
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
            header += f"📊 {len(messages)} messages analyzed • Style: {summary_style.title()}\n"
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

class DiscordSummarizerBot(commands.Bot):
    def __init__(self, anthropic_api_key: str = None):
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read message content
        super().__init__(command_prefix='!', intents=intents)
        
        self.summarizer = MessageSummarizer(anthropic_api_key)
    
    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        print(f'Bot is in {len(self.guilds)} guilds')
        print(f'Bot ID: {self.user.id}')
        print(f'Message Content Intent: {self.intents.message_content}')
    
    async def on_message(self, message):
        # Debug: Print all messages the bot sees
        if message.author != self.user:  # Don't respond to self
            print(f"Received message: '{message.content}' from {message.author}")
            
            # Check if it's a command
            if message.content.startswith('!'):
                print(f"Processing potential command: {message.content}")
        
        # Process commands
        await self.process_commands(message)
    
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        print(f"Command error: {error}")
        print(f"Command: {ctx.command}")
        print(f"Message: {ctx.message.content}")
        await ctx.send(f"❌ Error: {error}")
    
    async def on_command(self, ctx):
        """Called when a command is successfully invoked"""
        print(f"Command invoked: {ctx.command} by {ctx.author}")
    
    async def fetch_recent_messages(self, channel, hours: int = 24, limit: int = 100) -> List[str]:
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
    
    @commands.command(name='summarize')
    async def summarize_channel(self, ctx, hours: int = 24, limit: int = 100, style: str = "comprehensive"):
        """
        Summarize recent messages in the current channel
        Usage: !summarize [hours] [limit] [style]
        Styles: comprehensive, brief, bullet, participants
        """
        if style not in ["comprehensive", "brief", "bullet", "participants"]:
            await ctx.send("❌ Invalid style. Choose from: comprehensive, brief, bullet, participants")
            return
            
        await ctx.send(f"📊 Fetching messages from the last {hours} hours...")
        
        messages = await self.fetch_recent_messages(ctx.channel, hours, limit)
        
        if not messages:
            await ctx.send("No messages found in the specified time period.")
            return
        
        await ctx.send(f"🤖 Claude is analyzing {len(messages)} messages...")
        
        summary = await self.summarizer.summarize_messages(messages, ctx.channel.name, style)
        
        # Split long summaries if needed
        if len(summary) > 2000:
            chunks = [summary[i:i+2000] for i in range(0, len(summary), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(summary)
    
    @commands.command(name='summarize_channel')
    async def summarize_specific_channel(self, ctx, channel_name: str, hours: int = 24, limit: int = 100, style: str = "comprehensive"):
        """
        Summarize messages from a specific channel
        Usage: !summarize_channel channel_name [hours] [limit] [style]
        Styles: comprehensive, brief, bullet, participants
        """
        if style not in ["comprehensive", "brief", "bullet", "participants"]:
            await ctx.send("❌ Invalid style. Choose from: comprehensive, brief, bullet, participants")
            return
            
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        
        if not channel:
            await ctx.send(f"Channel '{channel_name}' not found.")
            return
        
        if not isinstance(channel, discord.TextChannel):
            await ctx.send(f"'{channel_name}' is not a text channel.")
            return
        
        await ctx.send(f"📊 Fetching messages from #{channel_name} (last {hours} hours)...")
        
        messages = await self.fetch_recent_messages(channel, hours, limit)
        
        if not messages:
            await ctx.send(f"No messages found in #{channel_name} for the specified time period.")
            return
        
        await ctx.send(f"🤖 Claude is analyzing {len(messages)} messages from #{channel_name}...")
        
        summary = await self.summarizer.summarize_messages(messages, channel.name, style)
        
        if len(summary) > 2000:
            chunks = [summary[i:i+2000] for i in range(0, len(summary), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(summary)
    
    @commands.command(name='help_summarizer')
    async def help_command(self, ctx):
        """Show available commands"""
        help_text = """
🤖 **Discord Summarizer Bot with Claude AI**

**Commands:**

`!summarize [hours] [limit] [style]` - Summarize recent messages in current channel
• hours: How many hours back to look (default: 24)
• limit: Maximum messages to fetch (default: 100)
• style: Summary style (default: comprehensive)

`!summarize_channel <channel_name> [hours] [limit] [style]` - Summarize messages from specific channel

`!help_summarizer` - Show this help message

**Summary Styles:**
• `comprehensive` - Detailed analysis with topics, decisions, and sentiment
• `brief` - Concise overview under 200 words
• `bullet` - Organized bullet point format
• `participants` - Focus on who said what and conversation dynamics

**Examples:**
• `!summarize` - Comprehensive summary of last 24 hours
• `!summarize 12 50 brief` - Brief summary of last 12 hours, max 50 messages
• `!summarize_channel general 6 100 bullet` - Bullet point summary of #general from last 6 hours
• `!summarize 24 100 participants` - Analyze participant activity from last 24 hours

**Powered by Claude AI** 🧠
        """
        await ctx.send(help_text)

# Main execution
async def main():
    # Configuration
    DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')  # Set this environment variable
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')  # Set this for Claude AI summaries
    
    if not DISCORD_TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        print("Please set your Discord bot token as an environment variable")
        return
    
    if not ANTHROPIC_API_KEY:
        print("Warning: ANTHROPIC_API_KEY environment variable not set")
        print("Bot will run but summaries will be basic without Claude AI")
    
    # Create and run the bot
    bot = DiscordSummarizerBot(ANTHROPIC_API_KEY)
    
    try:
        await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("Invalid Discord token")
    except Exception as e:
        print(f"Error running bot: {e}")

if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
