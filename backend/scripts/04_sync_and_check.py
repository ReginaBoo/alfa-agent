# # backend/scripts/04_sync_and_check.py

# #!/usr/bin/env python3
# """
# ПОЛНАЯ ПРОВЕРКА СИСТЕМЫ

# Запуск: python scripts/04_sync_and_check.py

# Этапы проверки:
# 1. ✅ Доступность бэкенда и БД
# 2. ✅ Авторизация
# 3. ✅ Синхронизация проектов
# 4. ✅ Синхронизация статусов
# 5. ✅ Синхронизация задач
# 6. ✅ Проверка данных в БД
# 7. ✅ Проверка метрик (Workload Index, SLA, Health Score)
# 8. ✅ Проверка дашборда
# 9. ✅ Проверка Activity Trends
# 10. ✅ Итоговый отчёт
# """

# import requests
# import sys
# import time
# import os
# import json
# from datetime import datetime
# from typing import Dict, List, Optional, Tuple

# sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# from config import BACKEND_URL


# class Colors:
#     GREEN = '\033[92m'
#     RED = '\033[91m'
#     YELLOW = '\033[93m'
#     BLUE = '\033[94m'
#     CYAN = '\033[96m'
#     MAGENTA = '\033[95m'
#     RESET = '\033[0m'
#     BOLD = '\033[1m'


# def print_success(msg: str): print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")
# def print_error(msg: str): print(f"{Colors.RED}❌ {msg}{Colors.RESET}")
# def print_warning(msg: str): print(f"{Colors.YELLOW}⚠️ {msg}{Colors.RESET}")
# def print_info(msg: str): print(f"{Colors.BLUE}📌 {msg}{Colors.RESET}")
# def print_header(title: str): print(f"\n{Colors.CYAN}{'='*70}\n{Colors.BOLD}{title}{Colors.RESET}\n{Colors.CYAN}{'='*70}{Colors.RESET}")
# def print_subheader(title: str): print(f"\n{Colors.MAGENTA}▶ {title}{Colors.RESET}")
# def print_stat(name: str, value, unit: str = ""): print(f"   {name:<35} {value:>10} {unit}")


# def get_session_token() -> str:
#     """Получает session_token из файла"""
#     cookies_file = os.path.join(os.path.dirname(__file__), '.cookies.json')
    
#     if os.path.exists(cookies_file):
#         with open(cookies_file, 'r') as f:
#             cookies = json.load(f)
#             token = cookies.get('session_token', '')
#             if token:
#                 return token
    
#     token = os.environ.get('SESSION_TOKEN', '')
#     if token:
#         return token
    
#     print_warning("Не найден session_token")
#     print_info("1. Откройте браузер: http://localhost:8000/auth/login")
#     print_info("2. Авторизуйтесь через Atlassian")
#     print_info("3. Откройте DevTools (F12) → Application → Cookies → http://localhost:8000")
#     print_info("4. Скопируйте значение session_token")
    
#     token = input("\nВведите session_token: ").strip()
    
#     with open(cookies_file, 'w') as f:
#         json.dump({'session_token': token}, f)
    
#     return token


# def get_headers():
#     return {"Cookie": f"session_token={get_session_token()}", "Content-Type": "application/json"}


# def check_backend() -> bool:
#     """Проверка доступности бэкенда"""
#     print_subheader("1. Проверка бэкенда")
#     try:
#         r = requests.get(f"{BACKEND_URL}/health", timeout=10)
#         if r.status_code == 200:
#             print_success("Бэкенд доступен")
#             return True
#         print_error(f"Ошибка: {r.status_code}")
#         return False
#     except Exception as e:
#         print_error(f"Бэкенд недоступен: {e}")
#         return False


# def check_auth() -> Tuple[bool, Dict]:
#     """Проверка авторизации с возможностью обновить токен"""
#     print_subheader("2. Проверка авторизации")
    
#     max_attempts = 2
#     for attempt in range(max_attempts):
#         try:
#             r = requests.get(f"{BACKEND_URL}/auth/me", headers=get_headers(), timeout=10)
            
#             if r.status_code == 200:
#                 data = r.json()
#                 user = data.get('user', {})
#                 print_success(f"Авторизован: {user.get('name')} ({user.get('email')})")
                
#                 sites = data.get('sites', [])
#                 if sites:
#                     print_info(f"Доступные сайты: {', '.join([s['site_name'] for s in sites])}")
#                 return True, data
            
#             elif r.status_code == 401 and attempt == 0:
#                 print_error("Токен недействителен или истёк")
#                 print_warning("═══════════════════════════════════════════════════════════════════")
#                 print_warning("🔑 ПОЛУЧИТЕ НОВЫЙ SESSION_TOKEN:")
#                 print_warning("═══════════════════════════════════════════════════════════════════")
#                 print_info("1. Откройте браузер: http://localhost:8000/auth/login")
#                 print_info("2. Авторизуйтесь через Atlassian")
#                 print_info("3. Откройте DevTools (F12) → Application → Cookies → http://localhost:8000")
#                 print_info("4. Найдите cookie 'session_token' и скопируйте значение")
#                 print_warning("═══════════════════════════════════════════════════════════════════")
                
#                 new_token = input("\n📋 Вставьте новый session_token: ").strip()
#                 if new_token:
#                     # Сохраняем новый токен в файл
#                     cookies_file = os.path.join(os.path.dirname(__file__), '.cookies.json')
#                     with open(cookies_file, 'w') as f:
#                         json.dump({'session_token': new_token}, f)
#                     print_success("Новый токен сохранён, повторяем проверку...\n")
#                     continue
#                 else:
#                     print_error("Токен не введён")
#                     return False, {}
#             else:
#                 print_error(f"Ошибка: {r.status_code}")
#                 return False, {}
                
#         except Exception as e:
#             print_error(f"Ошибка: {e}")
#             return False, {}
    
#     print_error("Не удалось авторизоваться после нескольких попыток")
#     return False, {}


# def wait_for_job(job_id: str, timeout: int = 180) -> Tuple[bool, Dict]:
#     """Ожидание завершения фоновой задачи"""
#     print_info(f"Ожидание завершения (max {timeout} сек)...")
    
#     start = time.time()
#     dots = 0
    
#     while time.time() - start < timeout:
#         try:
#             r = requests.get(f"{BACKEND_URL}/job/{job_id}", headers=get_headers(), timeout=10)
#             if r.status_code == 200:
#                 data = r.json()
#                 status = data.get('data', {}).get('status', 'unknown')
                
#                 if status in ['finished', 'completed', 'success']:
#                     print()
#                     print_success("Задача выполнена")
#                     return True, data.get('data', {})
#                 elif status in ['failed', 'error']:
#                     print()
#                     error = data.get('data', {}).get('error', 'Unknown')
#                     print_error(f"Задача не удалась: {error}")
#                     return False, {}
#         except Exception:
#             pass
        
#         dots = (dots + 1) % 4
#         print(f"\r   Обработка...{'.' * dots}{' ' * (3 - dots)}", end="")
#         time.sleep(3)
    
#     print()
#     print_error("Таймаут ожидания")
#     return False, {}


# def sync_projects(instance_name: str) -> Tuple[bool, Dict]:
#     """Синхронизация проектов и статусов"""
#     print_subheader("3. Синхронизация проектов")
#     print_info(f"Instance: {instance_name}")
    
#     try:
#         r = requests.post(
#             f"{BACKEND_URL}/jira/projects/sync?instance_name={instance_name}&sync_statuses=true",
#             headers=get_headers(),
#             timeout=30
#         )
        
#         if r.status_code == 200:
#             data = r.json()
#             details = data.get('details', {})
#             print_success(f"Проектов синхронизировано: {details.get('total', 0)}")
#             print_stat("  Создано проектов", details.get('created', 0))
#             print_stat("  Обновлено проектов", details.get('updated', 0))
#             print_stat("  Статусов синхронизировано", details.get('statuses_synced', 0))
#             return True, details
#         else:
#             print_error(f"Ошибка: {r.status_code}")
#             return False, {}
#     except Exception as e:
#         print_error(f"Ошибка: {e}")
#         return False, {}


# def sync_issues(instance_name: str) -> Tuple[bool, Dict]:
#     """Синхронизация всех задач"""
#     print_subheader("4. Синхронизация задач")
#     print_info(f"Запуск синхронизации всех проектов...")
    
#     try:
#         r = requests.post(
#             f"{BACKEND_URL}/jira/sync-all-async?instance_name={instance_name}",
#             headers=get_headers(),
#             timeout=30
#         )
        
#         if r.status_code == 200:
#             data = r.json()
#             job_id = data.get('data', {}).get('job_id')
#             if job_id:
#                 print_success(f"Задача запущена: {job_id}")
#                 success, result = wait_for_job(job_id)
                
#                 if success:
#                     issues_data = result.get('details', {}).get('issues', {})
#                     print_stat("  Всего задач синхронизировано", issues_data.get('total', 0))
#                     print_stat("  Создано новых", issues_data.get('created', 0))
#                     print_stat("  Обновлено", issues_data.get('updated', 0))
#                     return True, result
#             return False, {}
#         else:
#             print_error(f"Ошибка: {r.status_code}")
#             return False, {}
#     except Exception as e:
#         print_error(f"Ошибка: {e}")
#         return False, {}


# def check_database() -> Tuple[bool, Dict]:
#     """Проверка данных в БД через API"""
#     print_subheader("5. Проверка данных в БД")
    
#     try:
#         # Проверяем дашборд (он показывает проекты из БД)
#         r = requests.get(f"{BACKEND_URL}/dashboard/digest?period=month", headers=get_headers(), timeout=30)
        
#         if r.status_code == 200:
#             data = r.json()
#             projects = data.get('data', {}).get('projects', [])
#             total_projects = len(projects)
            
#             print_success(f"Проектов в БД: {total_projects}")
            
#             # Собираем статистику по проектам
#             stats = {
#                 'total_projects': total_projects,
#                 'with_health': 0,
#                 'with_metrics': 0
#             }
            
#             for p in projects:
#                 if p.get('health'):
#                     stats['with_health'] += 1
#                 if p.get('metrics'):
#                     stats['with_metrics'] += 1
            
#             print_stat("  Проектов с Health Score", stats['with_health'])
#             print_stat("  Проектов с метриками", stats['with_metrics'])
            
#             return True, stats
#         else:
#             print_error(f"Ошибка: {r.status_code}")
#             return False, {}
#     except Exception as e:
#         print_error(f"Ошибка: {e}")
#         return False, {}


# def check_workload_index(project_keys: List[str]) -> Tuple[bool, Dict]:
#     """Проверка Workload Index"""
#     print_subheader("6. Проверка Workload Index")
    
#     params = "&".join([f"project_keys={pk}" for pk in project_keys[:3]])
#     url = f"{BACKEND_URL}/dashboard/team-workload?{params}&weeks=4"
    
#     try:
#         r = requests.get(url, headers=get_headers(), timeout=30)
#         if r.status_code == 200:
#             data = r.json()
#             projects = data.get('projects', [])
            
#             print_success(f"WI получен для {len(projects)} проектов")
            
#             for p in projects:
#                 name = p.get('project_key', '?')
#                 wi = p.get('team_wi_percent', 0)
#                 status = p.get('status_text', '?')
#                 balance = p.get('balance', 0)
#                 balance_alert = "⚠️" if p.get('balance_alert') else ""
                
#                 print(f"   {name:<12} WI: {wi:>6}% {balance_alert} Статус: {status}")
            
#             return True, {'projects': projects}
#         else:
#             print_error(f"Ошибка: {r.status_code}")
#             return False, {}
#     except Exception as e:
#         print_error(f"Ошибка: {e}")
#         return False, {}


# def check_health_scores(project_keys: List[str]) -> Tuple[bool, Dict]:
#     """Проверка Health Score"""
#     print_subheader("7. Проверка Health Score")
    
#     url = f"{BACKEND_URL}/dashboard/health-cards?project_keys={','.join(project_keys[:3])}&period_days=30"
    
#     try:
#         r = requests.get(url, headers=get_headers(), timeout=30)
#         if r.status_code == 200:
#             data = r.json()
#             cards = data.get('cards', [])
            
#             print_success(f"Health Score получен для {len(cards)} проектов")
            
#             for card in cards:
#                 name = card.get('project_key', '?')
#                 health = card.get('health', {})
#                 score = health.get('health_score', 0)
#                 status = health.get('status_text', '?')
                
#                 icon = "🟢" if status == "Здоров" else "🟡" if status == "Есть риск" else "🔴"
#                 print(f"   {name:<12} Score: {score:>6.1f} {icon} {status}")
            
#             return True, {'cards': cards}
#         else:
#             print_error(f"Ошибка: {r.status_code}")
#             return False, {}
#     except Exception as e:
#         print_error(f"Ошибка: {e}")
#         return False, {}


# def check_dashboard() -> Tuple[bool, Dict]:
#     """Проверка дашборда"""
#     print_subheader("8. Проверка дашборда")
    
#     url = f"{BACKEND_URL}/dashboard/digest?period=month"
    
#     try:
#         r = requests.get(url, headers=get_headers(), timeout=30)
#         if r.status_code == 200:
#             data = r.json()
#             projects = data.get('data', {}).get('projects', [])
#             team_workload = len(data.get('data', {}).get('team_workload', []))
#             activity_trends = len(data.get('data', {}).get('activity_trends', []))
            
#             print_success(f"Дашборд получен")
#             print_stat("  Проектов в дашборде", len(projects))
#             print_stat("  Проектов в Team Workload", team_workload)
#             print_stat("  Проектов в Activity Trends", activity_trends)
            
#             return True, {'projects': projects}
#         else:
#             print_error(f"Ошибка: {r.status_code}")
#             return False, {}
#     except Exception as e:
#         print_error(f"Ошибка: {e}")
#         return False, {}


# def print_final_report(results: Dict):
#     """Итоговый отчёт"""
#     print_header("📊 ИТОГОВЫЙ ОТЧЁТ")
    
#     total_checks = len(results)
#     passed = sum(1 for v in results.values() if v)
    
#     print(f"\n{'Проверка':<40} {'Результат':<15}")
#     print("-" * 55)
    
#     for name, status in results.items():
#         icon = "✅" if status else "❌"
#         print(f"   {name:<38} {icon}")
    
#     print(f"\n{'='*55}")
#     print(f"   Всего проверок: {total_checks}")
#     print(f"   Успешно: {Colors.GREEN}{passed}{Colors.RESET}")
#     print(f"   Ошибок: {Colors.RED}{total_checks - passed}{Colors.RESET}")
    
#     if passed == total_checks:
#         print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ПОЗДРАВЛЯЮ! ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! 🎉{Colors.RESET}")
#         print(f"\n📊 Дашборд доступен по адресу:")
#         print(f"   http://localhost:8000/dashboard/digest?period=month")
#         print(f"\n📈 Документация API:")
#         print(f"   http://localhost:8000/docs")
#     else:
#         print(f"\n{Colors.YELLOW}⚠️ Некоторые проверки не пройдены.{Colors.RESET}")


# def main():
#     print_header("🚀 ПОЛНАЯ ПРОВЕРКА СИСТЕМЫ")
#     print("   Тестирование синхронизации, нормализации и метрик\n")
#     token = get_session_token()
#     print_info(f"Токен загружен: {token[:20]}...")
#     results = {
#         "1. Бэкенд": False,
#         "2. Авторизация": False,
#         "3. Синхронизация проектов": False,
#         "4. Синхронизация задач": False,
#         "5. Данные в БД": False,
#         "6. Workload Index": False,
#         "7. Health Score": False,
#         "8. Дашборд": False,
#     }
    
#     # Шаг 1: Бэкенд
#     results["1. Бэкенд"] = check_backend()
#     if not results["1. Бэкенд"]:
#         print_error("Не удалось подключиться к бэкенду")
#         print_final_report(results)
#         return
    
#     # Шаг 2: Авторизация
#     auth_success, auth_data = check_auth()
#     results["2. Авторизация"] = auth_success
#     if not auth_success:
#         print_error("Не удалось авторизоваться")
#         print_final_report(results)
#         return
    
#     # Получаем имя сайта из авторизации
#     sites = auth_data.get('sites', [])
#     instance_name = sites[0]['site_name'] if sites else "newtestsit"
#     print_info(f"Используем сайт: {instance_name}")
    
#     # Шаг 3: Синхронизация проектов
#     results["3. Синхронизация проектов"], _ = sync_projects(instance_name)
    
#     # Шаг 4: Синхронизация задач
#     results["4. Синхронизация задач"], _ = sync_issues(instance_name)
    
#     # Шаг 5: Проверка БД
#     results["5. Данные в БД"], db_stats = check_database()
    
#     # Получаем ключи проектов
#     project_keys = ["HEALTH", "CRUNCH", "IMBAL", "IDLE", "BUGS"]
    
#     # Шаг 6: Workload Index
#     results["6. Workload Index"], _ = check_workload_index(project_keys)
    
#     # Шаг 7: Health Score
#     results["7. Health Score"], _ = check_health_scores(project_keys)
    
#     # Шаг 8: Дашборд
#     results["8. Дашборд"], _ = check_dashboard()
    
#     # Итоговый отчёт
#     print_final_report(results)


# if __name__ == "__main__":
#     main()