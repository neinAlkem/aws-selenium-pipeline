import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from fake_useragent import UserAgent
import time
import logging
import argparse

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
                        time.sleep(10)
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

    df = pd.DataFrame(data)
    print(df.head())
    df.to_csv('gofood_reviews.csv', index=False)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', type=str, required=True, help='URL of GoFood Grouping \n Example: https://gofood.co.id/en/malang/restaurants/best_seller' )
    parser.add_argument('--total_merch', type=int, required=True, help='Total merchant \n Example: 10')
    parser.add_argument('--total_reviews_page', type=int, required=True, help='Total reviews load pages \n Example: 3')
    args = parser.parse_args()

    scrap_gofood(args.url, args.total_merch, args.total_reviews_page)

if __name__=="__main__":
      main()
