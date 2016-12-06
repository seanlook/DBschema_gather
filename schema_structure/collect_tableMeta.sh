# !/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH

mydumper=`which mydumper`
if [ "$mydumper" = "" ]; then
  echo "Error: can not find mydumper"
  exit $?
fi

cd `dirname $0`
outdir='./DBschema'
curdate=$(date +%Y%m%d-%H%M%S)
db_env=$(python settings_parser.py env)
git pull origin master

python settings_parser.py | while read line
do
  # event not
  MYDUMPER_CMD="$mydumper -k -v 1 -G -R -d "
  db_instance="${line}"
  eval $(echo ${db_instance} | awk '{print "db_id="$1; print "db_host="$2; print "db_port="$3; print "db_user="$4; print "db_pass="$5;}')
  #echo $db_id $db_host $db_port $db_user $db_pass
  if [ "$db_id" != "" ]; then
    outdir="${db_env}/${db_id}"
    if [ ! -d "$outdir" ]; then
      mkdir -p $outdir
    fi
    MYDUMPER_CMD="$MYDUMPER_CMD -h $db_host -P $db_port -u $db_user -p $db_pass --outputdir $outdir"
    echo $MYDUMPER_CMD
    rm -f $outdir/*
    $MYDUMPER_CMD
    sed -i 's/AUTO_INCREMENT=[0-9]* //g' $outdir/*
  fi
done


git add -A
# git commit -m "($db_env) DB schema snapshot: $curdate | big change"
 git commit -m "($db_env) DB schema snapshot: $curdate | $(git status -s)"
git push origin master
