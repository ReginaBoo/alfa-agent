#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генерация реалистичных тестовых данных GitHub:
- Pull Requests с разными статусами
- Reviews (APPROVED, CHANGES_REQUESTED)
- Commits с Jira-ключами
- Check Runs (CI/CD статусы)

Запуск: docker-compose exec backend python scripts/create_real_github_data.py
"""

import sys
import os
import random
import json
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from sqlalchemy import text

# Конфигурация проектов
PROJECTS_CONFIG = {
    "HEALTH": {
        "repo": "company/web-platform",
        "pr_count": 15,
        "authors": ["alexey.ivanov", "elena.petrova", "mikhail.sidorov"],
        "reviewers": ["olga.volkova", "maxim.vasiliev"],
        "jira_prefix": "HEALTH"
    },
    "CRUNCH": {
        "repo": "company/mobile-app",
        "pr_count": 8,
        "authors": ["olga.volkova", "irina.morozova"],
        "reviewers": ["alexey.ivanov", "andrey.sokolov"],
        "jira_prefix": "CRUNCH"
    },
    "BUGS": {
        "repo": "company/support-bot",
        "pr_count": 10,
        "authors": ["maxim.vasiliev", "mikhail.sidorov"],
        "reviewers": ["elena.petrova", "olga.volkova"],
        "jira_prefix": "BUGS"
    },
    "IMBAL": {
        "repo": "company/api-service",
        "pr_count": 12,
        "authors": ["mikhail.sidorov", "olga.volkova"],
        "reviewers": ["natalia.lebedeva", "alexey.ivanov"],
        "jira_prefix": "IMBAL"
    },
    "KANBAN": {
        "repo": "company/ops-tasks",
        "pr_count": 6,
        "authors": ["olga.volkova", "maxim.vasiliev"],
        "reviewers": ["pavel.sokolov", "andrey.sokolov"],
        "jira_prefix": "KANBAN"
    },
    "IDLE": {
        "repo": "company/docs",
        "pr_count": 3,
        "authors": ["sergey.novikov", "tatyana.kuzmina"],
        "reviewers": [],
        "jira_prefix": "IDLE"
    },
    "KAN": {
        "repo": "company/software-team",
        "pr_count": 8,
        "authors": ["alexey.ivanov", "maxim.vasiliev"],
        "reviewers": ["pavel.sokolov", "maria.vinogradova"],
        "jira_prefix": "KAN"
    },
    "EMAL": {
        "repo": "company/mobile-launch",
        "pr_count": 10,
        "authors": ["alexey.ivanov", "elena.petrova"],
        "reviewers": ["pavel.sokolov", "mikhail.sidorov"],
        "jira_prefix": "EMAL"
    },
    "NEWPROJ": {
        "repo": "company/research",
        "pr_count": 2,
        "authors": ["tatyana.kuzmina", "sergey.novikov"],
        "reviewers": [],
        "jira_prefix": "NEWPROJ"
    },
    "FULLCYCLE": {
        "repo": "company/enterprise-portal",
        "pr_count": 15,
        "authors": ["alexey.ivanov", "elena.petrova", "mikhail.sidorov", "olga.volkova"],
        "reviewers": ["pavel.sokolov", "natalia.lebedeva", "maria.vinogradova"],
        "jira_prefix": "FULLCYCLE"
    }
}

def get_project_id(db, project_key):
    """Получает ID проекта по его ключу"""
    result = db.execute(text("SELECT id FROM core.projects WHERE key = :key"), {"key": project_key}).fetchone()
    return result[0] if result else None


def generate_pr_data(project_key, config, pr_num, issue_id_start):
    """Генерирует данные для одного PR"""
    created_days_ago = random.randint(1, 60)
    created_at = datetime.now() - timedelta(days=created_days_ago)
    
    # Определяем статус
    rand = random.random()
    if rand < 0.7:  # 70% merged
        state = "closed"
        merged = True
        merged_days_after = random.randint(1, max(1, created_days_ago - 1))
        merged_at = created_at + timedelta(days=merged_days_after)
        closed_at = merged_at
    elif rand < 0.85:  # 15% closed without merge
        state = "closed"
        merged = False
        merged_at = None
        closed_at = created_at + timedelta(days=random.randint(1, max(1, created_days_ago - 1)))
    else:  # 15% open
        state = "open"
        merged = False
        merged_at = None
        closed_at = None
    
    author = random.choice(config["authors"])
    reviewers = random.sample(config["reviewers"], k=min(random.randint(1, 3), len(config["reviewers"])))
    
    # Генерируем номер задачи Jira
    jira_num = random.randint(1, 200)
    jira_key = f"{config['jira_prefix']}-{jira_num}"
    
    # Заголовки PR
    pr_titles = [
        f"[{jira_key}] Fix critical bug in authentication module",
        f"[{jira_key}] Add new API endpoint for user profiles",
        f"[{jira_key}] Refactor database queries for better performance",
        f"[{jira_key}] Update dependencies to latest versions",
        f"[{jira_key}] Implement dark mode for dashboard",
        f"[{jira_key}] Fix memory leak in background workers",
        f"[jira_key] Add integration tests for payment service"
    ]
    title = random.choice(pr_titles)
    
    # Статистика изменений
    additions = random.randint(10, 500)
    deletions = random.randint(0, additions // 2)
    
    # Ветки
    head_branch = f"feature/{jira_key.lower()}-some-feature"
    base_branch = "main"
    
    return {
        "pr_id": issue_id_start,
        "pr_number": pr_num,
        "title": title,
        "state": state,
        "merged": merged,
        "merged_at": merged_at,
        "closed_at": closed_at,
        "created_at": created_at,
        "updated_at": merged_at or closed_at or datetime.now(),
        "author": author,
        "reviewers": reviewers,
        "additions": additions,
        "deletions": deletions,
        "head_branch": head_branch,
        "base_branch": base_branch,
        "head_sha": f"a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8{pr_num:04d}",
        "comments_count": random.randint(0, 15),
        "review_comments_count": random.randint(0, 10)
    }


def generate_reviews_for_pr(pr_data, reviewer_list, pr_id):
    """Генерирует ревью для PR"""
    reviews = []
    pr_created = pr_data["created_at"]
    
    # Генерируем 1-4 ревью
    num_reviews = random.randint(1, 4) if pr_data["merged"] else random.randint(0, 2)
    
    states = ["APPROVED", "CHANGES_REQUESTED", "COMMENTED"]
    used_reviewers = random.sample(reviewer_list, k=min(num_reviews, len(reviewer_list)))
    
    for i, reviewer in enumerate(used_reviewers):
        # Время ревью после создания PR
        hours_after = random.randint(1, 48)
        submitted_at = pr_created + timedelta(hours=hours_after)
        
        # Определяем состояние
        if pr_data["merged"] and i == len(used_reviewers) - 1:
            # Последний ревьюер перед мержем обычно APPROVED
            state = "APPROVED"
        else:
            state = random.choice(states)
        
        review_bodies = {
            "APPROVED": [
                "LGTM! Looks good to me.",
                "Approved. Nice work!",
                "Changes look good, merging."
            ],
            "CHANGES_REQUESTED": [
                "Please fix the formatting in the function.",
                "There are some edge cases we need to handle.",
                "Can you add more tests for this scenario?",
                "This might cause issues in production. Please reconsider."
            ],
            "COMMENTED": [
                "Have you considered using a different approach?",
                "Interesting solution! Just curious about the performance impact.",
                "Minor suggestion: could use a more descriptive variable name."
            ]
        }
        
        reviews.append({
            "review_id": pr_id * 100 + i,
            "pr_id": pr_id,
            "user": reviewer,
            "state": state,
            "body": random.choice(review_bodies[state]),
            "submitted_at": submitted_at
        })
    
    return reviews


def generate_commits_for_pr(pr_data, repo_name, pr_id, jira_key):
    """Генерирует коммиты для PR"""
    commits = []
    num_commits = random.randint(2, 8)
    
    author = pr_data["author"]
    pr_created = pr_data["created_at"]
    
    commit_messages = [
        f"Add initial implementation of {jira_key}",
        f"Fix linting issues in {jira_key}",
        f"Add tests for {jira_key}",
        f"Refactor code for better readability",
        f"Update documentation",
        f"Fix bug in edge case handling",
        f"Optimize database queries",
        f"Add error handling"
    ]
    
    current_time = pr_created
    
    for i in range(num_commits):
        # Каждый коммит на несколько часов/дней позже
        hours_after = i * random.randint(2, 12)
        committed_at = pr_created + timedelta(hours=hours_after)
        
        # Статистика
        additions = random.randint(5, 100)
        deletions = random.randint(0, additions // 3)
        
        sha = f"{pr_data['head_sha'][:10]}{i:03d}"
        
        commits.append({
            "sha": sha,
            "author": author,
            "message": random.choice(commit_messages),
            "committed_at": committed_at,
            "additions": additions,
            "deletions": deletions,
            "total": additions + deletions
        })
    
    return commits


def main():
    print("=" * 70)
    print("📝 ГЕНЕРАЦИЯ РЕАЛИСТИЧНЫХ TEST DATA GITHUB")
    print("=" * 70)

    db = SessionLocal()
    
    try:
        # Очищаем старые данные
        print("\n🗑️ Очистка старых данных GitHub...")
        db.execute(text("DELETE FROM normalized.github_pull_request_reviews"))
        db.execute(text("DELETE FROM normalized.github_commits"))
        db.execute(text("DELETE FROM normalized.github_pull_requests"))
        db.commit()
        print("   ✅ Удалено")

        pr_counter = 1
        review_counter = 1
        commit_counter = 1
        all_prs = []
        all_reviews = []
        all_commits = []

        for project_key, config in PROJECTS_CONFIG.items():
            project_id = get_project_id(db, project_key)
            if not project_id:
                print(f"\n⚠️ Проект {project_key} не найден. Пропускаем.")
                continue

            print(f"\n📁 Проект: {project_key} (ID: {project_id}) -> {config['pr_count']} PR")

            for i in range(config["pr_count"]):
                pr_data = generate_pr_data(project_key, config, pr_counter, pr_counter)
                pr_data["project_id"] = project_id
                pr_data["repo"] = config["repo"]
                
                all_prs.append(pr_data)
                
                # Генерируем ревью если PR залит
                if pr_data["merged"]:
                    reviews = generate_reviews_for_pr(pr_data, config["reviewers"], pr_counter)
                    for review in reviews:
                        review["repo"] = config["repo"]
                        all_reviews.append(review)
                    
                    # Генерируем коммиты
                    jira_key = f"{config['jira_prefix']}-{random.randint(1, 200)}"
                    commits = generate_commits_for_pr(pr_data, config["repo"], pr_counter, jira_key)
                    for commit in commits:
                        commit["project_id"] = project_id
                        commit["repo"] = config["repo"]
                        all_commits.append(commit)

                pr_counter += 1

        # Вставляем PR
        print(f"\n💾 Вставка {len(all_prs)} Pull Requests...")
        for pr in all_prs:
            db.execute(text("""
                INSERT INTO normalized.github_pull_requests (
                    pr_id, pr_number, repo_full_name, title, state,
                    author_login, created_at, updated_at, closed_at, merged_at,
                    merged, additions, deletions, project_id,
                    head_branch, base_branch, head_sha,
                    comments_count, review_comments_count, requested_reviewers,
                    last_synced_at
                ) VALUES (
                    :pr_id, :pr_number, :repo, :title, :state,
                    :author, :created_at, :updated_at, :closed_at, :merged_at,
                    :merged, :additions, :deletions, :project_id,
                    :head_branch, :base_branch, :head_sha,
                    :comments_count, :review_comments_count, :reviewers,
                    :last_synced
                )
            """), {
                "pr_id": pr["pr_id"],
                "pr_number": pr["pr_number"],
                "repo": pr["repo"],
                "title": pr["title"],
                "state": pr["state"],
                "author": pr["author"],
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"],
                "closed_at": pr["closed_at"],
                "merged_at": pr["merged_at"],
                "merged": pr["merged"],
                "additions": pr["additions"],
                "deletions": pr["deletions"],
                "project_id": pr["project_id"],
                "head_branch": pr["head_branch"],
                "base_branch": pr["base_branch"],
                "head_sha": pr["head_sha"],
                "comments_count": pr["comments_count"],
                "review_comments_count": pr["review_comments_count"],
                "reviewers": json.dumps(pr["reviewers"]),
                "last_synced": datetime.now()
            })

        # Вставляем ревью
        print(f"💾 Вставка {len(all_reviews)} Reviews...")
        for review in all_reviews:
            db.execute(text("""
                INSERT INTO normalized.github_pull_request_reviews (
                    review_id, pr_id, repo_full_name, user_login, state,
                    body, submitted_at, last_synced_at
                ) VALUES (
                    :review_id, :pr_id, :repo, :user, :state,
                    :body, :submitted_at, :last_synced
                )
            """), {
                "review_id": review["review_id"],
                "pr_id": review["pr_id"],
                "repo": review["repo"],
                "user": review["user"],
                "state": review["state"],
                "body": review["body"],
                "submitted_at": review["submitted_at"],
                "last_synced": datetime.now()
            })

        # Вставляем коммиты
        print(f"💾 Вставка {len(all_commits)} Commits...")
        for commit in all_commits:
            db.execute(text("""
                INSERT INTO normalized.github_commits (
                    commit_sha, repo_full_name, author_login, author_name,
                    message, additions, deletions, total_changes,
                    project_id, committed_at, last_synced_at
                ) VALUES (
                    :sha, :repo, :author, :author_name,
                    :message, :additions, :deletions, :total,
                    :project_id, :committed_at, :last_synced
                )
            """), {
                "sha": commit["sha"],
                "repo": commit["repo"],
                "author": commit["author"],
                "author_name": commit["author"].replace(".", " ").title(),
                "message": commit["message"],
                "additions": commit["additions"],
                "deletions": commit["deletions"],
                "total": commit["total"],
                "project_id": commit["project_id"],
                "committed_at": commit["committed_at"],
                "last_synced": datetime.now()
            })

        db.commit()
        
        print("\n" + "=" * 70)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 70)
        
        # Проверка
        check = db.execute(text("""
            SELECT 
                p.key,
                COUNT(DISTINCT pr.id) as pr_count,
                COUNT(DISTINCT CASE WHEN pr.merged = true THEN pr.id END) as merged_prs,
                COUNT(DISTINCT rev.id) as reviews,
                COUNT(DISTINCT c.id) as commits
            FROM core.projects p
            LEFT JOIN normalized.github_pull_requests pr ON pr.project_id = p.id
            LEFT JOIN normalized.github_pull_request_reviews rev ON rev.pr_id = pr.pr_id
            LEFT JOIN normalized.github_commits c ON c.project_id = p.id
            GROUP BY p.key
            ORDER BY p.key
        """)).fetchall()
        
        print("\n📈 Распределение по проектам:")
        for row in check:
            print(f"   {row[0]}: {row[1]} PR ({row[2]} merged), {row[3]} ревью, {row[4]} коммитов")
        
        print("\n💡 Готово! Можно запускать метрики:")
        print("   - PR Cycle Time")
        print("   - Review Metrics")
        print("   - Review Friction")
        print("   - Stability Score")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
