# check_workload.py
from app.db.session import SessionLocal
from sqlalchemy import text
from datetime import datetime, timedelta

db = SessionLocal()

projects = ['FULLCYCLE', 'BUGS', 'EMAL', 'IMBAL', 'HEALTH', 'KANBAN', 'CRUNCH']
weeks = 6
cutoff_date = datetime.utcnow() - timedelta(days=weeks*7)

print('='*70)
print(f'Анализ Workload за последние {weeks} недель (с {cutoff_date.date()})')
print('='*70)

for project in projects:
    print(f'\n📊 Проект: {project}')
    print('-'*40)
    
    # 1. Сумма SP открытых задач
    open_sp = db.execute(text("""
        SELECT COALESCE(SUM(story_points), 0)
        FROM normalized.jira_issues
        WHERE project_key = :project
        AND status != 'Внедрение'
        AND is_deleted = false
    """), {'project': project}).fetchone()[0]
    
    print(f'  📌 Сумма SP открытых задач: {open_sp}')
    
    # 2. Сумма SP закрытых задач за 6 недель
    closed_sp = db.execute(text("""
        SELECT COALESCE(SUM(story_points), 0)
        FROM normalized.jira_issues
        WHERE project_key = :project
        AND status = 'Внедрение'
        AND closed_at > :cutoff
        AND is_deleted = false
    """), {'project': project, 'cutoff': cutoff_date}).fetchone()[0]
    
    print(f'  📌 Сумма SP закрытых задач за {weeks} нед: {closed_sp}')
    
    # 3. Velocity
    if closed_sp > 0:
        velocity = closed_sp / weeks
    else:
        velocity = 0
    
    print(f'  📌 Velocity (SP/неделю): {velocity:.2f}')
    
    # 4. Workload Index
    if velocity > 0:
        wi = open_sp / velocity
    else:
        wi = 0
    
    print(f'  📌 Workload Index: {wi:.2f} -> {wi*100:.0f}%')
    
    # 5. Количество закрытых задач за 6 недель
    closed_count = db.execute(text("""
        SELECT COUNT(*)
        FROM normalized.jira_issues
        WHERE project_key = :project
        AND status = 'Внедрение'
        AND closed_at > :cutoff
        AND is_deleted = false
    """), {'project': project, 'cutoff': cutoff_date}).fetchone()[0]
    
    print(f'  📌 Закрыто задач за {weeks} нед: {closed_count}')
    
    # 6. Последняя закрытая задача
    latest_closed = db.execute(text("""
        SELECT MAX(closed_at)
        FROM normalized.jira_issues
        WHERE project_key = :project
        AND status = 'Внедрение'
        AND is_deleted = false
    """), {'project': project}).fetchone()[0]
    
    if latest_closed:
        days_ago = (datetime.utcnow() - latest_closed).days
        print(f'  📌 Последняя закрытая задача: {days_ago} дней назад')
    else:
        print('  📌 Нет закрытых задач в проекте')
    
    # 7. Всего задач в проекте
    total = db.execute(text("""
        SELECT COUNT(*)
        FROM normalized.jira_issues
        WHERE project_key = :project
        AND is_deleted = false
    """), {'project': project}).fetchone()[0]
    
    print(f'  📌 Всего задач в проекте: {total}')

db.close()
print('\n' + '='*70)
print('Вывод: если Velocity = 0, то Workload всегда будет 0%')
print('Для расчёта нужны закрытые задачи за последние 6 недель!')
print('='*70)