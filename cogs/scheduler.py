"""
Scheduler — scheduled & recurring posts (MEE6 USP)
Supports one-time and recurring (daily/weekly/hourly) messages.
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json, os, logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord_bot.scheduler')
SCHED_FILE = 'scheduler.json'


def _load():
    if os.path.exists(SCHED_FILE):
        try:
            with open(SCHED_FILE) as f: return json.load(f)
        except: pass
    return []


def _save(d):
    with open(SCHED_FILE, 'w') as f: json.dump(d, f, indent=2)


RECUR_DELTA = {
    'once': None,
    'hourly': timedelta(hours=1),
    'daily': timedelta(days=1),
    'weekly': timedelta(weeks=1),
}


class Scheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._check.start()

    def cog_unload(self):
        self._check.cancel()

    @tasks.loop(minutes=1)
    async def _check(self):
        jobs = _load()
        now = datetime.now(timezone.utc)
        updated = []
        for job in jobs:
            run_at = datetime.fromisoformat(job['run_at'])
            if run_at.tzinfo is None:
                run_at = run_at.replace(tzinfo=timezone.utc)
            if now >= run_at:
                ch = self.bot.get_channel(int(job['channel_id']))
                if ch:
                    try:
                        await ch.send(job['message'])
                    except Exception as e:
                        logger.warning(f'Scheduler send failed: {e}')
                recur = job.get('recur', 'once')
                delta = RECUR_DELTA.get(recur)
                if delta:
                    job['run_at'] = (run_at + delta).isoformat()
                    updated.append(job)
                # once → drop
            else:
                updated.append(job)
        _save(updated)

    @_check.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    @commands.command(name="schedule-add")
    async def add(self, ctx,
                  channel: discord.TextChannel,
                  message: str,
                  when: str,
                  recur: str = None):
        now = datetime.now(timezone.utc)
        # Parse relative time
        try:
            if when.endswith('m'):
                run_at = now + timedelta(minutes=int(when[:-1]))
            elif when.endswith('h'):
                run_at = now + timedelta(hours=int(when[:-1]))
            elif when.endswith('d'):
                run_at = now + timedelta(days=int(when[:-1]))
            else:
                run_at = datetime.fromisoformat(when).replace(tzinfo=timezone.utc)
        except:
            return await ctx.send(
                'Invalid time. Use relative like `2h`, `1d`, or ISO datetime.')

        jobs = _load()
        job = {
            'id': len(jobs) + 1,
            'guild_id': str(ctx.guild.id),
            'channel_id': str(channel.id),
            'message': message,
            'run_at': run_at.isoformat(),
            'recur': recur.value if recur else 'once',
            'created_by': str(ctx.author.id),
        }
        jobs.append(job)
        _save(jobs)
        recur_str = recur.value if recur else 'once'
        await ctx.send(
            f'Scheduled message #{job["id"]} in {channel.mention} at `{run_at.strftime("%Y-%m-%d %H:%M UTC")}` ({recur_str}).')

    @commands.command(name="schedule-list")
    async def list_jobs(self, ctx):
        jobs = [j for j in _load() if j.get('guild_id') == str(ctx.guild.id)]
        if not jobs:
            return await ctx.send('No scheduled messages.')
        embed = discord.Embed(title='Scheduled Messages', color=0x5865f2)
        for j in jobs[:10]:
            ch = ctx.guild.get_channel(int(j['channel_id']))
            embed.add_field(
                name=f'#{j["id"]} — {j["recur"]}',
                value=f'{ch.mention if ch else j["channel_id"]} • `{j["run_at"][:16]}`\n{j["message"][:80]}',
                inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="schedule-remove")
    async def remove(self, ctx, job_id: int):
        jobs = _load()
        before = len(jobs)
        jobs = [j for j in jobs if not (j.get('guild_id') == str(ctx.guild.id) and j['id'] == job_id)]
        if len(jobs) < before:
            _save(jobs)
            await ctx.send(f'Removed job #{job_id}.')
        else:
            await ctx.send('Job not found.')


async def setup(bot):
    await bot.add_cog(Scheduler(bot))
