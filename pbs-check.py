import json
import subprocess
from datetime import datetime, timedelta
# apt install --no-install-recommends python3-dotenv
from dotenv import load_dotenv
import os

# Загрузка переменных из файла .env
load_dotenv()

# Получение значения переменной N из файла .env
N = int(os.environ.get("DAYS"))

# Получение списка пропущенных бэкапов из переменной окружения SKIPPED_BACKUPS
skipped_backups = os.getenv("SKIPPED_BACKUPS")

# Преобразование списка пропущенных бэкапов в словарь
if skipped_backups:
    skipped_backups = skipped_backups.split(",")
    skipped_backups_dict = {}
    for backup in skipped_backups:
        backup_data = backup.split(":")
        backup_id = backup_data[0]
        backup_type = backup_data[1]
        backup_datastore = backup_data[2]
        if len(backup_data) == 4:
            backup_namespace = backup_data[3]
        else:
            backup_namespace = None
        skipped_backups_dict[backup_id] = {"type": backup_type, "datastore": backup_datastore, "namespace": backup_namespace}
else:
    skipped_backups_dict = {}

# Выполнение команды и получение списка имен datastore'ов
output = subprocess.check_output("proxmox-backup-manager datastore list --output-format json", shell=True)
datastores = json.loads(output)
datastore_names = [datastore["name"] for datastore in datastores]

# Формирование списка репозиториев
pbs_repositories = [f"{os.popen('hostname -f').read().strip()}:{name}" for name in datastore_names if name]

# Проверка каждого репозитория
for pbs_repository in pbs_repositories:
    # Получение списка namespace'ов из репозитория
    raw_namespaces = os.popen(f"proxmox-backup-client namespace list --repository {pbs_repository}").read().strip()
    namespaces = raw_namespaces.splitlines()
    _, datastore = pbs_repository.split(":")

    # Если в репозитории есть namespace'ы, то проверяем каждый из них
    if namespaces:
        for namespace in namespaces:
            # Загрузка списка бэкапов из команды "proxmox-backup-client list"
            raw_backups = os.popen(f"proxmox-backup-client list --repository {pbs_repository} --ns {namespace} --output-format json").read().strip()

            # Преобразование JSON в объекты Python
            backups = json.loads(raw_backups)

            # Список машин, у которых не было бэкапов за последние N дней
            machines_without_backups = []

            # Проверка каждого бэкапа
            for backup in backups:
                # Если backup-id есть в списке пропущенных бэкапов и backup-type совпадает, то пропускаем его
                if backup["backup-id"] in skipped_backups_dict and skipped_backups_dict[backup["backup-id"]]["type"] == backup["backup-type"] and skipped_backups_dict[backup["backup-id"]]["datastore"] == datastore and (not skipped_backups_dict[backup["backup-id"]]["namespace"] or skipped_backups_dict[backup["backup-id"]]["namespace"] == namespace):
                    continue
                # Преобразование времени последнего бэкапа в формат datetime
                last_backup_time = datetime.fromtimestamp(backup["last-backup"])
                # Вычисление разницы между текущим временем и временем последнего бэкапа
                delta = datetime.now() - last_backup_time
                # Если разница больше N дней и у машины нет комментария, то добавляем её в список
                if delta >= timedelta(days=N) and not backup.get("comment"):
                    machines_without_backups.append(backup["backup-type"] + " " + backup["backup-id"])

            # Вывод списка машин без бэкапов
            if machines_without_backups:
                print(f"Список машин без бэкапов за последние {N} дней ({pbs_repository}, {namespace}):")
                for machine in machines_without_backups:
                    print(machine)
            else:
                print(f"Все машины имеют бэкапы за последние {N} дней ({pbs_repository}, {namespace}).")
    # Если в репозитории нет namespace'ов, то проверяем все бэкапы
    else:
        # Загрузка списка бэкапов из команды "proxmox-backup-client list"
        raw_backups = os.popen(f"proxmox-backup-client list --repository {pbs_repository} --output-format json").read().strip()

        # Преобразование JSON в объекты Python
        backups = json.loads(raw_backups)

        # Список машин, у которых не было бэкапов за последние N дней
        machines_without_backups = []

        # Проверка каждого бэкапа
        for backup in backups:
            # Если backup-id есть в списке пропущенных бэкапов и backup-type совпадает, то пропускаем его
            if backup["backup-id"] in skipped_backups_dict and skipped_backups_dict[backup["backup-id"]]["type"] == backup["backup-type"] and skipped_backups_dict[backup["backup-id"]]["datastore"] == datastore and (not skipped_backups_dict[backup["backup-id"]]["namespace"] or skipped_backups_dict[backup["backup-id"]]["namespace"] == namespace):
                continue
            # Преобразование времени последнего бэкапа в формат datetime
            last_backup_time = datetime.fromtimestamp(backup["last-backup"])
            # Вычисление разницы между текущим временем и временем последнего бэкапа
            delta = datetime.now() - last_backup_time
            # Если разница больше N дней и у машины нет комментария, то добавляем её в список
            if delta >= timedelta(days=N) and not backup.get("comment"):
                machines_without_backups.append(backup["backup-type"] + " " + backup["backup-id"])

        # Вывод списка машин без бэкапов
        if machines_without_backups:
            print(f"Список машин без бэкапов за последние {N} дней ({pbs_repository}):")
            for machine in machines_without_backups:
                print(machine)
        else:
            print(f"Все машины имеют бэкапы за последние {N} дней ({pbs_repository}).")
