import discord
from discord.ext import commands
import asyncio
import json
import re


# permission helper check
def is_moderator(ctx):
	return ctx.message.author.top_role.name in config.admin_roles


class Config:
	def __init__(self, configFile):
		config = json.load(open(configFile))
		self.token = config["token"]
		self.prefix = config["prefix"]
		self.admin_roles = config["admin_roles"]
		self.mute_role = config["mute_role"]
		self.moderator_channel = int(config["moderator_channel"])
		self.gulag_channel = int(config["gulag_channel"])
		self.blacklist_file = config["blacklist_file"]


class BeepskyBot(commands.Bot):
	async def on_ready(self):
		print(f"{self.user} is ready!")


class UtilCommands(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.command()
	async def ping(self, ctx):
		latency = bot.latency
		await ctx.send(latency)

	@commands.command()
	async def firstseen(self, ctx, member: discord.Member):
		await ctx.send("{0} joined on {0.joined_at}".format(member))


class BlacklistWatcher(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.word_blacklist = []
		self.output_channel = None
		self.ignored_channel = None
		self.regexExp = None

	@commands.Cog.listener()
	async def on_ready(self):
		self.output_channel = self.bot.get_channel(config.moderator_channel)
		if not self.output_channel:
			print(f"Unable to find moderator channel {config.moderator_channel}")
		else:
			print(f"Found moderator channel {self.output_channel}")

		self.ignored_channel = self.bot.get_channel(config.gulag_channel)
		if not self.ignored_channel:
			print(f"Unable to find gulag channel {config.ignored_channel}")
		else:
			print(f"Found gulag channel {self.ignored_channel}")

		self.blacklist_read()

	async def cog_command_error(self, ctx, error):
		if isinstance(error, commands.CheckFailure):
			await ctx.send("You do not have the permissions to use the blacklist")
		elif isinstance(error, commands.UserInputError):
			await ctx.send(f"Incorrect usage. Use: `{config.prefix}blacklist add|remove word`")
		else:
			await ctx.send("Unknown failure...")
			print(str(error))

	# adds a word to the blacklist
	async def blacklist_add(self, ctx, word):
		word = word.lower()
		if word not in self.word_blacklist:
			self.word_blacklist.append(word)
			await ctx.send(f"Added {word} to blacklist!")
			self.blacklist_update_regex()
			self.blacklist_write()
		else:
			await ctx.send(f"Blacklist already contains {word}!")

	# removes a word from the blacklist
	async def blacklist_remove(self, ctx, word):
		word = word.lower()
		if word in self.word_blacklist:
			self.word_blacklist.remove(word)
			await ctx.send(f"Removed {word} from the blacklist!")
			self.blacklist_update_regex()
			self.blacklist_write()
		else:
			await ctx.send(f"Blacklist doesn't contain {word}!")

	# print all words in the blacklist
	async def blacklist_list(self, ctx):
		if len(self.word_blacklist) != 0:
			out = ""
			for word in self.word_blacklist:
				out = out + word + ", "
			await ctx.send(f"Blacklist contains `{out}`")
		else:
			await ctx.send("The blacklist is empty!")

	# used to write blacklist to file
	def blacklist_write(self):
		file = open(config.blacklist_file, "w")
		for word in self.word_blacklist:
			file.write(word + "\n")
		file.close()
		print("Updated blacklist file!")

	def blacklist_read(self):
		self.word_blacklist = []
		with open(config.blacklist_file, "r") as file:
			self.word_blacklist = file.read().splitlines()
		file.close()
		self.blacklist_update_regex()
		print("Loaded blacklist file!")

	def blacklist_update_regex(self):
		string = "(" + "|".join(self.word_blacklist) + ")\\b"
		self.regexExp = re.compile(string)
		print(f"Compiled regex as {string}")

	# blacklist control function
	@commands.command()
	@commands.check(is_moderator)
	async def blacklist(self, ctx, *args):
		arglen = len(args)
		if arglen == 1:
			if args[0] == "list":
				await self.blacklist_list(ctx)
			else:
				raise commands.UserInputError(ctx.message.content)
				return

		elif arglen == 2:
			mode = args[0]
			word = args[1]
			if mode == "add":
				await self.blacklist_add(ctx, word)
			elif mode == "remove":
				await self.blacklist_remove(ctx, word)
			else:
				raise commands.UserInputError(ctx.message.content)
				return
		else:
			raise commands.UserInputError(ctx.message.content)

	# Reads ALL messages, used for detecting words in the blacklist
	@commands.Cog.listener()
	async def on_message(self, msg):
		if not msg.author.bot and msg.content[0] != config.prefix and msg.channel != self.ignored_channel:
			match = re.search(self.regexExp, msg.content.lower())
			if match:
				await self.output_channel.send(content=f"\U000026A0Warning: {msg.author.mention} made a post in {msg.channel.mention}"
													   f" containing a blacklisted word. \"`{msg.clean_content}`\"")


class AdminCommands(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	def cog_check(self, ctx):
		return ctx.message.author.top_role.name in config.admin_roles

	async def cog_command_error(self, ctx, error):
		if isinstance(error, commands.CheckFailure):
			await ctx.send("You do not have the permissions required "
						   "to run this command.")

	''' for debugging use
	@commands.command()
	async def die(self, ctx):
		await ctx.send("Shutting Down...")
		await bot.change_presence(status=discord.Status.invisible)
		await bot.logout()

		print("shutting down")'''

	@commands.command()
	async def permtest(self, ctx):
		await ctx.send("You can run admin commands!")

	@commands.command()
	async def punish(self, ctx, user: discord.Member=None, *, reason=None):
		if user:
			if config.punish_role in user.roles:
				await ctx.send(f"{user.name} is already punished. "
							   "Have a secure day!")
			else:
				await ctx.send(f"Detaining level 5 scumbag {user.name}!")
				blame = "{ctx.author.name} punished {user.name}: {reason}"
				await user.add_roles(config.punish_role, reason=blame)
		else:
			await ctx.send(f"No such user '{user.name}'.")

	@commands.command()
	async def unpunish(self, ctx, user: discord.Member=None):
		if user:
			if config.punish_role not in user.roles:
				await ctx.send(f"{user.name} is not punished. Yet.")
			else:
				await ctx.send(f"{user.name} is no longer punished.")
				await user.remove_roles(config.punish_role)
		else:
			await ctx.send(f"No such user '{user.name}'.")

	@commands.command()
	async def cooldown(self, ctx, user: discord.Member=None, time=5):
		await self.punish(user)
		await asyncio.sleep(time*60)
		await self.unpunish(user)


config = Config("config.json")

bot = BeepskyBot(command_prefix=config.prefix)
bot.add_cog(UtilCommands(bot))
bot.add_cog(BlacklistWatcher(bot))
bot.add_cog(AdminCommands(bot))

bot.run(config.token)
