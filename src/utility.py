import json
import time
import re

import pandas as pd
from io import BytesIO

from datetime import datetime

from typing import List, Tuple

from selenium.webdriver import Chrome


def parse_id_from_url(product_url: str) -> str | None:
    patterns = [
        r'-(\d+)/\?at',
        r'-(\d+)/'
    ]

    match = re.search(patterns[0], product_url)

    if match:
        return match.group(1)
    
    match = re.search(patterns[1], product_url)
    if match:
        return match.group(1)
    
    return None

def scrolldown(driver: Chrome, deep: int, scroll: int = 500) -> None:
    for _ in range(deep):
        driver.execute_script(f'window.scrollBy(0, {scroll})')
        time.sleep(0.1)

def activate_javascript(driver: Chrome) -> None:
    activation_scripts = [
        "setTimeout(function(){}, 100);",
        "setInterval(function(){}, 1000);",
        
        "window.dispatchEvent(new Event('load'));",
        "window.dispatchEvent(new Event('resize'));",
        "window.dispatchEvent(new Event('focus'));",
        
        "document.dispatchEvent(new Event('DOMContentLoaded'));",
        "document.dispatchEvent(new Event('readystatechange'));",
        
        "window.scrollBy(0, 1);",
        "window.dispatchEvent(new Event('scroll'));"
    ]
    
    for script in activation_scripts:
        try:
            driver.execute_script(script)
        except:
            pass

def preload_activation(driver: Chrome) -> None:
    init_script = """
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(function(){}, 100);
        setInterval(function(){}, 1000);
        
        window.dispatchEvent(new Event('load'));
        window.dispatchEvent(new Event('resize'));
    });
    
    setTimeout(function(){}, 50);
    """
    
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": init_script
    })

def convert_to_json(product_list: List[List[Tuple[str, str, str, str]]]) -> str:
    result = {
        "products": [],
        "total_layers": len(product_list),
        "total_products": sum(len(layer) for layer in product_list)
    }
    
    for layer_index, layer in enumerate(product_list):
        layer_data = {
            "layer_index": layer_index,
            "products_in_layer": len(layer),
            "items": []
        }
        
        for product_index, (name, price, product_id, url) in enumerate(layer):
            product_data = {
                "id": f"layer_{layer_index}_product_{product_index}",
                "product_id": product_id,
                "name": name,
                "price": price,
                "url": url,
                "layer": layer_index,
                "position": product_index
            }
            layer_data["items"].append(product_data)
        
        result["products"].append(layer_data)
    
    return json.dumps(result, ensure_ascii=False, indent=2)

def convert_to_simple_json(product_list: List[List[Tuple[str, str, str, str]]]) -> str:
    all_products = []
    
    for layer_index, layer in enumerate(product_list):
        for product_index, (name, price, product_id, url) in enumerate(layer):
            product_data = {
                "json_id": f"{layer_index}_{product_index}",
                "product_id": product_id,
                "name": name,
                "price": price,
                "url": url,
                "original_layer": layer_index
            }
            all_products.append(product_data)
    
    result = {
        "products": all_products,
        "total_products": len(all_products)
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2)

def convert_to_excel(product_list: List[List[Tuple[str, str, str, str]]], filename: str = "products.xlsx") -> None:
    all_products = []
    
    for layer_index, layer in enumerate(product_list):
        for product_index, (name, price, product_id, url) in enumerate(layer):
            product_data = {
                "Слой": layer_index + 1,
                "Позиция в слое": product_index + 1,
                "Название товара": name,
                "Цена": price,
                "ID товара": product_id,
                "Ссылка": url
            }
            all_products.append(product_data)
    
    df = pd.DataFrame(all_products)
    df.to_excel(f"{filename}.xlsx", index=False, engine='openpyxl')

def parse_widgetstates_to_excel(json_str):
    data = json.loads(json_str)
    widget_states = data.get('widgetStates', {})
    
    all_data = []
    for state_data in widget_states.values():
        state_obj = json.loads(state_data)
        
        if 'sellers' in state_obj:
            for seller in state_obj['sellers']:
                delivery_date = None
                if 'advantages' in seller:
                    for advantage in seller['advantages']:
                        if advantage.get('key') == 'delivery':
                            content = advantage.get('contentRs', {}).get('headRs', [{}])[0]
                            if content.get('type') == 'text':
                                delivery_text = content.get('content', '')
                                date_match = re.search(r'\d{1,2}\s+\w+', delivery_text)
                                if date_match:
                                    delivery_date = date_match.group()
                
                row = {
                    'seller_id': seller.get('id'),
                    'seller_link': seller.get('link'),
                    'sku': seller.get('sku'),
                    'price': seller.get('price', {}).get('cardPrice', {}).get('price'),
                    'delivery_date': delivery_date,
                    'product_link': seller.get('productLink')
                }
                all_data.append(row)
    
    df = pd.DataFrame(all_data)
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    return output

def create_table(json_data: str, file_mark: str = ""):
    excel_file = parse_widgetstates_to_excel(json_data)

    current_time = datetime.now().strftime("%Y-%m-%d")
    filename = f'delivery_dates_{current_time}.xlsx'

    with open(f'{file_mark}_{filename}', 'w+b') as f:
        f.write(excel_file.getvalue())
