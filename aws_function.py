import os
import re
import string
import subprocess
import sys
import numpy as np
import pandas as pd
import pytz
import datetime as dt
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import boto3
import time
import logging
from io import StringIO
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from tempfile import mkdtemp
from fake_useragent import UserAgent

# The above code is attempting to configure the logging module in Python. However, there is a typo in
# the code. It should be `logging.basicConfig` instead of `Plogging.basicConfig`. The code is setting
# the logging level to DEBUG and specifying the format of the log messages to include the timestamp,
# log level, and message.
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# def install_dependencies():
#     """Install all required dependencies for the application"""
#     print("Installing dependencies...")

#     # Install Python packages
#     subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas"])

#     # Install Node.js if not installed
#     try:
#         node_version = subprocess.check_output(["node", "-v"]).decode().strip()
#         print(f"✓ Node.js already installed: {node_version}")
#     except:
#         print("Installing Node.js...")
#         subprocess.check_call(["sudo", "apt-get", "update"])
#         subprocess.check_call(
#             ["sudo", "apt-get", "install", "-y", "ca-certificates", "curl", "gnupg"]
#         )
#         subprocess.check_call(["sudo", "mkdir", "-p", "/etc/apt/keyrings"])

#         subprocess.check_call(
#             "curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg",
#             shell=True,
#         )
#         subprocess.check_call(
#             'NODE_MAJOR=20 && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list',
#             shell=True,
#         )

#         subprocess.check_call(["sudo", "apt-get", "update"])
#         subprocess.check_call(["sudo", "apt-get", "install", "nodejs", "-y"])

#         node_version = subprocess.check_output(["node", "-v"]).decode().strip()
#         print(f"✓ Node.js installed: {node_version}")


def scrape_twitter(twitter_auth_token, filename, search_keyword, limit):
    """Scrape tweets using tweet-harvest"""
    print(f"Scraping Twitter for: '{search_keyword}'")
    print(f"Will save {limit} tweets to: {filename}")

    cmd = f'npx -y tweet-harvest@2.6.1 -o "{filename}" -s "{search_keyword}" --tab "LATEST" -l {limit} --token {twitter_auth_token}'
    subprocess.check_call(cmd, shell=True)

    # Check if file exists in tweets-data directory
    expected_path = f"tweets-data/{filename}"
    if os.path.exists(expected_path):
        print(f"Tweets saved to: {expected_path}")
        return expected_path
    else:
        print(f"⚠️ File not found at expected location: {expected_path}")
        # Try to find the file
        for root, dirs, files in os.walk("."):
            if filename in files:
                file_path = os.path.join(root, filename)
                print(f"✓ Found file at: {file_path}")
                return file_path

        raise FileNotFoundError(f"Could not find scraped tweets file: {filename}")

def transform_tweets(input_file, output_file="twitter_reviews_transformed.csv"):
    """Transform raw tweet data into structured reviews"""
    print(f"Transforming tweets from: {input_file}")

    # Read the CSV file
    try:
        tweets = pd.read_csv(input_file)
        print(f"Loaded {len(tweets)} tweets")
    except Exception as e:
        print(f"Error loading tweets file: {e}")
        raise

    # Stop-words & list makanan/minuman populer
    food_drink_terms = set(
        """
    bakso sate soto rawon pecel nasi goreng ayam goreng ayam geprek
    mie ayam mie ayam geprek indomie ramen udon sushi sashimi pizza burger
    kebab shawarma rendang gudeg lalapan dimsum siomay batagor lumpia martabak
    roti kue brownies cheesecake croissant donat waffle pancake puding eskrim gelato
    kopi latte cappuccino espresso americano matcha boba bubble es teh soda cola sprite fanta
    jus smoothie milkshake
    """.split()
    )

    # Helper regex patterns
    STAR_RE = re.compile("[⭐★]")
    NUM_RE = re.compile(r"([1-5])\s*/\s*5")
    WORD_RE = re.compile(r"(?i)bintang\s+([1-5])")
    SHOP_RE = re.compile(
        r"\b(?:di|at)\s+([A-Z][\w&\'\-\.]*(?:\s+[A-Z][\w&\'\-\.]*){0,3})"
    )
    tz = pytz.timezone("Asia/Jakarta")

    def clean(txt: str) -> str:
        """Clean text by removing URLs, mentions, hashtags"""
        txt = re.sub(r"http\S+|@\w+|#\w+", "", txt)  # hapus URL, mention, hashtag
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt

    def rating(txt: str):
        """Extract rating from text"""
        stars = len(STAR_RE.findall(txt))
        if 1 <= stars <= 5:
            return stars
        m = NUM_RE.search(txt) or WORD_RE.search(txt)
        return int(m.group(1)) if m else np.nan

    def produk(txt: str):
        """Extract product mentioned in text"""
        words = [w.lower().strip(string.punctuation) for w in txt.split()]
        for i, w in enumerate(words):
            if w in food_drink_terms:
                return w.title()
            # cek bigram
            if i < len(words) - 1:
                bigram = f"{w} {words[i+1]}"
                if all(x in food_drink_terms for x in bigram.split()):
                    return bigram.title()
        return np.nan

    def toko(txt: str):
        """Extract shop/store name"""
        m = SHOP_RE.search(txt)
        if m:
            return m.group(1).strip()
        ment = re.search(r"@(\w+)", txt)  # fallback username mention
        return ment.group(1) if ment else np.nan

    def tanggal(ts):
        """Convert timestamp to formatted date"""
        try:
            return (
                pd.to_datetime(ts, utc=True)
                .tz_convert(tz)
                .strftime("%d %B %Y %H:%M:%S")
            )
        except:
            return np.nan

    def transform(row):
        """Transform a tweet row into a review"""
        raw = str(row["full_text"])
        return pd.Series(
            {
                "Review": clean(raw),
                "Rating": rating(raw),
                "Produk": produk(raw),
                "Nama Toko": toko(raw),
                "Tanggal": tanggal(row["created_at"]),
            }
        )

    # Apply transformation to all tweets
    print("🔄 Applying transformation...")
    twitter_reviews = tweets.apply(transform, axis=1)

    # Save the transformed data
    twitter_reviews.to_csv(output_file, index=False)
    print(f"✅ Transformation complete! Output saved to: {output_file}")

    return twitter_reviews

def scrap_gofood(url, total_merch, total_reviews_page):

    chrome_options = ChromeOptions()
    ua = UserAgent()
    user_agent = ua.random
    chrome_options.add_argument(f"--user-agent-{user_agent}")
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
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    data = [] 

    container = soup.find('div', class_='my-6 grid grid-cols-1 md:grid-cols-2 md:gap-6 lg:grid-cols-4 lg:gap-6 -mx-6 md:mx-0')

    if container:
        links = container.find_all('a', href=True)
        hrefs = ['https://gofood.co.id' + a['href'] for a in links]

        for href in hrefs[:total_merch]:
            try:
                driver.get(href)
                time.sleep(10)

                review_url = driver.current_url + '/reviews'
                driver.get(review_url)
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'What people say') or contains(text(), 'All reviews')]")))
                time.sleep(10)

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

def upload_s3(df, file_name):
    s3 = boto3.client('s3')
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.put_object(Bucket='rdv-bucket-project', Key=f"{file_name}", Body=csv_buffer.getvalue())
    
def lambda_process(event, context):

    gofood_review = scrap_gofood(url = 'https://gofood.co.id/en/malang/restaurants/best_seller', 
                                 total_merch = 10, 
                                 total_reviews_page = 3)

    if not gofood_review.empty:
        upload_s3(gofood_review, 'review_gofood.csv')
        return {'statusCode': 200, 'body': 'Data uploaded successfully'}
    else:
        return {'statusCode': 500, 'body': 'No data scraped.'}

def upload_s3(df, file_name):
    s3 = boto3.client('s3')
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.put_object(Bucket='rdv-bucket-project', Key=f"{file_name}", Body=csv_buffer.getvalue())
    print(f'Uploaded {file_name} to S3 Buckets')

def lambda_process(event, context):
    """Main Lambda function handler"""
    print("🚀 Starting scraping process...")
    try:
        # Scrape GoFood
        gofood_review = scrap_gofood(
            url='https://gofood.co.id/en/malang/restaurants/best_seller', 
            total_merch=10, 
            total_reviews_page=3
        )
        
        if not gofood_review.empty:
            upload_s3(gofood_review, 'review_gofood.csv')
        else:
            print("⚠️ No GoFood data scraped")
        
        # Scrape Twitter
        twitter_auth_token = "980a94062ac48817cb293d8dc1e55c99494c05a5"
        twitter_file = scrape_twitter(
            twitter_auth_token=twitter_auth_token,
            filename="crawl-raw.csv",
            search_keyword="makanan di malang",
            limit=400
        )
        
        twitter_reviews = transform_tweets(twitter_file, "twitter_reviews.csv")
        
        if not twitter_reviews.empty:
            upload_s3(twitter_reviews, 'twitter_reviews.csv')
        else:
            print("No Twitter data scraped")
            
        return {
            'statusCode': 200,
            'body': 'Data scraping and upload completed successfully'
        }
        
    except Exception as e:
        logging.error(f"Error in lambda_process: {str(e)}")
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

def main():
    """Main function for local testing"""
    print("Food Review Scraper")
    print("=" * 60)
    
    # Run the Lambda handler (for testing)
    lambda_process({}, {})

if __name__ == "__main__":
    main()