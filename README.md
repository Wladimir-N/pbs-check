# pbs-check
Проверка наличия бекапов в Proxmox Backup Server

Данный скрипт проверяет наличие бекапов за текущий день и за вчера, те виртуалки и контейнеры у которых последний бекап старше будут присланы в оповещении в телеграм через бота и на почту.

Для работы скрипта скопируйте .env.example в .env и заполните переменне своими данными

Коментарии по тому как заполнять эти переменные и примеры заполнения даны в самом .env.example

Для работы отправки почты нужно установить mailutils

<code>apt install --no-install-recommends git mailutils curl</code>

<code>git clone https://github.com/Wladimir-N/pbs-check.git</code>

<code>ln -s $(pwd)/pbs-check/pbs-check.sh /usr/local/bin</code>

<code>cp pbs-check/.env.example pbs-check/.env</code>

<code>nano pbs-check/.env</code>
