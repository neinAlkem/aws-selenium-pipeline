
import asyncio
from twscrape import API
from contextlib import aclosing
import os
from dotenv import load_dotenv

load_dotenv()

def parse_cookie_string(cookie_string):
    return dict(pair.strip().split("=", 1) for pair in cookie_string.split(";"))

async def main():
    """
    The main function uses an API to delete and add accounts, login, and search for tweets based on a
    specific query.
    """
    api = API()

    cookies = os.getenv("COOKIES")

    await api.pool.delete_accounts("skrepingkuliah")
    acc = await api.pool.add_account(
        username=os.getenv("USERNAME"),
        password=os.getenv("PASSWORD"),
        email=os.getenv("EMAIL"),
        email_password=os.getenv("EMAIL_PASS"),
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        cookies=cookies
    )
    
    await api.pool.login_all()

    print("Starting Tweet Scrap..")
    
    async with aclosing(api.search("makan di malang")) as query:
        count = 0
        async for tweet in query:
            print(f"ID: {tweet.id}")
            print(f"Username: {tweet.user.username}")
            print(f"Waktu Tweet: {tweet.date}")
            print(f"Tweet: {tweet.rawContent}\n")
            count += 1
            # Amount of tweets to be retrived
            if count >=20:
                break

    print("Process Completed..")

if __name__ == "__main__":
    asyncio.run(main())

    
