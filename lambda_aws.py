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


logging.basicConfig(level=logging.DEBUG, format='$(asctime)s - $(levelname)s - $(message)s')

def scrap_gofood(url, total_merch, total_reviews_page):


    service = Service(
         executable_path="/opt/chrome-driver/chromedriver-linux64/chromedriver",
         service_log_path="/tmp/chromedriver.log"
     )

    options = webdriver.ChromeOptions()
    options.binary_location = "/opt/chrome/chrome-linux64/chrome"
    options.add_argument('--start-maximized')
    options.add_argument('--user-agent="Mozilla/5.0 (Windows Phone 10.0; Android 4.2.1; Microsoft; Lumia 640 XL LTE) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Mobile Safari/537.36 Edge/12.10166"')
    driver = webdriver.Chrome( service=service, options=options)
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
