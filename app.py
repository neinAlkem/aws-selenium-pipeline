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


if __name__ == "__main__":
    main()
