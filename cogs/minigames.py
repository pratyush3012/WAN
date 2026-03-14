import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
from utils.permissions import is_member

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y
    
    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if interaction.user != view.current_player:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        
        if view.board[self.y][self.x] != 0:
            return await interaction.response.send_message("That spot is taken!", ephemeral=True)
        
        view.board[self.y][self.x] = view.current_mark
        self.label = view.current_symbol
        self.style = discord.ButtonStyle.primary if view.current_mark == 1 else discord.ButtonStyle.danger
        self.disabled = True
        
        winner = view.check_winner()
        if winner:
            for child in view.children:
                child.disabled = True
            view.stop()
            
            if winner == 3:
                await interaction.response.edit_message(content="It's a tie!", view=view)
            else:
                winner_player = view.player1 if winner == 1 else view.player2
                await interaction.response.edit_message(content=f"{winner_player.mention} wins!", view=view)
        else:
            view.switch_player()
            await interaction.response.edit_message(
                content=f"{view.current_player.mention}'s turn ({view.current_symbol})",
                view=view
            )

class TicTacToeView(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(timeout=60)
        self.player1 = player1
        self.player2 = player2
        self.current_player = player1
        self.current_mark = 1
        self.current_symbol = "X"
        self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))
    
    def switch_player(self):
        self.current_player = self.player2 if self.current_player == self.player1 else self.player1
        self.current_mark = 2 if self.current_mark == 1 else 1
        self.current_symbol = "O" if self.current_symbol == "X" else "X"
    
    def check_winner(self):
        # Check rows
        for row in self.board:
            if row[0] == row[1] == row[2] != 0:
                return row[0]
        
        # Check columns
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] != 0:
                return self.board[0][col]
        
        # Check diagonals
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != 0:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != 0:
            return self.board[0][2]
        
        # Check tie
        if all(self.board[y][x] != 0 for y in range(3) for x in range(3)):
            return 3
        
        return None

class MiniGames(commands.Cog):
    """Mini Games - Interactive games to play with friends"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="tictactoe", description="Play Tic-Tac-Toe with someone")
    @is_member()
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.Member):
        """Play tic-tac-toe"""
        
        if opponent.bot:
            return await interaction.response.send_message(
                "❌ You can't play with a bot!",
                ephemeral=True
            )
        
        if opponent == interaction.user:
            return await interaction.response.send_message(
                "❌ You can't play with yourself!",
                ephemeral=True
            )
        
        view = TicTacToeView(interaction.user, opponent)
        await interaction.response.send_message(
            f"{interaction.user.mention} vs {opponent.mention}\n{interaction.user.mention}'s turn (X)",
            view=view
        )
    
    @app_commands.command(name="coinflip", description="Flip a coin")
    @is_member()
    async def coinflip(self, interaction: discord.Interaction):
        """Flip a coin"""
        result = random.choice(["Heads", "Tails"])
        emoji = "🪙" if result == "Heads" else "🎴"
        
        await interaction.response.send_message(f"{emoji} **{result}**!")
    
    @app_commands.command(name="dice", description="Roll dice")
    @is_member()
    async def dice(self, interaction: discord.Interaction, sides: int = 6, count: int = 1):
        """Roll dice"""
        
        if sides < 2 or sides > 100:
            return await interaction.response.send_message(
                "❌ Sides must be between 2 and 100!",
                ephemeral=True
            )
        
        if count < 1 or count > 10:
            return await interaction.response.send_message(
                "❌ Count must be between 1 and 10!",
                ephemeral=True
            )
        
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        
        embed = discord.Embed(
            title="🎲 Dice Roll",
            color=discord.Color.blue()
        )
        embed.add_field(name="Rolls", value=" + ".join(map(str, rolls)), inline=False)
        embed.add_field(name="Total", value=str(total), inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="rps", description="Play Rock Paper Scissors")
    @is_member()
    async def rps(self, interaction: discord.Interaction, choice: str):
        """Play rock paper scissors"""
        
        choices = ["rock", "paper", "scissors"]
        choice = choice.lower()
        
        if choice not in choices:
            return await interaction.response.send_message(
                "❌ Choose rock, paper, or scissors!",
                ephemeral=True
            )
        
        bot_choice = random.choice(choices)
        
        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        
        if choice == bot_choice:
            result = "It's a tie!"
            color = discord.Color.gold()
        elif (choice == "rock" and bot_choice == "scissors") or \
             (choice == "paper" and bot_choice == "rock") or \
             (choice == "scissors" and bot_choice == "paper"):
            result = "You win!"
            color = discord.Color.green()
        else:
            result = "You lose!"
            color = discord.Color.red()
        
        embed = discord.Embed(
            title="Rock Paper Scissors",
            description=f"You chose {emojis[choice]} **{choice.title()}**\nI chose {emojis[bot_choice]} **{bot_choice.title()}**\n\n**{result}**",
            color=color
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="hangman", description="Play Hangman")
    @is_member()
    async def hangman(self, interaction: discord.Interaction):
        """Play hangman"""
        
        words = [
            "python", "discord", "gaming", "streaming", "youtube",
            "computer", "keyboard", "mouse", "monitor", "headset",
            "microphone", "camera", "internet", "server", "channel"
        ]
        
        word = random.choice(words).upper()
        guessed = set()
        wrong = 0
        max_wrong = 6
        
        def get_display():
            return " ".join(c if c in guessed else "_" for c in word)
        
        def get_hangman():
            stages = [
                "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",
                "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",
                "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",
                "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",
                "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",
                "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
                "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```"
            ]
            return stages[wrong]
        
        embed = discord.Embed(
            title="🎮 Hangman",
            description=f"{get_hangman()}\n\nWord: {get_display()}\n\nGuessed: {', '.join(sorted(guessed)) or 'None'}\n\nType a letter to guess!",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel and len(m.content) == 1 and m.content.isalpha()
        
        while wrong < max_wrong and set(word) != guessed:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60.0)
                letter = msg.content.upper()
                
                if letter in guessed:
                    await msg.delete()
                    continue
                
                guessed.add(letter)
                
                if letter not in word:
                    wrong += 1
                
                embed.description = f"{get_hangman()}\n\nWord: {get_display()}\n\nGuessed: {', '.join(sorted(guessed))}"
                
                if set(word) == guessed:
                    embed.color = discord.Color.green()
                    embed.description += f"\n\n✅ **You won!** The word was **{word}**"
                elif wrong >= max_wrong:
                    embed.color = discord.Color.red()
                    embed.description += f"\n\n❌ **You lost!** The word was **{word}**"
                
                await message.edit(embed=embed)
                await msg.delete()
                
            except asyncio.TimeoutError:
                embed.color = discord.Color.orange()
                embed.description += "\n\n⏱️ **Time's up!**"
                await message.edit(embed=embed)
                break
    
    @app_commands.command(name="trivia", description="Play trivia")
    @is_member()
    async def trivia(self, interaction: discord.Interaction):
        """Play trivia"""
        
        questions = [
            {"q": "What is the capital of France?", "a": ["Paris", "paris"], "wrong": ["London", "Berlin", "Madrid"]},
            {"q": "What is 2 + 2?", "a": ["4", "four"], "wrong": ["3", "5", "22"]},
            {"q": "What color is the sky?", "a": ["Blue", "blue"], "wrong": ["Red", "Green", "Yellow"]},
            {"q": "How many days in a week?", "a": ["7", "seven"], "wrong": ["5", "6", "8"]},
            {"q": "What is the largest planet?", "a": ["Jupiter", "jupiter"], "wrong": ["Earth", "Mars", "Saturn"]},
        ]
        
        question = random.choice(questions)
        all_answers = [question["a"][0]] + question["wrong"]
        random.shuffle(all_answers)
        
        embed = discord.Embed(
            title="🧠 Trivia",
            description=f"**{question['q']}**\n\n" + "\n".join(f"{i+1}. {ans}" for i, ans in enumerate(all_answers)),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Type the number of your answer!")
        
        await interaction.response.send_message(embed=embed)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit()
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30.0)
            answer_num = int(msg.content) - 1
            
            if 0 <= answer_num < len(all_answers):
                if all_answers[answer_num] in question["a"]:
                    await msg.reply("✅ **Correct!**")
                else:
                    await msg.reply(f"❌ **Wrong!** The answer was **{question['a'][0]}**")
            else:
                await msg.reply("❌ Invalid answer number!")
                
        except asyncio.TimeoutError:
            await interaction.followup.send(f"⏱️ **Time's up!** The answer was **{question['a'][0]}**")

async def setup(bot):
    await bot.add_cog(MiniGames(bot))
