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
    
    async def summarize_messages_custom(self, messages: List[str], channel_name: str, custom_prompt: str) -> str:
        """Summarize messages using a custom prompt"""
        if not messages:
            return "No messages to summarize."
        
        # If no API key, fall back to simple summary
        if not self.client:
            return self._create_simple_summary(messages, channel_name)
        
        # Combine messages into a single text
        combined_text = "\n".join(messages)
        
        # Log message size for debugging
        char_count = len(combined_text)
        print(f"Preparing to send {char_count} characters to Claude API")
        
        # Truncate if too large (Claude has limits)
        if char_count > 150000:  # Conservative limit
            print(f"Message too large ({char_count} chars), truncating to last 150k characters")
            combined_text = combined_text[-150000:]
        
        # Use the custom prompt provided by the user
        full_prompt = f"""{custom_prompt}

Here are the Discord messages from #{channel_name}:

{combined_text}"""
        
        try:
            print("Sending request to Claude API...")
            
            # Call Claude API (synchronous)
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,  # Increased for custom summaries
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": full_prompt
                }]
            )
            
            print("Received response from Claude API")
            
            summary = response.content[0].text
            
            # Add metadata header
            header = f"🤖 **Custom Claude Summary of #{channel_name}**\n"
            header += f"📊 {len(messages)} messages analyzed\n"
            header += f"📝 Custom prompt: {custom_prompt[:100]}{'...' if len(custom_prompt) > 100 else ''}\n"
            header += f"⏰ Generated at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            
            print(f"Successfully generated summary ({len(summary)} characters)")
            return header + summary
            
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            print(f"Error type: {type(e).__name__}")
            return f"❌ **Error generating AI summary**: {str(e)}\n\n" + \
                   self._create_simple_summary(messages, channel_name)
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

async def fetch_messages_by_date_range(channel, start_date: str, end_date: str, limit: int = 200) -> List[str]:
    """Fetch messages from a channel within a specific date range"""
    messages = []
    
    try:
        # Parse date strings (expected format: YYYY-MM-DD)
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Include the entire end day
        
        # Calculate days difference for safety check
        days_diff = (end_datetime - start_datetime).days
        if days_diff > 90:  # Limit to 90 days to prevent memory issues
            print(f"Warning: Date range too large ({days_diff} days). Limiting to last 90 days.")
            start_datetime = end_datetime - timedelta(days=90)
        
        print(f"Fetching messages from {start_datetime} to {end_datetime} (max {limit} messages)")
        
        message_count = 0
        async for message in channel.history(limit=limit, after=start_datetime, before=end_datetime):
            if not message.author.bot:  # Skip bot messages
                # Format: "Username (YYYY-MM-DD HH:MM): Message content"
                timestamp = message.created_at.strftime('%Y-%m-%d %H:%M')
                formatted_msg = f"{message.author.display_name} ({timestamp}): {message.content}"
                messages.append(formatted_msg)
                message_count += 1
                
                # Progress indicator for large fetches
                if message_count % 50 == 0:
                    print(f"Fetched {message_count} messages so far...")
        
        print(f"Successfully fetched {len(messages)} messages")
        
        # Reverse to get chronological order
        messages.reverse()
        return messages
        
    except ValueError as e:
        print(f"Date parsing error: {e}")
        return []
    except discord.Forbidden:
        print(f"No permission to read messages in #{channel.name}")
        return []
    except Exception as e:
        print(f"Error fetching messages: {e}")
        return []
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

**Basic Summarization:**
`!summarize [hours] [limit]` - Summarize recent messages in current channel
`!summarize_channel <channel_name> [hours] [limit]` - Summarize messages from specific channel

**Advanced Custom Summarization:**
`!summarize_custom <channel_name> <start_date> <end_date> <custom_prompt>`
• channel_name: Name of the Discord channel
• start_date: Start date in YYYY-MM-DD format
• end_date: End date in YYYY-MM-DD format  
• custom_prompt: Your custom instructions for Claude

**Examples:**
• `!ping` - Test the bot
• `!summarize` - Summarize last 24 hours of current channel
• `!summarize_channel general 48` - Summarize #general from last 48 hours
• `!summarize_custom general 2025-05-20 2025-05-22 Summarize the key decisions and action items`
• `!summarize_custom dev-team 2025-05-01 2025-05-15 Focus on technical discussions and bugs mentioned`
• `!summarize_custom project-updates 2025-05-10 2025-05-20 Create a timeline of project milestones`

**Custom Prompt Ideas:**
• "Focus on action items and decisions made"
• "Summarize technical discussions and any bugs mentioned"  
• "Create a timeline of important events"
• "List all questions that were asked and their answers"
• "Identify the main topics and who contributed to each"
• "Extract key metrics, numbers, and data points mentioned"

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

@bot.command(name='summarize_custom')
async def summarize_custom_command(ctx, channel_name: str, start_date: str, end_date: str, *, summary_prompt: str):
    """
    Summarize messages from a specific channel with custom date range and prompt
    Usage: !summarize_custom channel_name YYYY-MM-DD YYYY-MM-DD your custom prompt here
    
    Examples:
    !summarize_custom general 2025-05-20 2025-05-22 Summarize the key decisions and action items from these messages
    !summarize_custom dev-team 2025-05-01 2025-05-15 Focus on technical discussions and any bugs mentioned
    """
    try:
        # Find the channel
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        
        if not channel:
            await ctx.send(f"❌ Channel '{channel_name}' not found.")
            return
        
        if not isinstance(channel, discord.TextChannel):
            await ctx.send(f"❌ '{channel_name}' is not a text channel.")
            return
        
        # Validate date format
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            days_diff = (end_dt - start_dt).days
            
            if days_diff > 90:
                await ctx.send(f"⚠️ Date range is {days_diff} days. For performance, limiting to last 90 days.")
            elif days_diff < 0:
                await ctx.send("❌ Start date must be before end date.")
                return
                
        except ValueError:
            await ctx.send("❌ Invalid date format. Please use YYYY-MM-DD format (e.g., 2025-05-22)")
            return
        
        await ctx.send(f"📊 Fetching messages from #{channel_name} between {start_date} and {end_date}...")
        await ctx.send("⏳ This may take a moment for large date ranges...")
        
        messages = await fetch_messages_by_date_range(channel, start_date, end_date, limit=200)
        
        if not messages:
            await ctx.send(f"No messages found in #{channel_name} for the specified date range.")
            return
        
        if len(messages) > 100:
            await ctx.send(f"📈 Found {len(messages)} messages. This is a large dataset - Claude analysis may take 30-60 seconds...")
        
        await ctx.send(f"🤖 Claude is analyzing {len(messages)} messages with your custom prompt...")
        
        # Add timeout handling
        try:
            summary = await asyncio.wait_for(
                summarizer.summarize_messages_custom(messages, channel.name, summary_prompt),
                timeout=120  # 2 minute timeout
            )
            
            # Split long summaries if needed
            if len(summary) > 2000:
                chunks = [summary[i:i+2000] for i in range(0, len(summary), 2000)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await ctx.send(chunk)
                    else:
                        await ctx.send(f"**Continued ({i+1}/{len(chunks)}):**\n{chunk}")
            else:
                await ctx.send(summary)
                
            print(f"Successfully completed custom summary for {ctx.author}")
            
        except asyncio.TimeoutError:
            await ctx.send("⏰ Analysis timed out. Try a smaller date range or fewer messages.")
            print("Custom summary timed out")
            
    except Exception as e:
        print(f"Error in summarize_custom_command: {e}")
        await ctx.send(f"❌ An error occurred: {str(e)}")
        await ctx.send("Try using a smaller date range or check the channel name.")

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
