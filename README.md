# pbs-check
Проверка наличия бекапов в Proxmox Backup Server

Для работы скрипта скопируйте .env.example в .env и заполните переменне своими данными

Коментарии по тому как заполнять эти переменные и примеры заполнения даны в самом .env.example

Для работы скрипта нужены дополнительный пакеты, python3-python-telegram-bot устанавливаете если вам нужна отправка уведомлений в телеграм

<code>apt install --no-install-recommends python3-dotenv git python3-python-telegram-bot</code>

<code>git clone https://github.com/Wladimir-N/pbs-check.git -b python3</code>

<code>cd pbs-check</code>

<code>cp .env.example .env</code>

<code>nano .env</code>

<code>python3 pbs-check.py</code>
