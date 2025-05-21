import pandas as pd
import time
import logging
from tempfile import mkdtemp
from io import StringIO
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import boto3
import asyncio
from twscrape import API
from contextlib import aclosing
import pandas as pd
import numpy as np
import re
import pytz
import string
import os 
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG, format='$(asctime)s - $(levelname)s - $(message)s')

food_drink_terms = set("""
bakso sate soto rawon pecel nasi goreng ayam goreng ayam geprek
mie ayam mie ayam geprek indomie ramen udon sushi sashimi pizza burger
kebab shawarma rendang gudeg lalapan dimsum siomay batagor lumpia martabak
roti kue brownies cheesecake croissant donat waffle pancake puding eskrim gelato
kopi latte cappuccino espresso americano matcha boba bubble es  teh soda cola sprite fanta
jus smoothie milkshake
""".split())

# ── Helper fungsi ────────────────────────────────────────────────────
STAR_RE = re.compile('[⭐★]')
NUM_RE = re.compile(r'([1-5])\s*/\s*5')
WORD_RE = re.compile(r'(?i)bintang\s+([1-5])')
SHOP_RE = re.compile(r'\b(?:di|at)\s+([A-Z][\w&\'\-\.]*(?:\s+[A-Z][\w&\'\-\.]*){0,3})')

tz = pytz.timezone('Asia/Jakarta')

def clean(txt: str) -> str:
    txt = re.sub(r'http\S+|@\w+|#\w+', '', txt)   # hapus URL, mention, hashtag
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt

def rating(txt: str):
    stars = len(STAR_RE.findall(txt))
    if 1 <= stars <= 5: return stars
    m = NUM_RE.search(txt) or WORD_RE.search(txt)
    return int(m.group(1)) if m else np.nan

def produk(txt: str):
    words = [w.lower().strip(string.punctuation) for w in txt.split()]
    for i, w in enumerate(words):
        if w in food_drink_terms: return w.title()
        # cek bigram
        if i < len(words)-1:
            bigram = f"{w} {words[i+1]}"
            if all(x in food_drink_terms for x in bigram.split()):
                return bigram.title()
    return np.nan

def toko(txt: str):
    m = SHOP_RE.search(txt)
    if m: return m.group(1).strip()
    ment = re.search(r'@(\w+)', txt)  # fallback username mention
    return ment.group(1) if ment else np.nan

def tanggal(ts):
    try:
        return pd.to_datetime(ts, utc=True).tz_convert(tz).strftime('%d %B %Y')
    except: return np.nan

def transform_tweets(df_tweets):
    def transform_row(row):
        raw = str(row['content'])
        return pd.Series({
            'merchant_name': toko(raw),
            'date_review': tanggal(row['date']),
            'product_name': produk(raw),
            'review': clean(raw),
            'rating': rating(raw),
        })
    
    return df_tweets.apply(transform_row, axis=1)

async def scrape_twitter(query: str, max_results: int = 50):
    api = API("/tmp/twscrape.db")

    cookies = os.getenv("COOKIES")

    await api.pool.delete_accounts("skrepingkuliah")
    acc = await api.pool.add_account(
        username=os.getenv("USERNAME"),
        # password=os.getenv("PASSWORD"),
        email=os.getenv("EMAIL"),
        email_password=os.getenv("EMAIL_PASS"),
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        cookies=cookies
    )    
    await api.pool.login_all()

    tweets_data = []
    async with aclosing(api.search("makan di malang")) as query:
        count = 0
        async for tweet in query:
            tweet_info = {
                "id": tweet.id,
                "username": tweet.user.username,
                "date": tweet.date,
                "content": tweet.rawContent
            }
            tweets_data.append(tweet_info)
            print(tweet_info)
            count += 1
            if count >= max_results:
                break
            
    return pd.DataFrame(tweets_data)
        
# ========== SCRAPE GOFOOD ==========
def scrap_gofood(url, total_merch, total_reviews_page):
       
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-tools")
    chrome_options.add_argument("--no-zygote")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument(f"--user-data-dir={mkdtemp()}")
    chrome_options.add_argument(f"--data-path={mkdtemp()}")
    chrome_options.add_argument(f"--disk-cache-dir={mkdtemp()}")
    chrome_options.add_argument("--remote-debugging-pipe")
    chrome_options.add_argument("--verbose")
    chrome_options.add_argument("--log-path=/tmp")
    chrome_options.add_argument('--start-maximized')
    chrome_options.binary_location = "/opt/chrome/chrome-linux64/chrome"

    service = Service(
        executable_path="/opt/chrome-driver/chromedriver-linux64/chromedriver",
        service_log_path="/tmp/chromedriver.log"
    )

    driver = webdriver.Chrome(
        service=service,
        options=chrome_options
    )

    driver.get(url)
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    data = [] 

    container = soup.find('div', class_='my-6 grid grid-cols-1 md:grid-cols-2 md:gap-6 lg:grid-cols-4 lg:gap-6 -mx-6 md:mx-0')

    if container:
        links = container.find_all('a', href=True)
        hrefs = ['https://gofood.co.id' + a['href'] for a in links]

        for href in hrefs[:total_merch]:
            try:
                driver.get(href)
                time.sleep(5)

                review_url = driver.current_url + '/reviews'
                driver.get(review_url)
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'What people say') or contains(text(), 'All reviews')]")))
                time.sleep(5)

                for _ in range(total_reviews_page):
                    try: 
                        load_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(By.XPATH, "//button[.//span[text()='Load more']]"))
                        load_button.click()
                        time.sleep(2)
                    except:
                        break
                    
                review_soup = BeautifulSoup(driver.page_source, 'html.parser')
                all_reviews = review_soup.find('div', class_='mx-auto w-[calc(100%_-_48px)] max-w-wrapper py-6 md:w-[calc(100%_-_64px)] lg:pb-16')

                if not all_reviews:
                    print("No reviews found.")
                    break
                
                stars_container = review_soup.find_all('div', class_=lambda x: x and 'flex items-center' in x)
                date_container = review_soup.find_all('div', class_=lambda x:x and 'mt-4 text-gf-content-muted gf-body-s' in x)
                merch_title = review_soup.find('div', class_=lambda x: x and 'flex gap-4 mb-8' in x)
                review_containers = review_soup.find_all('div', class_=lambda x: x and 'bg-gf-background-fill-primary' in x)
                partner_name_tag = merch_title.find('h1', class_=lambda x: x and 'text-gf-content-primary' in x) if merch_title else None
                partner_name = partner_name_tag.text.strip() if partner_name_tag else "Unknown Merchant"

                for stars, container, date in zip(stars_container, review_containers, date_container):
                        try:
                            review_tag = container.find('p', class_=lambda x: x and 'break-words' in x)
                            if not review_tag or not review_tag.text.strip():
                                continue  
                            product_tag = container.find('span', class_=lambda x: x and 'ml-2 break-words md:mt-1' in x)
                            rating_tag = stars.find('span', class_=lambda x: x and 'ml-1 inline-block' in x)
                            
                            date_review = date.text.strip() if date else 'No date'
                            date_review = date_review.replace('Purchased on','').strip()
                            review_text = review_tag.text.strip() if review_tag else 'No review'
                            product_name = product_tag.text.strip() if product_tag else 'No product'
                            rating_text = rating_tag.text.strip() if rating_tag else 'No rating'

                            data.append({
                                'merchant_name': partner_name,
                                'date_review' : date_review,
                                'product_name': product_name,
                                'review': review_text,
                                'rating': rating_text,
                            })

                        except Exception as e:
                            logging.error(f'Error scraping review: {e}')

            except Exception as e:
                print(f'Failed to process {href}: {str(e)}')

    driver.quit()

    return pd.DataFrame(data)

# ========== UPLOAD TO S3 ==========
def upload_s3(df, file_name):
    s3 = boto3.client('s3')
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.put_object(Bucket='rdv-bucket-project', Key=file_name, Body=csv_buffer.getvalue())
    print(f"Uploaded {file_name} to S3")

# ========== MAIN ==========
def main():
    
    print("Starting Twitter Scraping Process...")
    df_tweets = asyncio.run(scrape_twitter(query="makanan di malang"))
    print("Transforming Twitter Scrape Result...")
    df_tweets_transform = transform_tweets(df_tweets)
    df_tweets_transform.to_csv("/tmp/tweet_reviews_transform.csv",index=False)
    upload_s3(df_tweets_transform, "tweets_reviews.csv")
    
    print("Starting GoFood Scraping Process...")
    df_gofood = scrap_gofood("https://gofood.co.id/en/malang/restaurants/best_seller", 10, 3)
    df_gofood.to_csv("/tmp/gofood_reviews.csv", index=False)
    upload_s3(df_gofood, "gofood_reviews.csv")
    
    print("All Process Completed...")

def lambda_handler(event=None, context=None):
    main()
