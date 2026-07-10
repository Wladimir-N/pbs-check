#!/usr/bin/env python3
import os
import json
import asyncio
import logging
import argparse
import signal
from datetime import datetime, timedelta
from dotenv import load_dotenv

import subprocess
import smtplib
from email.mime.text import MIMEText
import telegram

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Загружаем .env
load_dotenv()

# Аргументы CLI
parser = argparse.ArgumentParser(description='Проверка бэкапов на PBS')
parser.add_argument('--dry-run', action='store_true', help='Не отправлять уведомления, только логировать')
args = parser.parse_args()

# --- Конфигурация из .env ---
CONFIG = {
    'ignore_backup_days': int(os.getenv('ignore_backup_days', 90)),
    'N': int(os.getenv('DAYS', '30')),
    'skipped_backups': {},
    'smtp': {
        'server': os.getenv('SMTP_SERVER'),
        'port': int(os.getenv('SMTP_PORT', 587)),
        'user': os.getenv('SMTP_USERNAME'),
        'password': os.getenv('SMTP_PASSWORD'),
    },
    'mail': {
        'from': os.getenv('FROM_EMAIL'),
        'to': os.getenv('TO_EMAIL', '').split(',') if os.getenv('TO_EMAIL') else [],
    },
    'telegram': {
        'token': os.getenv('TELEGRAM_TOKEN'),
        'chat_id': os.getenv('TELEGRAM_CHAT_ID'),
    },
}

# --- Разбор пропущенных бэкапов (SKIPPED_BACKUPS) ---
skipped_str = os.getenv("SKIPPED_BACKUPS")
if skipped_str:
    for entry in skipped_str.split(','):
        parts = entry.strip().split(':')
        if len(parts) == 4:
            backup_id, backup_type, datastore, namespace = parts
            key = (backup_id, namespace)
            CONFIG['skipped_backups'][key] = {
                'type': backup_type,
                'datastore': datastore,
                'namespace': namespace,
            }
        elif len(parts) == 3:
            backup_id, backup_type, datastore = parts
            key = (backup_id, None)
            CONFIG['skipped_backups'][key] = {
                'type': backup_type,
                'datastore': datastore,
                'namespace': None,
            }

# --- Проверка: хотя бы один канал уведомлений должен быть настроен ---
has_telegram = bool(CONFIG['telegram']['token'] and CONFIG['telegram']['chat_id'])
has_email = bool(CONFIG['smtp']['server'] and CONFIG['mail']['from'] and CONFIG['mail']['to'])

if not has_telegram and not has_email:
    logging.warning("Не настроен ни Telegram, ни Email. Уведомления отправляться не будут.")
elif has_telegram:
    logging.info("Telegram уведомления настроены.")
elif has_email:
    logging.info("Email уведомления настроены.")


# --- Асинхронная отправка уведомлений ---
async def send_notifications(message, config, dry_run=False):
    # Telegram
    if config['telegram']['token'] and config['telegram']['chat_id']:
        bot = telegram.Bot(token=config['telegram']['token'])
        for i in range(0, len(message), 4096):
            chunk = message[i:i+4096]
            if not dry_run:
                try:
                    await bot.send_message(chat_id=config['telegram']['chat_id'], text=chunk)
                    logging.info(f"Отправлено в Telegram (часть {i//4096 + 1})")
                except Exception as e:
                    logging.error(f"Ошибка отправки в Telegram: {e}")
            else:
                logging.info(f"[DRY-RUN] Telegram: {chunk[:80]}...")
    else:
        logging.debug("Telegram не настроен, пропуск.")

    # Email
    smtp = config['smtp']
    mail = config['mail']
    if smtp['server'] and mail['from'] and mail['to']:
        msg = MIMEText(message)
        msg['Subject'] = f"Бэкапы за последние {CONFIG['N']} дней"
        msg['From'] = mail['from']
        msg['To'] = ', '.join(mail['to'])

        if not dry_run:
            try:
                if smtp['port'] == 587:
                    server = smtplib.SMTP(smtp['server'], smtp['port'])
                    server.starttls()
                elif smtp['port'] == 465:
                    server = smtplib.SMTP_SSL(smtp['server'], smtp['port'])
                else:
                    server = smtplib.SMTP(smtp['server'], smtp['port'])

                if smtp['user'] and smtp['password']:
                    server.login(smtp['user'], smtp['password'])

                server.sendmail(mail['from'], mail['to'], msg.as_string())
                server.quit()
                logging.info("Email отправлен успешно")
            except Exception as e:
                logging.error(f"Ошибка отправки email: {e}")
        else:
            logging.info(f"[DRY-RUN] Email отправлен бы на {', '.join(mail['to'])}")
    else:
        logging.debug("Email не настроен, пропуск.")


# --- Получение данных с PBS ---
def get_datastores():
    output = subprocess.check_output(
        "proxmox-backup-manager datastore list --output-format json", shell=True
    )
    return json.loads(output)


def get_namespaces(repo):
    cmd = f"proxmox-backup-client namespace list --repository {repo}"
    try:
        out = os.popen(cmd).read().strip()
        return out.splitlines() or [None]
    except Exception:
        return [None]


def get_backups(repo, namespace):
    if namespace:
        cmd = f"proxmox-backup-client list --repository {repo} --ns {namespace} --output-format json"
    else:
        cmd = f"proxmox-backup-client list --repository {repo} --output-format json"
    try:
        out = os.popen(cmd).read().strip()
        return json.loads(out)
    except (json.JSONDecodeError, Exception):
        return []


async def check_namespace(repo, namespace):
    issues = []
    backups = get_backups(repo, namespace)
    for backup in backups:
        backup_id = backup.get("backup-id")
        backup_type = backup.get("backup-type")
        last_ts = backup.get("last-backup")
        comment = backup.get("comment")

        key = (backup_id, namespace)
        skip = CONFIG['skipped_backups'].get(key)
        if skip:
            datastore = repo.split(':')[1] if ':' in repo else ''
            if (skip['type'] == backup_type and
                (skip['datastore'] == datastore or skip['datastore'] == '*') and
                (skip['namespace'] is None or skip['namespace'] == namespace)):
                continue

        last_dt = datetime.fromtimestamp(last_ts)
        delta = datetime.now() - last_dt
        days = delta.days

        if delta <= timedelta(days=CONFIG['ignore_backup_days']) and delta >= timedelta(days=CONFIG['N']) and not comment:
            issues.append(f"{backup_type} {backup_id} - {days} дней")

    return "\n".join(issues) if issues else ""


async def check_repo(repo):
    issues = ""
    try:
        namespaces = get_namespaces(repo)
        for ns in namespaces:
            ns_issues = await check_namespace(repo, ns)
            if ns_issues:
                ns_label = ns if ns else "(root)"
                issues += f"({repo}, {ns_label}):\n{ns_issues}\n"
        return issues
    except Exception as e:
        logging.error(f"Ошибка обработки репозитория {repo}: {e}")
        return ""


async def main():
    hostname = os.popen('hostname -f').read().strip()
    datastores = get_datastores()
    repos = [f"{hostname}:{ds['name']}" for ds in datastores if ds.get('name')]

    tasks = [check_repo(repo) for repo in repos]
    results = await asyncio.gather(*tasks)

    final_msg = "\n".join(filter(None, results))

    if final_msg:
        body = (
            f"Список машин без бэкапов за последние {CONFIG['N']} дней:\n\n"
            f"{final_msg.strip()}\n\n"
            f"Машины, не делавшие бэкапы более {CONFIG['ignore_backup_days']} дней, игнорируются."
        )
        await send_notifications(body, CONFIG, args.dry_run)
    else:
        logging.info(f"Все машины имеют бэкапы за последние {CONFIG['N']} дней. "
                     f"Машины без бэкапов более {CONFIG['ignore_backup_days']} дней игнорируются.")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: exit(0))
    if args.dry_run:
        logging.info("Режим DRY-RUN — уведомления не будут отправлены.")
    asyncio.run(main())
