"""
WAN Bot - Chatbot Cog
Gender-aware, fun, flirty, witty auto-replies in designated chatbot channels.
Configure with /chatbot-setchannel or from the dashboard.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging, random, re

logger = logging.getLogger('discord_bot.chatbot')
DATA_FILE = 'chatbot_data.json'

# ── Gender detection ──────────────────────────────────────────────────────────
FEMININE_NAMES = {
    'emma','olivia','ava','isabella','sophia','mia','charlotte','amelia','harper',
    'evelyn','abigail','emily','elizabeth','mila','ella','avery','sofia','camila',
    'aria','scarlett','victoria','madison','luna','grace','chloe','penelope',
    'layla','riley','zoey','nora','lily','eleanor','hannah','lillian','addison',
    'aubrey','ellie','stella','natalie','zoe','leah','hazel','violet','aurora',
    'savannah','audrey','brooklyn','bella','claire','skylar','lucy','paisley',
    'everly','anna','caroline','nova','genesis','emilia','kennedy','samantha',
    'maya','willow','kinsley','naomi','aaliyah','elena','sarah','ariana','allison',
    'gabriella','alice','madelyn','cora','ruby','eva','serenity','autumn','adeline',
    'hailey','gianna','valentina','isla','eliana','quinn','nevaeh','ivy','sadie',
    'piper','lydia','alexa','josephine','emery','julia','delilah','arianna',
    'vivian','kaylee','sophie','brielle','madeline','peyton','rylee','clara',
    'hadley','melanie','mackenzie','reagan','adalynn','liliana','aubree','jade',
    'katherine','isabelle','natalia','raelynn','jasmine','faith','alexandra',
    'morgan','khloe','london','destiny','ximena','ashley','brianna','ariel',
    'alyssa','andrea','vanessa','jessica','taylor','amber','brittany','tiffany',
    'priya','ananya','divya','pooja','neha','shreya','riya','aisha','fatima',
    'zara','sara','nadia','lena','nina','diana','vera','kate','amy','lisa',
    'mary','rose','hope','joy','dawn','eve','iris','pearl','opal','crystal',
    'sandy','cindy','wendy','mandy','candy','brandy','mindy','randi','candi',
}

MASCULINE_NAMES = {
    'liam','noah','william','james','oliver','benjamin','elijah','lucas','mason',
    'ethan','alexander','henry','jacob','michael','daniel','logan','jackson',
    'sebastian','jack','aiden','owen','samuel','ryan','nathan','luke','gabriel',
    'anthony','isaac','grayson','dylan','leo','jaxon','julian','levi','matthew',
    'wyatt','andrew','joshua','lincoln','christopher','joseph','theodore','caleb',
    'hunter','christian','eli','jonathan','connor','landon','adrian','asher',
    'cameron','colton','easton','gael','evan','kayden','angel','roman',
    'dominic','austin','ian','adam','nolan','brayden','thomas','charles','jace',
    'miles','brody','xavier','bentley','tyler','declan','carter','jason','cooper',
    'ryder','ayden','kevin','zachary','parker','blake','jose','chase','cole',
    'weston','hudson','jordan','greyson','bryson','zion','sawyer','emmett',
    'silas','micah','rowan','beau','tristan','ivan','alex','max','jake','sam',
    'ben','tom','tim','jim','bob','rob','joe','dan','ken','ron','don','ray',
    'jay','lee','rex','ace','ash','kai','zak','zac','zach',
    'arjun','rahul','rohan','vikram','aditya','karan','nikhil','siddharth',
    'pratik','pratyush','raj','amit','ankit','aman','akash','ayush','harsh',
    'yash','varun','tarun','arun','pavan','ravi','suresh','mahesh','ganesh',
    'ramesh','dinesh','naresh','mukesh','rakesh','lokesh','yogesh','umesh',
    'omar','ali','hassan','ahmed','khalid','tariq','bilal','hamza','usman',
    'mike','john','david','chris','mark','paul','steve','brian','eric',
    'jeff','scott','gary','larry','jerry','terry','barry','harry',
}

def _detect_gender(member: discord.Member) -> str:
    name = member.display_name.lower().strip()
    first = name.split()[0] if name.split() else name
    first_clean = ''.join(c for c in first if c.isalpha())
    if first_clean in FEMININE_NAMES:
        return 'female'
    if first_clean in MASCULINE_NAMES:
        return 'male'
    if any(first_clean.endswith(s) for s in ('ette','elle','ine','ina','ia','ya','ie','ee')):
        return 'female'
    return 'unknown'

