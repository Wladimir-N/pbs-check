#!/bin/bash
# пароль от root
export PBS_PASSWORD='Rm6wTrdNWDDpec~6'

# исключить из проверки бекапы перечисленных виртуалок и контейнеров в соответствующих DataStore
export DatastoreTypeVMID=DATASTORE-ct-VMID/DATASTORE-vm-VMID

# Настройки доставки в телеграм чат
export chat_id=-441147659
export token=2311215865:BBDf-SadX4T6rlXTbu3ljdcBugVBqVIlv1ff
telegramm () {
	test=
	while [ "$(echo $test | cut -d '"' -f 2)" != "ok" ]; do
		test=$(curl --header 'Content-Type: application/json' --request 'POST' --data "{\"chat_id\":\"${chat_id}\",\"parse_mode\":\"HTML\",\"text\":\"$1\"}" "https://api.telegram.org/bot${token}/sendMessage")
		sleep 1
	done
}

# Настройки отправки на email
# требуется установка пакета mailutils
# почтовый ящики на который присылать оповещения, если не нужен, закоментируйте
export email=info@settin.ru
# почтовый ящик на который присылать оповещения в html если у Вас в обычном формате всё съезжает, если не нужен, закоментируйте
export email_html=info@settin.ru
send_email () {
  if [ ! -z ${email} ]
  then
    echo "$2" | mail -s "no backup - $(hostname -f) - $1" ${email}
  fi
  if [ ! -z ${email_html} ]
  then
    echo "<code>$2</code>" | mail -s "$no backup - (echo -e "$(hostname -f) - $1\nContent-Type: text/html")" ${email_html}
  fi
}

while read datastore
do
	export PBS_REPOSITORY=${datastore}
	export check="$(proxmox-backup-client list | grep -vE "($(echo ${DatastoreTypeVMID} | tr '/' '\n' | grep "${datastore}-" | cut -d '-' -f2,3 | tr '-' '/' | tr '\n' '|')$(date +"/%Y-%m-%dT")|$(date -d "1 day ago"  +"/%Y-%m-%dT")|├)")"
	if [ "$(proxmox-backup-client list | grep -vE "($(date +"/%Y-%m-%dT")|$(date -d "1 day ago"  +"/%Y-%m-%dT")|├)" | grep -E '(ct|vm)/' | wc -l)" -gt "0" ]
	then
    send_email "${datastore}" "${check}"
		echo "${check}" | mail -s "no backup - $(hostname -f) - $datastore" info@settin.ru
		telegramm "$(hostname -f) - $datastore<code>$(proxmox-backup-client list | grep -vE "($(date +"/%Y-%m-%dT")|$(date -d "1 day ago"  +"/%Y-%m-%dT")|├)")</code>"
	fi
done < <(proxmox-backup-manager datastore list --output-format json-pretty | grep '    "name": ' | cut -d '"' -f4)
