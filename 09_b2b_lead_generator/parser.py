import json
import re
import sys
from pathlib import Path
import requests
import ollama

BASE_DIR = Path(__file__).resolve().parent
WEBHOOK_URL = "http://localhost:5678/webhook/leads"


def extract_contacts(text: str) -> tuple[list[str], list[str]]:
    phones = re.findall(r'\+?\d[\d\s\-\(\)]{8,14}\d', text)
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return list(set(phones)), list(set(emails))


def calculate_priority(employees: int, has_catering: bool) -> str:
    """
    Жесткая бизнес-логика из ТЗ.
    """
    if employees > 500 and not has_catering:
        return "AAA"
    elif 200 <= employees <= 500:
        return "A"
    elif 100 <= employees < 200 and has_catering:
        return "B"
    else:
        return "C"


def main():
    output_file = BASE_DIR / "leads.json"
    existing_leads = []
    
    if output_file.exists():
        with output_file.open("r", encoding="utf-8") as f:
            try:
                existing_leads = json.load(f)
            except json.JSONDecodeError:
                pass
                
    # Для дедупликации используем ИНН
    existing_inns = {lead.get("inn") for lead in existing_leads if lead.get("inn")}
    
    # Эмуляция данных, которые мы якобы спарсили
    scraped_data = [
        {
            "company": "ООО ФармЛогистик", 
            "inn": "7701234567",
            "description": "Крупный складской комплекс. 600 сотрудников.",
            "text": "Контакты: +7 999 111-22-33, info@farmlog.ru", 
            "employees": 600, 
            "has_catering": False
        },
        {
            "company": "ИП Иванов", 
            "inn": "7707654321",
            "description": "Мелкий ремонт обуви. 5 сотрудников.",
            "text": "Контакты: +7 999 123-45-67, mail@example.com",
            "employees": 5, 
            "has_catering": True
        },
        {
            "company": "ИП Петров", 
            "inn": "7707657777",
            "description": "Мелкий ремонт обуви. 99 сотрудников.",
            "text": "Контакты: +7 999 123-7777, mail@mail.com",
            "employees": 99, 
            "has_catering": True
        },
        {
            "company": "ИП Анаконда", 
            "inn": "7707657788",
            "description": "Мелкий ремонт обуви. 199 сотрудников.",
            "text": "Контакты: +7 999 123-7788, mail@mail.com",
            "employees": 199, 
            "has_catering": True
        },
        {
            "company": "ООО ФармЛогистик Дубль", 
            "inn": "7701234567", # Тот же ИНН
            "description": "Дубль компании.",
            "text": "",
            "employees": 600, 
            "has_catering": False
        }
    ]

    new_leads = []
    duplicates_count = 0
    print("Запускаем сбор и анализ компаний...")
    
    for comp in scraped_data:
        inn = comp['inn']
        
        if inn in existing_inns:
            print(f"\nКомпания с ИНН {inn} уже есть в базе. Пропускаем.")
            duplicates_count += 1
            continue
            
        print(f"\nОбрабатываем: {comp['company']}")
        
        phones, emails = extract_contacts(comp['text'])
        priority = calculate_priority(comp['employees'], comp['has_catering'])
        
        new_lead = {
            "company": comp['company'],
            "inn": inn,
            "description": comp['description'],
            "employees": comp['employees'],
            "has_catering": comp['has_catering'],
            "phones": phones,
            "emails": emails,
            "priority": priority
        }
        new_leads.append(new_lead)
        existing_inns.add(inn)
        print(f"  -> Категория: {priority}")

    # Формируем отчет для ответственного лица
    report = {
        "new_records": len(new_leads),
        "duplicates": duplicates_count,
        "total_unique_companies": len(existing_inns),
        "leads": new_leads
    }

    if new_leads:
        print(f"\nОтправляем отчет и лиды в n8n...")
        try:
            response = requests.post(WEBHOOK_URL, json=report)
            if response.status_code == 200:
                print("Успех! Данные отправлены в n8n.")
                # Сохраняем локально только если n8n принял данные
                existing_leads.extend(new_leads)
                with output_file.open("w", encoding="utf-8") as f:
                    json.dump(existing_leads, f, ensure_ascii=False, indent=2)
                print(f"Данные сохранены локально: {output_file}")
            else:
                print(f"n8n ответил с ошибкой: {response.status_code}. Данные не сохранены.")
        except Exception as e:
            print(f"Не удалось подключиться к n8n: {e}")
    else:
        print("\nНовых компаний нет.")

if __name__ == "__main__":
    main()