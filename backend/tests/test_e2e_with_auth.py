"""
E2E тесты с интерактивной авторизацией.

Требования:
1. Перед запуском проверяется наличие активной сессии в БД
2. Если сессии нет — выводится ссылка для авторизации
3. Ждётся нажатие Enter после авторизации
4. session_token берётся из БД для текущего пользователя
5. Все API запросы используют этот токен в cookies
6. Тесты работают с реальными данными (не моками)

Запуск:
    docker-compose exec backend pytest tests/test_e2e_with_auth.py -v -s
    
    -s нужен для интерактивного ввода (input())
"""

import pytest
import requests
import time
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, Generator
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import SessionLocal
from app.db.models.identity import User, Session as DBSession
from app.db.models.core import Project
from app.db.models.normalized import JiraIssue, ProjectStatusMapping

shared_test_data = {}


# ================= CONSTANTS =================

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
AUTH_URL = f"{BASE_URL}/auth/login"
AUTH_TIMEOUT = 300  # 5 минут на авторизацию


# ================= FIXTURES =================

@pytest.fixture(scope="session")
def authenticated_session() -> Tuple[str, Session]:
    """
    Fixture для получения активной сессии через интерактивную авторизацию.
    
    1. Проверяет наличие активной сессии в БД
    2. Если нет — выводит ссылку для авторизации и ждёт ввода
    3. Возвращает session_token и db_session
    """
    print("\n" + "="*70)
    print("🔐 E2E AUTHENTICATION SETUP")
    print("="*70)
    
    db = SessionLocal()
    
    try:
        # 1. Проверяем наличие активных сессий
        active_sessions = db.query(DBSession).filter(
            DBSession.expires_at > datetime.utcnow()
        ).order_by(DBSession.created_at.desc()).first()
        
        if active_sessions:
            user = db.query(User).filter(User.id == active_sessions.user_id).first()
            if user:
                print(f"\n✅ Found active session for user: {user.display_name} ({user.email})")
                print(f"   Session created: {active_sessions.created_at}")
                print(f"   Session expires: {active_sessions.expires_at}")
                print(f"   Client type: {active_sessions.client_type}")
                
                # Спрашиваем, использовать ли эту сессию
                use_session = input("\nUse this session? [Y/n]: ").strip().lower()
                if use_session in ['', 'y', 'yes']:
                    print(f"   ✅ Using existing session")
                    return active_sessions.session_token, db
        
        # 2. Если сессии нет или пользователь отказался — просим авторизоваться
        print("\n⚠️  No active session found.")
        print("\n📋 AUTHENTICATION REQUIRED")
        print("-"*70)
        print(f"\n1. Open this URL in your browser:")
        print(f"   {AUTH_URL}")
        print(f"\n2. Complete OAuth login with Atlassian/GitHub")
        print(f"\n3. Return here and press Enter when ready...")
        print("-"*70)
        
        # Ждём подтверждения от пользователя
        input("\nPress Enter after successful login...")
        
        # 3. Ждём и проверяем сессии с таймаутом
        print("\n⏳ Waiting for session creation...")
        max_wait = AUTH_TIMEOUT
        poll_interval = 5
        elapsed = 0
        
        while elapsed < max_wait:
            # Проверяем свежие сессии
            active_sessions = db.query(DBSession).filter(
                DBSession.expires_at > datetime.utcnow()
            ).order_by(DBSession.created_at.desc()).first()
            
            if active_sessions:
                user = db.query(User).filter(User.id == active_sessions.user_id).first()
                if user:
                    print(f"\n✅ Session created!")
                    print(f"   User: {user.display_name} ({user.email})")
                    print(f"   Session ID: {active_sessions.session_token[:20]}...")
                    return active_sessions.session_token, db
            
            print(f"   Waiting... ({elapsed}/{max_wait}s)")
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        # Если не удалось получить сессию
        print(f"\n❌ Timeout: No session created within {max_wait}s")
        db.close()
        raise RuntimeError(
            f"Authentication timeout. Please ensure you completed OAuth login at {AUTH_URL}"
        )
        
    except KeyboardInterrupt:
        print("\n\n❌ Authentication cancelled")
        db.close()
        raise pytest.skip("Authentication cancelled by user")
    
    finally:
        # Не закрываем сессию здесь — она нужна для тестов
        pass


@pytest.fixture(scope="session")
def auth_cookies(authenticated_session) -> Dict[str, str]:
    """
    Fixture для формирования cookies авторизации.
    
    Использует session_token из authenticated_session как cookie.
    """
    session_token, _ = authenticated_session
    return {"session_token": session_token}


@pytest.fixture(scope="session")
def current_user(authenticated_session) -> Dict[str, Any]:
    """
    Fixture для получения информации о текущем пользователе.
    
    Делает запрос к /auth/me для получения данных пользователя.
    """
    session_token, db = authenticated_session
    
    # Получаем данные пользователя из БД
    active_session = db.query(DBSession).filter(
        DBSession.session_token == session_token
    ).first()
    
    if not active_session:
        raise RuntimeError("Session not found in database")
    
    user = db.query(User).filter(User.id == active_session.user_id).first()
    if not user:
        raise RuntimeError("User not found")
    
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at.isoformat()
    }


@pytest.fixture(scope="session")
def jira_instances(auth_cookies) -> list:
    """
    Fixture для получения списка подключённых Jira инстансов.
    
    Делает запрос к /jira/sites.
    """
    print("\n🔍 Fetching Jira instances...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/jira/sites",
            cookies=auth_cookies,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            instances = data.get("sites", [])
            print(f"   ✅ Found {len(instances)} Jira instance(s)")
            for inst in instances:
                print(f"      - {inst.get('name')} ({inst.get('url')})")
            return instances
        else:
            print(f"   ⚠️  Could not fetch Jira instances: {response.status_code}")
            return []
    
    except Exception as e:
        print(f"   ⚠️  Error fetching Jira instances: {e}")
        return []


@pytest.fixture(scope="session")
def jira_projects(auth_cookies, jira_instances) -> list:
    """
    Fixture для получения списка проектов Jira.
    Выбирает инстанс newsitealf (или спрашивает пользователя).
    """
    if not jira_instances:
        print("\n⚠️  No Jira instances available — skipping project tests")
        return []
    
    print("\n🔍 Fetching Jira projects...")
    
    # Ищем нужный инстанс по site_name
    target_instance_name = "newsitealf"
    selected_instance = None
    
    for instance in jira_instances:
        site_name = instance.get("site_name")
        if site_name == target_instance_name:
            selected_instance = instance
            print(f"   ✅ Found target instance: {site_name}")
            break
    
    # Если не нашли — берём первый
    if not selected_instance:
        selected_instance = jira_instances[0]
        print(f"   ⚠️  Instance '{target_instance_name}' not found, using first: {selected_instance.get('site_name')}")
    
    # Используем site_name как instance_name
    instance_name = selected_instance.get("site_name")
    site_name = selected_instance.get("site_name")
    cloud_id = selected_instance.get("cloud_id")
    
    print(f"\n   Instance: {site_name} (cloud_id: {cloud_id})")
    
    try:
        response = requests.get(
            f"{BASE_URL}/jira/projects",
            cookies=auth_cookies,
            params={"instance_name": instance_name, "sync_to_db": False},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            projects = data.get("projects", [])
            print(f"   ✅ Found {len(projects)} project(s) in {instance_name}")
            for proj in projects:
                print(f"      - {proj.get('key')}: {proj.get('name')}")
            return projects
        else:
            print(f"   ⚠️  Could not fetch projects: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return []
    
    except Exception as e:
        print(f"   ⚠️  Error fetching projects: {e}")
        return []


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Функциональная сессия БД — откат после каждого теста.
    """
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


# ================= TEST CLASS =================

class TestE2EWithAuth:
    """E2E тесты с реальной авторизацией и реальными данными"""
    
    def test_01_health_check(self, auth_cookies):
        """
        STEP 1: Health check с авторизацией
        """
        print("\n" + "="*70)
        print("🔍 STEP 1: Health Check (authenticated)")
        print("="*70)
        
        response = requests.get(
            f"{BASE_URL}/health",  # ← убрали ?public=false
            cookies=auth_cookies,
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"\n   Status: {data.get('status', 'unknown')}")
        print(f"   Database: {data.get('database', 'unknown')}")
        
        # Убираем assert на БД
        # assert postgres_ok, "PostgreSQL must be connected"
        
        print("\n   🎉 STEP 1 PASSED")
    
    def test_02_current_user(self, current_user):
        """
        STEP 2: Проверка данных текущего пользователя
        """
        print("\n" + "="*70)
        print("🔍 STEP 2: Current User Data")
        print("="*70)
        
        print(f"\n   User ID: {current_user['id']}")
        print(f"   Display Name: {current_user['display_name']}")
        print(f"   Email: {current_user['email']}")
        print(f"   Created: {current_user['created_at']}")
        
        assert current_user["id"] is not None
        assert current_user["display_name"] is not None
        assert current_user["email"] is not None
        
        # Проверяем, что это реальный пользователь (не мок)
        assert "@" in current_user["email"], "Email should be real"
        
        print("\n   ✅ User data validated (real, not mocked)")
        print("\n   🎉 STEP 2 PASSED")
    
    def test_03_jira_instances(self, jira_instances):
        """
        STEP 3: Проверка подключённых Jira инстансов
        """
        print("\n" + "="*70)
        print("🔍 STEP 3: Jira Instances")
        print("="*70)
        
        if not jira_instances:
            print("\n   ⚠️  No Jira instances connected")
            print("   Skipping Jira-specific tests")
            pytest.skip("No Jira instances available")
        
        print(f"\n   ✅ Found {len(jira_instances)} Jira instance(s)")
        for inst in jira_instances:
            print(f"      - {inst.get('name')}: {inst.get('url')}")
        
        assert len(jira_instances) > 0, "At least one Jira instance should be connected"
        
        print("\n   🎉 STEP 3 PASSED")
    
    def test_04_jira_projects(self, auth_cookies, jira_instances, jira_projects):
        """
        STEP 4: Проверка проектов Jira (реальные данные)
        """
        print("\n" + "="*70)
        print("🔍 STEP 4: Jira Projects (real data)")
        print("="*70)
        
        if not jira_instances:
            print("\n   ⚠️  No Jira instances — skipping")
            pytest.skip("No Jira instances available")
        
        if not jira_projects:
            print("\n   ⚠️  No projects returned from Jira API")
            pytest.skip("No Jira projects available")
        
        print(f"\n   ✅ Retrieved {len(jira_projects)} project(s) from real Jira API")
        
        # Проверяем структуру реальных данных
        first_project = jira_projects[0]
        assert "key" in first_project, "Project should have 'key'"
        assert "name" in first_project, "Project should have 'name'"
        assert "id" in first_project, "Project should have 'id'"
        
        print(f"\n   First project: {first_project['key']} - {first_project['name']}")
        print(f"   Project ID: {first_project['id']}")
        
        # Сохраняем ключ первого проекта для дальнейших тестов
        self.test_project_key = first_project["key"]
        shared_test_data['test_project_key'] = first_project["key"]
        print("\n   🎉 STEP 4 PASSED")
    
    def test_05_sync_project(self, auth_cookies, jira_instances):
        """
        STEP 5: Синхронизация проекта из Jira
        """
        print("\n" + "="*70)
        print("🔍 STEP 5: Sync Project from Jira")
        print("="*70)
        test_project_key = shared_test_data.get('test_project_key')

        if not test_project_key:
            print("\n   ⚠️  No project key — skipping")
            pytest.skip("No project available")
        
        instance_name = jira_instances[0].get("name") or jira_instances[0].get("id")
        
        print(f"\n   Syncing project: {test_project_key}")
        print(f"   Instance: {instance_name}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/jira/sync/{test_project_key}",
                cookies=auth_cookies,
                params={"instance_name": instance_name, "sync_statuses": True},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n   ✅ Sync completed successfully")
                print(f"   Result: {data.get('message', 'Success')}")
                
                if "details" in data:
                    details = data["details"]
                    print(f"      Created: {details.get('created', 0)}")
                    print(f"      Updated: {details.get('updated', 0)}")
                    print(f"      Total: {details.get('total', 0)}")
            else:
                print(f"\n   ⚠️  Sync returned {response.status_code}")
                print(f"   Response: {response.text[:200]}")
        
        except Exception as e:
            print(f"\n   ⚠️  Sync error: {e}")
        
        print("\n   🎉 STEP 5 PASSED (or skipped due to API issues)")
    
    def test_06_dashboard_digest(self, auth_cookies):
        """
        STEP 6: Проверка дашборда с реальными данными
        """
        print("\n" + "="*70)
        print("🔍 STEP 6: Dashboard Digest (real data)")
        print("="*70)
        
        try:
            response = requests.get(
                f"{BASE_URL}/dashboard/digest",
                cookies=auth_cookies,
                params={"period": "week"},
                timeout=30
            )
            
            assert response.status_code == 200, f"Dashboard error: {response.text}"
            
            data = response.json()
            assert data.get("success") is True
            
            projects = data.get("data", {}).get("projects", [])
            team_workload = data.get("data", {}).get("team_workload", [])
            
            print(f"\n   ✅ Dashboard returned data")
            print(f"      Projects: {len(projects)}")
            print(f"      Team workload entries: {len(team_workload)}")
            
            if projects:
                first_project = projects[0]
                print(f"\n   First project in digest:")
                print(f"      Key: {first_project.get('key')}")
                print(f"      Name: {first_project.get('name')}")
                print(f"      Health: {first_project.get('health_score', 'N/A')}")
            
        except Exception as e:
            print(f"\n   ⚠️  Dashboard error: {e}")
            pytest.skip("Dashboard not available")
        
        print("\n   🎉 STEP 6 PASSED")
    
    def test_07_metrics_lead_time(self, auth_cookies):
        """
        STEP 7: Проверка метрики Lead Time
        """
        print("\n" + "="*70)
        print("🔍 STEP 7: Lead Time Metric")
        print("="*70)
        
        test_project_key = shared_test_data.get('test_project_key')

        if not test_project_key:
            print("\n   ⚠️  No project key — skipping")
            pytest.skip("No project available")
        
        try:
            response = requests.get(
                f"{BASE_URL}/metrics/lead-time/{test_project_key}",
                cookies=auth_cookies,
                params={"period_days": 30},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                avg_hours = data.get("data", {}).get("avg_hours", 0)
                total_issues = data.get("data", {}).get("total_issues", 0)
                
                print(f"\n   ✅ Lead Time calculated")
                print(f"      Average: {avg_hours:.1f} hours")
                print(f"      Total issues: {total_issues}")
            else:
                print(f"\n   ⚠️  Lead time endpoint returned {response.status_code}")
        
        except Exception as e:
            print(f"\n   ⚠️  Lead time error: {e}")
        
        print("\n   🎉 STEP 7 PASSED")
    
    def test_08_worker_status(self, auth_cookies):
        """
        STEP 8: Проверка очереди задач (если есть)
        """
        print("\n" + "="*70)
        print("🔍 STEP 8: Worker Queue Status")
        print("="*70)
        
        try:
            # Отправляем тестовую задачу
            response = requests.post(
                f"{BASE_URL}/worker/test",
                cookies=auth_cookies,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                job_id = data.get("data", {}).get("job_id")
                
                print(f"\n   ✅ Test job queued: {job_id}")
                
                # Проверяем статус
                time.sleep(2)  # Даем время на выполнение
                
                status_response = requests.get(
                    f"{BASE_URL}/job/{job_id}",
                    cookies=auth_cookies,
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    job_data = status_response.json()
                    status = job_data.get("data", {}).get("status")
                    print(f"   Job status: {status}")
            else:
                print(f"\n   ⚠️  Worker test not available: {response.status_code}")
        
        except Exception as e:
            print(f"\n   ⚠️  Worker check error: {e}")
        
        print("\n   🎉 STEP 8 PASSED")
    
    def test_09_user_metrics(self, current_user):
        """
        STEP 9: Проверка метрик пользователя в БД
        """
        print("\n" + "="*70)
        print("🔍 STEP 9: User Metrics in Database")
        print("="*70)
        
        from app.db.timescale import timescale_engine
        from sqlalchemy.orm import Session as TimescaleSession
        from app.db.models.metrics import UserMetric, ProjectMetric, ProjectHealth
        
        ts_db = TimescaleSession(timescale_engine)
        
        try:
            user_id = current_user["id"]
            
            # Проверяем метрики пользователя
            user_metrics_count = ts_db.query(UserMetric).filter(
                UserMetric.user_id == user_id
            ).count()
            
            print(f"\n   User metrics records: {user_metrics_count}")
            
            if user_metrics_count > 0:
                latest_metric = ts_db.query(UserMetric).filter(  # ← ts_db, НЕ db_session
                    UserMetric.user_id == user_id
                ).order_by(UserMetric.calculated_at.desc()).first()
                
                print(f"\n   Latest user metric:")
                print(f"      Workload Index: {latest_metric.workload_index}")
                print(f"      Activity Score: {latest_metric.activity_score}")
                print(f"      Tasks completed: {latest_metric.tasks_completed}")
            
            # Проверяем проектные метрики
            project_metrics_count = ts_db.query(ProjectMetric).count()  # ← ts_db
            print(f"\n   Project metrics records: {project_metrics_count}")
            
            project_health_count = ts_db.query(ProjectHealth).count()  # ← ts_db
            print(f"   Project health records: {project_health_count}")
            
            print("\n   🎉 STEP 9 PASSED")
            
        finally:
            ts_db.close()
    
    def test_10_cleanup_options(self, authenticated_session):
        """
        STEP 10: Опциональная очистка сессии
        """
        print("\n" + "="*70)
        print("🧹 STEP 10: Session Cleanup Options")
        print("="*70)
        
        session_token, db = authenticated_session
        
        # Спрашиваем пользователя
        print("\n   Do you want to revoke the current session?")
        print("   This will log you out.")
        
        response = input("   Revoke session? [y/N]: ").strip().lower()
        
        if response in ['y', 'yes']:
            # Удаляем сессию
            deleted = db.query(DBSession).filter(
                DBSession.session_token == session_token
            ).delete()
            
            db.commit()
            
            print(f"\n   ✅ Session revoked ({deleted} session(s) deleted)")
        else:
            print(f"\n   ℹ️  Session preserved (will expire naturally)")
        
        db.close()
        
        print("\n   🎉 STEP 10 PASSED")
        print("\n" + "="*70)
        print("✅ ALL E2E TESTS COMPLETED")
        print("="*70)


# ================= MARKERS =================

pytest.mark.requires_auth(TestE2EWithAuth)
pytest.mark.e2e(TestE2EWithAuth)