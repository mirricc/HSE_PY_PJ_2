# HSE_PY_PJ_2
# Дополнительная функциональность:
# Демонстрация работы 
1. **Графики:**
   <img width="1280" height="771" alt="image" src="https://github.com/user-attachments/assets/d64c264d-6193-48ae-959f-09cad9525e2f" />
2.  **Рекомендации по ккал:** 
  <img width="1280" height="319" alt="image" src="https://github.com/user-attachments/assets/5a407697-49ca-44b9-bfce-cf282ff9e8c9" />
  <img width="1280" height="747" alt="image" src="https://github.com/user-attachments/assets/49755a6a-81f7-4f1d-a16e-f404ca4ad971" />
3. Продвинутое определение калорийности:
   
   - Улучшенный запрос: без лишних пробелов, с фильтрацией по стране и языку
   - Получаем несколько вариантов для выбора лучшего
   - Ищем лучший результат: с калориями и на русском языке
   - Получаем калории из разных возможных полей запроса
```
def get_food_info(product_name: str) -> Optional[Dict[str, Any]]:
    try:
        encoded_name = urllib.parse.quote(product_name.strip())
        url = (
            f"https://world.openfoodfacts.org/cgi/search.pl?"
            f"action=process&"
            f"search_terms={encoded_name}&"
            f"json=1&"
            f"page_size=3"
        )
        response = requests.get(url, timeout=8)
        if response.status_code != 200:
            return None
        
        data = response.json()
        products = data.get('products', [])
        
        for product in products:
            # Получаем название на русском или английском
            name = (
                product.get('product_name_ru') or 
                product.get('product_name') or 
                'Неизвестный продукт'
            ).strip()
            
            nutriments = product.get('nutriments', {})
            calories = (
                nutriments.get('energy-kcal_100g') or
                nutriments.get('energy_100g', 0) / 4.184 or 
                0
            )
            
            if calories > 0 and name and name.lower() != 'unknown':
                serving_size = product.get('serving_size', '100г')
                
                return {
                    'name': name.capitalize(),
                    'calories': round(float(calories), 1),
                    'serving_size': serving_size
                }
        
        return None
    except Exception:
        return None
```
<img width="1280" height="1045" alt="image" src="https://github.com/user-attachments/assets/0b458bfb-170a-44d5-a4dc-11c60a7ad616" />
<img width="1280" height="1057" alt="image" src="https://github.com/user-attachments/assets/c627d198-5183-4075-ada8-10431f3dc550" />
<img width="1280" height="540" alt="image" src="https://github.com/user-attachments/assets/98926552-0f92-483d-8736-3d8784d8c2d3" />
<img width="1280" height="945" alt="image" src="https://github.com/user-attachments/assets/b20e646c-f59b-43f6-a58c-fe1fe7e18eed" />
<img width="1280" height="809" alt="image" src="https://github.com/user-attachments/assets/69824391-583d-49ff-9bb8-b9bdedcba554" />
<img width="1280" height="1108" alt="image" src="https://github.com/user-attachments/assets/3f69abb2-ae13-4255-92a8-45711b5bddef" />
<img width="1280" height="771" alt="image" src="https://github.com/user-attachments/assets/30c6bd5e-62e9-4f48-aefd-48b29efb22ec" />
<img width="1280" height="1021" alt="image" src="https://github.com/user-attachments/assets/cbb9428c-767e-4a9e-84cb-d733b4a99a2d" />
<img width="1280" height="319" alt="image" src="https://github.com/user-attachments/assets/5ab910de-e33e-4902-9453-d99d7767c2c7" />
<img width="1280" height="753" alt="image" src="https://github.com/user-attachments/assets/630ca5f6-eee1-46fd-866c-fe772184083f" />
<img width="1280" height="747" alt="image" src="https://github.com/user-attachments/assets/0698092b-f8d4-4586-94ca-6e8a5cc5b74f" />
# Демонстрация деплоя 
<img width="1280" height="820" alt="image" src="https://github.com/user-attachments/assets/8f814939-885b-4c97-aafb-866a9a0e19ab" />
<img width="1280" height="524" alt="image" src="https://github.com/user-attachments/assets/53f94e07-a869-4b96-a09e-0c83eaa3ee3b" />
<img width="1280" height="506" alt="image" src="https://github.com/user-attachments/assets/ee0e2026-75e6-44ce-8c02-c30ae20e663a" />
<img width="1280" height="298" alt="image" src="https://github.com/user-attachments/assets/2900fce5-60eb-4000-b8ad-2828f54ecb6b" />
## При этом логи приложения не аиссались на сайте, хотя локально все работает
<img width="1280" height="493" alt="image" src="https://github.com/user-attachments/assets/3581432c-43a3-4355-ae79-1d9dd5310af5" />
