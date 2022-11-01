#!/bin/bash
source $(dirname "$(realpath $0)")/.env
telegramm () {
	if [ ! -z ${chat_id} ] && [ ! -z ${token} ]
	then
		test=
		while [ "$(echo $test | cut -d '"' -f 2)" != "ok" ]; do
			test=$(curl --header 'Content-Type: application/json' --request 'POST' --data "{\"chat_id\":\"${chat_id}\",\"parse_mode\":\"HTML\",\"text\":\"$1\"}" "https://api.telegram.org/bot${token}/sendMessage")
			sleep 1
		done
	fi
}
send_email () {
	if [ ! -z ${email} ]
	then
		echo "$2" | mail -s "no backup - $(hostname -f) - $1" ${email}
	fi
	if [ ! -z ${email_html} ]
	then
		echo "<code>$2</code>" | mail -s "$no backup - $(echo -e "$(hostname -f) - $1\nContent-Type: text/html")" ${email_html}
	fi
}
while read datastore
do
	export PBS_REPOSITORY=${datastore}
	export check="$(proxmox-backup-client list | grep -vE "($(echo ${DatastoreTypeVMID} | tr '/' '\n' | grep "${datastore}-" | cut -d '-' -f2,3 | tr '-' '/' | tr '\n' '|')$(date +"/%Y-%m-%dT")|$(date -d "1 day ago"  +"/%Y-%m-%dT")|├)")"
	if [ "$(proxmox-backup-client list | grep -vE "($(date +"/%Y-%m-%dT")|$(date -d "1 day ago"  +"/%Y-%m-%dT")|├)" | grep -E '(ct|vm)/' | wc -l)" -gt "0" ]
	then
    		send_email "${datastore}" "${check}"
		telegramm "$(hostname -f) - $datastore<code>${check}</code>"
	fi
done < <(proxmox-backup-manager datastore list --output-format json-pretty | grep '    "name": ' | cut -d '"' -f4)
