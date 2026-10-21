"""Uploads the first Notification Box and Curio Vault episodes to TikTok as private posts."""
import os

import tiktok_mcp as t

POSTS = [
    (
        "thenotificationbox",
        r"C:\Users\siraj\Downloads\Shorts\Fake Texts\ft1e1.mp4",
        """The First-Class Upgrade Trap

When Mark accidentally receives a flight upgrade confirmation for his wife and his best friend to Paris, he realizes their upcoming work trips are an elaborate cover for an affair. Instead of confronting them immediately, Mark orchestrates a live property auction of their shared luxury assets while they are trapped mid-flight without cellular service.

#faketexts #cheatingcaught #revenge #textstory #drama #part1 #fyp #trending #texts #interesting #fortheworld #worldwide #youtube""",
    ),
    (
        "the_curio_vault1945",
        r"C:\Users\siraj\Downloads\Shorts\Reddit\hist1.mp4",
        """The Secret Codes Nailed to Telephone Poles

Ever wondered why old wooden telephone poles have strange metal tags and numbers nailed into them? In the early 1900s, utility linemen used arcane symbols and copper date nails for chemical tracking, leading superstitious mountain communities to believe they were government occult hexes! Here is the bizarre true history behind these mysterious roadside codes.

#Shorts #BizarreHistory #ForgottenHistory #Appalachia #HistoricalMysteries #fyp #trending #curiosity #mindboggling #interesting #foryoupage #trend""",
    ),
]

for account, path, caption in POSTS:
    print(f"--- {account}")
    if not os.path.exists(path):
        print(f"FILE NOT FOUND: {path}")
        continue
    try:
        result = t.post_video(account, path, caption, "SELF_ONLY")
        print("uploaded:", result)
        print("status:", t.publish_status(account, result["publish_id"]))
    except Exception as e:
        print("FAILED:", e)
