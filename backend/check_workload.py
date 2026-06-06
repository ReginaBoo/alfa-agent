from app.db.session import SessionLocal
from sqlalchemy import text
from datetime import datetime, timedelta

db = SessionLocal()
projects = ['FULLCYCLE', 'BUGS', 'EMAL', 'IMBAL', 'HEALTH', 'KANBAN', 'CRUNCH']
weeks = 6
cutoff_date = datetime.utcnow() - timedelta(days=weeks*7)

print('='*70)
print(f'Анализ Workload за последние {weeks} недель')
print('='*70)

for project in projects:
    open_sp = db.execute(text("SELECT COALESCE(SUM(story_points), 0) FROM normalized.jira_issues WHERE project_key = :project AND status != 'Внедрение' AND is_deleted = false"), {'project': project}).fetchone()[0]
    closed_sp = db.execute(text("SELECT COALESCE(SUM(story_points), 0) FROM normalized.jira_issues WHERE project_key = :project AND status = 'Внедрение' AND closed_at > :cutoff AND is_deleted = false"), {'project': project, 'cutoff': cutoff_date}).fetchone()[0]
    velocity = closed_sp / weeks if closed_sp > 0 else 0
    wi = open_sp / velocity if velocity > 0 else 0
    closed_count = db.execute(text("SELECT COUNT(*) FROM normalized.jira_issues WHERE project_key = :project AND status = 'Внедрение' AND closed_at > :cutoff AND is_deleted = false"), {'project': project, 'cutoff': cutoff_date}).fetchone()[0]
    latest = db.execute(text("SELECT MAX(closed_at) FROM normalized.jira_issues WHERE project_key = :project AND status = 'Внедрение' AND is_deleted = false"), {'project': project}).fetchone()[0]
    
    print(f"\n📊 {project}")
    print(f"   Открытых SP: {open_sp}")
    print(f"   Закрытых SP за {weeks} нед: {closed_sp}")
    print(f"   Velocity: {velocity:.2f}")
    print(f"   Workload: {wi:.2f} -> {wi*100:.0f}%")
    print(f"   Закрыто задач: {closed_count}")
    if latest:
        days_ago = (datetime.utcnow() - latest).days
        print(f"   Последняя закрытая: {days_ago} дней назад")

db.close()