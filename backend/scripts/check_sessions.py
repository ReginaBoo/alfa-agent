#!/usr/bin/env python3
"""
Скрипт для проверки активных сессий в БД.
Полезен для отладки E2E тестов с авторизацией.

Запуск:
    docker-compose exec backend python scripts/check_sessions.py
"""

from datetime import datetime
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.identity import User, Session as DBSession


def check_sessions():
    """Проверка всех сессий в БД"""
    print("\n" + "="*70)
    print("🔍 SESSION CHECKER")
    print("="*70)
    
    db = SessionLocal()
    
    try:
        # Все сессии
        all_sessions = db.query(DBSession).all()
        print(f"\n📊 Total sessions in DB: {len(all_sessions)}")
        
        if not all_sessions:
            print("   No sessions found.")
            return
        
        # Активные сессии
        now = datetime.utcnow()
        active_sessions = db.query(DBSession).filter(
            DBSession.expires_at > now
        ).all()
        
        print(f"✅ Active sessions: {len(active_sessions)}")
        print(f"❌ Expired sessions: {len(all_sessions) - len(active_sessions)}")
        
        # Вывод активных сессий
        if active_sessions:
            print("\n📋 Active Sessions:")
            print("-"*70)
            
            for session in active_sessions:
                user = db.query(User).filter(User.id == session.user_id).first()
                
                if user:
                    print(f"\n   User: {user.display_name} ({user.email})")
                    print(f"   Session ID: {session.session_token[:30]}...")
                    print(f"   Created: {session.created_at}")
                    print(f"   Expires: {session.expires_at}")
                    print(f"   Client: {session.client_type or 'unknown'}")
                    print(f"   Time left: {session.expires_at - now}")
        
        # Вывод expired сессий
        expired_sessions = [s for s in all_sessions if s.expires_at <= now]
        if expired_sessions:
            print(f"\n❌ Expired Sessions ({len(expired_sessions)}):")
            print("-"*70)
            
            for session in expired_sessions[:5]:  # Показываем первые 5
                user = db.query(User).filter(User.id == session.user_id).first()
                if user:
                    print(f"   - {user.display_name}: expired at {session.expires_at}")
            
            if len(expired_sessions) > 5:
                print(f"   ... and {len(expired_sessions) - 5} more")
        
        # Статистика по пользователям
        print("\n👥 Users with sessions:")
        print("-"*70)
        
        user_counts = db.query(
            User.display_name,
            User.email,
            Session.count()
        ).join(
            DBSession, User.id == DBSession.user_id
        ).group_by(
            User.id, User.display_name, User.email
        ).all()
        
        for user_name, user_email, count in user_counts:
            print(f"   {user_name} ({user_email}): {count} session(s)")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()
    
    print("\n" + "="*70)


def cleanup_expired():
    """Очистка expired сессий"""
    print("\n🧹 CLEANING EXPIRED SESSIONS")
    print("="*70)
    
    db = SessionLocal()
    
    try:
        expired_count = db.query(DBSession).filter(
            DBSession.expires_at <= datetime.utcnow()
        ).delete()
        
        db.commit()
        
        print(f"✅ Deleted {expired_count} expired session(s)")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--cleanup":
        cleanup_expired()
    else:
        check_sessions()
    
    print("\n")
