DATE=$(date +%Y-%m-%d)
URL=https://ibl.flatironinstitute.org/json/${DATE}_alyxfull.sql.gz
LOGIN=$(cat ~/.one_params | jq -r '.HTTP_DATA_SERVER_LOGIN')
PWD=$(cat ~/.one_params | jq -r '.HTTP_DATA_SERVER_PWD')
FILESIZE=$(curl -u $LOGIN:$PWD -sI $URL | grep -i Content-Length | awk '{print $2 + 0}')

# # macOS:
# #alias NOTIF='/Users/username/Library/Python/3.8/bin/ntfy -t "Alyx backup" send '

# Ubuntu:
function NOTIF() {
    notify-send "$1" "$2"
}

if [[ $FILESIZE -lt 600000000 ]]
then
    NOTIF "ALYX BACKUP ALERT" "Backup failed on $DATE, file was $FILESIZE bytes"
else
    NOTIF "Alyx backup" "Alyx backup for $DATE was $FILESIZE bytes"
fi
