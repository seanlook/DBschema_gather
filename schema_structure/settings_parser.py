#coding:utf8
from ConfigParser import ConfigParser
from socket import gethostname
import sys

"""
Author: seanlook7@gmail.com
Date:   2016-11-25 written
Description: 读取settings.ini配置，获取当前环境、组合DB列表
"""
SETTINGS_INI = "settings.ini"

# 形式格式化后的db列表，交给shell处理
def get_setttings(sect='', opt=''):
    cf = ConfigParser()
    cf.read(SETTINGS_INI)

    env = get_env()

    default_u_p = cf.get(env, env + "_auth").split(":")

    db_instances = []

    dblist = cf.items(env)
    for dbid, dbinfo_str in dblist:
        if dbid.startswith("db_"):
            db_one = [dbid]
            dbinfo = dbinfo_str.split(":")
            try:
                if 0 in (len(dbinfo[2]), len(dbinfo[3])):
                    dbinfo[2] = default_u_p[0]
                    dbinfo[3] = default_u_p[1]
            except IndexError:
                dbinfo.insert(2, default_u_p[0])
                dbinfo.insert(3, default_u_p[1])

            db_one.extend(dbinfo)
            db_instances.append(db_one)

    dblist_output = ""
    for db in db_instances:
        dblist_output += " ".join(db) + "\n"

    print dblist_output

# 根据当前主机名，获取对应的环境
def get_env():
    cf = ConfigParser()
    cf.read(SETTINGS_INI)
    envs = cf.items("environment")
    this_host = gethostname()

    env = ""
    for e in envs:
        if e[1] == this_host:
            env = e[0]
            break
    if env == "":
        print "Error can not find the enviroment for '%s'" % this_host
        sys.exit(-1)
    else:
        return env

if __name__ == '__main__':
    if len(sys.argv) == 2:
        if sys.argv[1] == 'env':
            print get_env()
        else:
            print 'Error wrong usage'
    else:
        get_setttings()