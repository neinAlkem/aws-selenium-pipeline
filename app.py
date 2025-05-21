<<<<<<< HEAD
#!/usr/bin/env python3
import os
import re
import string
import subprocess
import sys
import numpy as np
import pandas as pd
import pytz
import datetime as dt


def install_dependencies():
    """Install all required dependencies for the application"""
    print("📦 Installing dependencies...")

    # Install Python packages
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas"])

    # Install Node.js if not installed
    try:
        node_version = subprocess.check_output(["node", "-v"]).decode().strip()
        print(f"✓ Node.js already installed: {node_version}")
    except:
        print("📥 Installing Node.js...")
        subprocess.check_call(["sudo", "apt-get", "update"])
        subprocess.check_call(
            ["sudo", "apt-get", "install", "-y", "ca-certificates", "curl", "gnupg"]
        )
        subprocess.check_call(["sudo", "mkdir", "-p", "/etc/apt/keyrings"])

        subprocess.check_call(
            "curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg",
            shell=True,
        )
        subprocess.check_call(
            'NODE_MAJOR=20 && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list',
            shell=True,
        )

        subprocess.check_call(["sudo", "apt-get", "update"])
        subprocess.check_call(["sudo", "apt-get", "install", "nodejs", "-y"])

        node_version = subprocess.check_output(["node", "-v"]).decode().strip()
        print(f"✓ Node.js installed: {node_version}")


def scrape_twitter(twitter_auth_token, filename, search_keyword, limit):
    """Scrape tweets using tweet-harvest"""
    print(f"🔍 Scraping Twitter for: '{search_keyword}'")
    print(f"📝 Will save {limit} tweets to: {filename}")

    cmd = f'npx -y tweet-harvest@2.6.1 -o "{filename}" -s "{search_keyword}" --tab "LATEST" -l {limit} --token {twitter_auth_token}'
    subprocess.check_call(cmd, shell=True)

    # Check if file exists in tweets-data directory
    expected_path = f"tweets-data/{filename}"
    if os.path.exists(expected_path):
        print(f"✓ Tweets saved to: {expected_path}")
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
    print(f"🔄 Transforming tweets from: {input_file}")

    # Read the CSV file
    try:
        tweets = pd.read_csv(input_file)
        print(f"✓ Loaded {len(tweets)} tweets")
    except Exception as e:
        print(f"⚠️ Error loading tweets file: {e}")
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
        r"\b(?:di|at)\s+([A-Z][\w&\'\-\.]*(?    :\s+[A-Z][\w&\'\-\.]*){0,3})"
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
    print("Applying transformation...")
    twitter_reviews = tweets.apply(transform, axis=1)

    # Save the transformed data
    twitter_reviews.to_csv(output_file, index=False)
    print(f"Transformation complete! Output saved to: {output_file}")

    return twitter_reviews


def main():
    """Main application function"""
    print("Twitter Food Review Scraper & Transformer 🍜")
    print("=" * 60)

    # Configuration
    twitter_auth_token = (
        "980a94062ac48817cb293d8dc1e55c99494c05a5"  # change this auth token
    )
    filename = "crawl-raw.csv"
    search_keyword = "makanan di malang"
    limit = 400
    output_file = "twitter_reviews_transformed.csv"

    # Step 1: Install dependencies
    install_dependencies()

    # Step 2: Scrape Twitter
    try:
        input_file = scrape_twitter(twitter_auth_token, filename, search_keyword, limit)
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        return

    # Step 3: Transform data
    try:
        reviews = transform_tweets(input_file, output_file)

        # Display summary stats
        print("\n📊 Summary of transformed data:")
        print(f"Total reviews: {len(reviews)}")
        print(
            f"Reviews with ratings: {reviews['Rating'].count()} ({reviews['Rating'].count()/len(reviews)*100:.1f}%)"
        )
        print(
            f"Reviews with product identified: {reviews['Produk'].count()} ({reviews['Produk'].count()/len(reviews)*100:.1f}%)"
        )
        print(
            f"Reviews with store identified: {reviews['Nama Toko'].count()} ({reviews['Nama Toko'].count()/len(reviews)*100:.1f}%)"
        )

        # Show sample of results
        print("\n📑 Sample of transformed reviews:")
        print(reviews.head().to_string())

    except Exception as e:
        print(f"❌ Error during transformation: {e}")
        return

    print("\n✨ All done! You can find your reviews in the file:", output_file)
=======
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import time
import random
import pandas as pd
import numpy as np
import re
import string
import pytz
from datetime import datetime, timezone, timedelta

# Konfigurasi Crawling
TWITTER_EMAIL = "rahasia@gmail.com"
TWITTER_USERNAME = "@rahasia"
TWITTER_PASSWORD = "rahasia"


keyword = "makanan di malang"
jumlah_tweet = 10
tanggal_mulai = "2024-05-01"
tanggal_akhir = "2025-05-01"

# Konfigurasi Transformasi
food_drink_terms = set(
    """
bakso sate soto rawon pecel nasi goreng ayam goreng ayam geprek
mie ayam mie ayam geprek indomie ramen udon sushi sashimi pizza burger
kebab shawarma rendang gudeg lalapan dimsum siomay batagor lumpia martabak
roti kue brownies cheesecake croissant donat waffle pancake puding eskrim gelato
kopi latte cappuccino espresso americano matcha boba bubble es  teh soda cola sprite fanta
jus smoothie milkshake
""".split()
)

# Helper Regex untuk transformasi
STAR_RE = re.compile("[⭐★]")
NUM_RE = re.compile(r"([1-5])\s*/\s*5")
WORD_RE = re.compile(r"(?i)bintang\s+([1-5])")
SHOP_RE = re.compile(r"\b(?:di|at)\s+([A-Z][\w&\'\-\.]*(?:\s+[A-Z][\w&\'\-\.]*){0,3})")
tz = pytz.timezone("Asia/Jakarta")


# Setup Chrome Driver
def setup_driver():
    options = Options()
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)


# Fungsi login
def login_twitter(driver):
    driver.get("http://twitter.com/login")
    time.sleep(5)
    email_input = driver.find_element(By.NAME, "text")
    email_input.send_keys(TWITTER_EMAIL)
    email_input.send_keys(Keys.RETURN)
    time.sleep(3)
    username_input = driver.find_element(By.NAME, "text")
    username_input.send_keys(TWITTER_USERNAME)
    username_input.send_keys(Keys.RETURN)
    time.sleep(3)
    password_input = driver.find_element(By.NAME, "password")
    password_input.send_keys(TWITTER_PASSWORD)
    password_input.send_keys(Keys.RETURN)
    time.sleep(5)


# Fungsi untuk crawling tweets
def crawl_tweets(driver, keyword, jumlah_tweet, tanggal_mulai, tanggal_akhir):
    # Membuat query pencarian
    query = f"{keyword} since:{tanggal_mulai} until:{tanggal_akhir} lang:id"
    search_url = f"https://x.com/search?q={query}&src=typed_query"
    driver.get(search_url)
    time.sleep(5)

    # Persiapan penyimpanan data
    tweets_data = set()
    tweets = []
    last_position = driver.execute_script("return window.pageYOffset;")
    scroll_attempt = 0

    # Loop untuk mendapatkan tweet
    while len(tweets) < jumlah_tweet:
        try:
            elements = driver.find_elements(By.XPATH, '//article[@data-testid="tweet"]')
            for el in elements:
                try:
                    konten = el.text
                    if konten not in tweets_data:
                        tweets_data.add(konten)
                        # Ambil username
                        username = el.find_element(
                            By.XPATH, ".//div[@data-testid='User-Name']//span"
                        ).text
                        # Ambil hanya teks tweet
                        tweet_text_elements = el.find_elements(
                            By.XPATH, ".//div[@data-testid='tweetText']//span"
                        )
                        full_text = " ".join(
                            [
                                span.text
                                for span in tweet_text_elements
                                if span.text.strip() != ""
                            ]
                        )
                        # Ambil waktu dan konversi ke WIB
                        waktu_utc = el.find_element(By.XPATH, ".//time").get_attribute(
                            "datetime"
                        )
                        try:
                            waktu_utc = waktu_utc.replace("Z", "+00:00")
                            waktu_obj = datetime.fromisoformat(waktu_utc)
                            waktu_wib = waktu_obj + timedelta(hours=7)
                            waktu_str = waktu_wib.strftime("%d-%m-%Y %H:%M")
                        except ValueError:
                            waktu_str = datetime.now().strftime("%d-%m-%Y %H:%M")
                        # Simpan data
                        tweets.append(
                            {
                                "username": username,
                                "tweet": full_text,
                                "waktu": waktu_str,
                            }
                        )
                        print(
                            f"Mendapatkan tweet ke-{len(tweets)}: {full_text[:50]}..."
                        )
                        if len(tweets) >= jumlah_tweet:
                            break
                except Exception as e:
                    print(f"Gagal memproses satu tweet: {str(e)}")
                    continue
            # Scroll down untuk memuat lebih banyak tweet
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 4))
            # Cek apakah scroll berhasil
            new_position = driver.execute_script("return window.pageYOffset;")
            if new_position == last_position:
                scroll_attempt += 1
                if scroll_attempt >= 3:  # Coba scroll 3 kali sebelum berhenti
                    print(
                        "Tidak bisa scroll lebih jauh, mungkin sudah mencapai akhir halaman"
                    )
                    break
            else:
                scroll_attempt = 0
                last_position = new_position
        except Exception as e:
            print(f"Error utama: {str(e)}")
            break

    return tweets


# Fungsi helper untuk transformasi
def clean(txt: str) -> str:
    txt = re.sub(r"http\S+|@\w+|#\w+", "", txt)  # hapus URL, mention, hashtag
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def rating(txt: str):
    stars = len(STAR_RE.findall(txt))
    if 1 <= stars <= 5:
        return stars
    m = NUM_RE.search(txt) or WORD_RE.search(txt)
    return int(m.group(1)) if m else np.nan


def produk(txt: str):
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
    m = SHOP_RE.search(txt)
    if m:
        return m.group(1).strip()
    ment = re.search(r"@(\w+)", txt)  # fallback username mention
    return ment.group(1) if ment else np.nan


def tanggal(ts):
    try:
        return pd.to_datetime(ts, utc=True).tz_convert(tz).strftime("%d %B %Y %H:%M:%S")
    except:
        return np.nan


def transform(row):
    raw = str(row["tweet"])
    return pd.Series(
        {
            "Review": clean(raw),
            "Rating": rating(raw),
            "Produk": produk(raw),
            "Nama Toko": toko(raw),
            "Tanggal": tanggal(row["waktu"]),
        }
    )


# Fungsi utama yang menggabungkan crawling dan transformasi
def main():
    print("=== Memulai Crawling Twitter ===")
    driver = setup_driver()

    try:
        print("Login ke Twitter...")
        login_twitter(driver)

        print(
            f"Mencari tweet tentang '{keyword}' dari {tanggal_mulai} sampai {tanggal_akhir}..."
        )
        tweets = crawl_tweets(
            driver, keyword, jumlah_tweet, tanggal_mulai, tanggal_akhir
        )

        # Simpan hasil crawling ke CSV
        df_tweets = pd.DataFrame(tweets)
        df_tweets.to_csv("hasil_tweet_bersih.csv", index=False)
        print(f"Berhasil menyimpan {len(tweets)} tweet ke hasil_tweet_bersih.csv")

        # Transformasi data tweet
        print("\n=== Memulai Transformasi Data ===")
        twitter_reviews = df_tweets.apply(transform, axis=1)
        twitter_reviews.to_csv("twitter_reviews_transformed.csv", index=False)
        print("✅ Transformasi selesai → twitter_reviews_transformed.csv")

    except Exception as e:
        print(f"Terjadi kesalahan: {str(e)}")
    finally:
        # Tutup browser
        driver.quit()
>>>>>>> 7827e2bd5c7ad1978f8fceecefeacb46f6c57aee


if __name__ == "__main__":
    main()
