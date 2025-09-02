import re
import json
import time

from selenium.webdriver import Chrome
from bs4 import BeautifulSoup

from cfg import logging, init_webdriver
from utility import scrolldown, preload_activation, parse_id_from_url

from utility import convert_to_json
from utility import convert_to_excel, create_table



def parse_product_data(json_data):
    try:
        data = json.loads(json_data)
        
        widget_state = data.get('widgetStates', {})
        web_seller_key = None
        
        for key in widget_state.keys():
            if key.startswith('webSellerList-'):
                web_seller_key = key
                break
        
        if not web_seller_key:
            return []
        
        seller_data = json.loads(widget_state[web_seller_key])
        sellers = seller_data.get('sellers', [])
        
        results = []
        
        for seller in sellers:
            product_link = seller.get('productLink', '')

            price = None

            if 'price' in seller and 'cardPrice' in seller['price']:
                price = seller['price']['cardPrice'].get('price', '')

            elif 'price' in seller and 'price' in seller['price']:
                price = seller['price'].get('price', '')

            elif 'price' in seller and 'originalPrice' in seller['price']:
                price = seller['price'].get('originalPrice', '')

            if price:
                price = re.sub(r'[^\d₽]', '', price)
                price = price.replace(' ', ' ')
            
            results.append({
                'product_link': product_link,
                'price': price,
                'seller_name': seller.get('name', ''),
                'seller_id': seller.get('id', ''),
                'sku': seller.get('sku', '')
            })
        
        return results
        
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON: {e}")
        return []
    
    except Exception as e:
        print(f"Ошибка при обработке данных: {e}")
        return []

def get_mainpage_cards(driver: Chrome, url: str) -> list[list[tuple[str, str, str, str]]]:
    all_cards = list()
    driver.get(url)
    scrolldown(driver, 50)

    logging.info("Creating main_page_html")
    page_html = BeautifulSoup(driver.page_source, "html.parser")

    logging.info("Creating content")
    content = page_html.find("div", {"class": "container c"})
    content = content.findChildren(recursive=False)[-1].find("div")
    content = content.findChildren(recursive=False)
    content = [item for item in content if "island" in str(item)][-1]
    content = content.find("div").find("div").find("div").find_all("div", style=True)[1]
    content = content.findChildren(recursive=False)

    logging.info("Parsing content")
    
    for layer in content:
        layer_info = layer.find("div").find("div").find("div")
        cards = layer_info.findChildren(recursive=False)
        cards_in_layer = list()
        logging.info("Getting layer data")
        
        for card in cards:
            card = card.findChildren(recursive=False)
            
            for data in card:
                card_name = data.find("span", {"class": "tsBody500Medium"}).contents[0]
                card_url = data.find("a", href=True)["href"]
                card_price = data.findChildren(recursive=False)[-1].find("div").find("div").find(class_=re.compile(r'tsHeadline500Medium')).contents[0]
                product_url = "https://ozon.ru" + card_url
                cards_in_layer.append(f"{card_name}, {str(card_price).replace("\u2009", " ")}, {product_url}")
            
            all_cards.append(cards_in_layer)

    logging.info("Cards data get correctly")
    return all_cards

def get_search_cards(driver: Chrome, url: str, searching: str) -> list[list[tuple[str, str, str, str]]]:
    all_cards = list()
    pattern = r'-(\d+)/\?at'

    driver.get(f"{url}search/?text={searching}&from_global=true")
    scrolldown(driver, 50)
    
    page_html = BeautifulSoup(driver.page_source, "html.parser")
    content = page_html.find("div", {"class": "container c"})
    content = content.find_all(id="contentScrollPaginator")[-1]

    fixed = content.findChildren(recursive=False)[0] # Первые 12 карточек
    fixed = fixed.find_all(attrs={"data-widget": "tileGridDesktop"})

    for _ in fixed:
        card = _.findChildren(recursive=False)
        cards_in_layer = list()
        
        for fixed_data in card:
            try:
                card_id = re.search(pattern, str(fixed_data)).group(1)
                name_span = fixed_data.find("span", {"class": "tsBody500Medium"}).contents[0]
                link_a = fixed_data.find("a", href=True)["href"]
                price_element = fixed_data.find(class_=re.compile(r'tsHeadline500Medium')).contents[0]

                if (name_span and link_a and price_element):
                    product_url = "https://ozon.ru" + link_a
                    card_price = str(price_element).replace("\u2009", " ")
                    
                    cards_in_layer.append((name_span, card_price, card_id, product_url))
                    
                else:
                    logging.critical(f"Something missing in card data - {name_span}, {card_price}, {card_id}, {product_url}")
                    
            except Exception as e:
                logging.critical(f"Error processing card: {e}")
                continue
        
        all_cards.append(cards_in_layer)

    content = content.findChildren(recursive=False)[1] # Остальные карты
    content = content.find_all(attrs={"data-widget": "tileGridDesktop"})

    for _ in content:
        card = _.findChildren(recursive=False)
        cards_in_layer = list()
        
        for data in card:
            try:
                card_id = re.search(pattern, str(data)).group(1)
                name_span = data.find("span", {"class": "tsBody500Medium"}).contents[0]
                link_a = data.find("a", href=True)["href"]
                price_element = data.find(class_=re.compile(r'tsHeadline500Medium')).contents[0]

                if (name_span and link_a and price_element):
                    product_url = f" https://ozon.ru{link_a} "
                    card_price = str(price_element).replace("\u2009", " ")
                    
                    cards_in_layer.append((name_span, card_price, card_id, product_url))
                    
                else:
                    logging.critical(f"Something missing in card data - {name_span}, {card_price}, {card_id}, {product_url}")
                    
            except Exception as e:
                logging.critical(f"Error processing card: {e}")
                continue
        
        all_cards.append(cards_in_layer)
    return all_cards

def get_cheaper_cards(driver: Chrome, url: str, url_id: str, file_mark: str = "") -> None:
    preload_activation(driver)
    data = parse_id_from_url(url_id)

    if data:
        driver.get(f"{url}api/entrypoint-api.bx/page/json/v2?url=%2Fmodal%2FotherOffersFromSellers%3Fproduct_id%3D{data}%26page_changed%3Dtrue")

    elif data == None:
        driver.get(f"{url}api/entrypoint-api.bx/page/json/v2?url=%2Fmodal%2FotherOffersFromSellers%3Fproduct_id%3D{url_id}%26page_changed%3Dtrue")
    
    else:
        print("You must input product id or product url")
        raise ValueError
    
    scrolldown(driver, 2)

    try:
        page_html = BeautifulSoup(driver.page_source , "html.parser")
        json_data = page_html.find("pre")

        if json_data.text and "widgetStates" in json_data.text: 
            return create_table(json_data.text, file_mark)
        else:
            print(f"This product don`t have any other sellers: {url_id}")
            return None
    
    except AttributeError as e:
        with open('AttributeError.txt', 'w+', encoding="utf-8") as f:
            f.write(f"{e=}\n\n{str(e.__traceback__)}")
        raise AttributeError
    

if __name__ == "__main__":
    try:
        url_Ozon = "https://www.ozon.ru/"
        driver = init_webdriver()
        logging.info("Initiating web_driwer...")
        time.sleep(10)

        command = input(
            """Выберите комманду: 
            \n0 - Поиск+Парсинг карточек по названию. 
            \n1 - Парсинг вариантов дешевле, по url/id товара.
            \n2 - Парсинг вариантов дешевле, по url/id товара (Списком).
            \n3 - Поиск+Парсинг вариантов дешевле по названию.
            \n"""
        )

        if command == "0":
            logging.info("Trying get cards data")
            searching = input("Введите поисковый запрос: ")

            search_cards = get_search_cards(driver, url_Ozon, searching)
            convert_to_excel(search_cards, searching)

        elif command == "1":
            logging.info("Trying get cheaper products")
            url_id = input("Введите url или id товара: ")
            get_cheaper_cards(driver, url_Ozon, url_id)

        elif command == "2":
            file_mark = 0

            data = input("Введите url или id товара разделяя их пробелом: ")
            list_url_id = data.split(" ")

            for url_id in list_url_id:
                logging.info(f"Trying get cheaper products - {file_mark}")
                time.sleep(10)
                get_cheaper_cards(driver, url_Ozon, url_id, file_mark)
                file_mark += 1
        
        elif command == "3":
            logging.info("Trying get cards data")
            file_mark = 0

            searching = input("Введите поисковый запрос: ")
            search_Cards = get_search_cards(driver, url_Ozon, searching)
            convert_to_excel(search_Cards, searching)

            list_url_id = []
            for layer in search_Cards:
                for card in layer:
                    list_url_id.append(card[2])

            for url_id in list_url_id:
                logging.info(f"Trying get cheaper products - {file_mark}")
                time.sleep(10)
                get_cheaper_cards(driver, url_Ozon, url_id, file_mark)
                file_mark += 1

    except Exception as e:
        logging.error(f"Error while: {e}")
        raise

    except ValueError as e:
        logging.error(f"Value incorrect: {e}")
        raise

    except AttributeError as e:
        logging.error(f"Attribute error: {e}")

    except KeyboardInterrupt:
        print("___Close___")

    finally:
        driver.quit()
