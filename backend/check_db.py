from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print('=' * 60)
print('ПРОВЕРКА STORY POINTS ПО ПРОЕКТАМ')
print('=' * 60)

projects = ['HEALTH', 'CRUNCH', 'IMBAL', 'IDLE', 'BUGS', 'KANBAN']

for project_key in projects:
    # Сумма SP в открытых задачах
    result = db.execute(text("""
        SELECT COALESCE(SUM(story_points), 0)
        FROM normalized.jira_issues
        WHERE project_key = :project_key
          AND status NOT IN ('Готово', 'Done', 'Closed')
          AND story_points IS NOT NULL
    """), {'project_key': project_key}).scalar()
    
    open_sp = result or 0
    
    # Количество открытых задач
    open_count = db.execute(text("""
        SELECT COUNT(*)
        FROM normalized.jira_issues
        WHERE project_key = :project_key
          AND status NOT IN ('Готово', 'Done', 'Closed')
    """), {'project_key': project_key}).scalar()
    
    print(f'{project_key}: open_sp={open_sp}, open_tasks={open_count}')

print('\n' + '=' * 60)
print('ПРОВЕРКА VELOCITY (за последние 4 недели)')
print('=' * 60)

from datetime import datetime, timedelta
cutoff_date = datetime.now() - timedelta(weeks=4)

for project_key in projects:
    result = db.execute(text("""
        SELECT COALESCE(SUM(story_points), 0)
        FROM normalized.jira_issues
        WHERE project_key = :project_key
          AND status IN ('Готово', 'Done', 'Closed')
          AND updated_at >= :cutoff_date
          AND story_points IS NOT NULL
    """), {'project_key': project_key, 'cutoff_date': cutoff_date}).scalar()
    
    closed_sp = result or 0
    velocity = closed_sp / 4
    print(f'{project_key}: closed_sp={closed_sp}, velocity/неделю={velocity:.2f}')

print('\n' + '=' * 60)
print('РАСЧЁТ WI ДЛЯ ПЕРВОГО СОТРУДНИКА')
print('=' * 60)

for project_key in projects:
    assignee = db.execute(text("""
        SELECT assignee_account_id
        FROM normalized.jira_issues
        WHERE project_key = :project_key
          AND assignee_account_id IS NOT NULL
        LIMIT 1
    """), {'project_key': project_key}).scalar()
    
    if assignee:
        from app.services.metrics.workload_index import calculate_workload_index
        wi = calculate_workload_index(db, assignee, project_key, weeks=4)
        
        if wi:
            if wi < 0.7:
                status = 'недогруз'
            elif wi < 1.0:
                status = 'оптимально'
            elif wi < 1.3:
                status = 'повышенная'
            else:
                status = 'перегруз'
            print(f'{project_key}: WI={wi:.2f} -> {status}')
        else:
            print(f'{project_key}: нет данных для расчёта')
    else:
        print(f'{project_key}: нет исполнителей')

db.close()
