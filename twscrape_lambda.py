import pandas as pd
import datetime as dt
import time
import logging
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
from fake_useragent import UserAgent

def setup_driver():
    chrome_path = "/opt/chrome/chrome-linux64/chrome"
    chromedriver_path = "/opt/chrome-driver/chromedriver-linux64/chromedriver"

    options = Options()
    options.binary_location = chrome_path
    options.add_argument("--headless=chrome")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--single-process")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=1280x800")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--single-process")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--headless")  

    service = Service(executable_path=chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

async def scrape_twitter(query: str, max_results: int = 50):
    api = API("/tmp/twscrape.db")

    cookies = "auth_token=4214a8c209ad0cb3d8631d5039a38f2b4bfccdc0; ct0=86088b9a59d9fdc9505110aaeb3939a57f846240052a5f40bcb051186e1bae009316eb82a0d13353c3a9bf08f63c5e1a3afcdfe0f34963c22f22b4f3e9aab668e96f7f2362bd1bf91524e4463217aad1"

    await api.pool.delete_accounts("skrepingkuliah")
    acc = await api.pool.add_account(
        username="skrepingkuliah",
        password="whyscrapingsohardla!123",
        email="rulcollegedummy@gmail.com",
        email_password="Pantsondummy!123",
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
    ua = UserAgent()
    user_agent = ua.random

    options = webdriver.ChromeOptions()
    options.add_argument(f'--user-agent={user_agent}')
    options.add_argument('--start-maximized')
    options.add_argument('--user-agent="Mozilla/5.0 (Windows Phone 10.0; Android 4.2.1; Microsoft; Lumia 640 XL LTE) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Mobile Safari/537.36 Edge/12.10166"')
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    container = soup.find('div', class_='my-6 grid grid-cols-1 md:grid-cols-2 md:gap-6 lg:grid-cols-4 lg:gap-6 -mx-6 md:mx-0')
    data = []   
    if container:
        links = container.find_all('a', href=True)
        hrefs = ['https://gofood.co.id' + a['href'] for a in links]
        for href in hrefs[:total_merch]:
            try:
                driver.get(href)
                time.sleep(8)
                driver.get(driver.current_url + '/reviews')
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'h2')))
                time.sleep(5)

                for _ in range(total_reviews_page):
                    try:
                        load_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Load more']]")))
                        load_button.click()
                        time.sleep(2)
                    except:
                        break

                review_soup = BeautifulSoup(driver.page_source, 'html.parser')
                partner_name = review_soup.find('h1')
                merchant_name = partner_name.text.strip() if partner_name else "Unknown"

                stars = review_soup.find_all('div', class_=lambda x: x and 'flex items-center' in x)
                reviews = review_soup.find_all('div', class_=lambda x: x and 'bg-gf-background-fill-primary' in x)
                dates = review_soup.find_all('div', class_=lambda x: x and 'text-gf-content-muted' in x)

                for star, review_block, date_tag in zip(stars, reviews, dates):
                    review_tag = review_block.find('p')
                    if not review_tag:
                        continue
                    product_tag = review_block.find('span')
                    rating_tag = star.find('span')
                    data.append({
                        'merchant_name': merchant_name,
                        'date_review': date_tag.text.strip().replace('Purchased on', '').strip(),
                        'product_name': product_tag.text.strip() if product_tag else 'Unknown',
                        'review': review_tag.text.strip(),
                        'rating': rating_tag.text.strip() if rating_tag else '0',
                    })
            except Exception as e:
                logging.error(f"Gagal proses {href}: {e}")
        driver.quit()
    return pd.DataFrame(data)


# ========== UPLOAD KE S3 ==========
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
    df_tweets.to_csv("/tmp/tweets_review.csv", index=False)
    upload_s3(df_tweets, "tweets_reviews.csv")
    
    print("Starting GoFood Scraping Process...")
    df_gofood = scrap_gofood("https://gofood.co.id/en/malang/restaurants/best_seller", 10, 3)
    df_gofood.to_csv("/tmp/gofood_reviews.csv", index=False)
    upload_s3(df_gofood, "gofood_reviews.csv")
    
    print("All Process Completed...")

def lambda_handler(event=None, context=None):
    main()