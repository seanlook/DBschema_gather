#!/usr/bin/python
#coding:utf-8
"""
Description:    收集数据库表的信息：表数据大小，表索引大小，行数，当前自增ID值，自增Id使用率
                写入InfluxDB
Author: seanlook.com
Date:   2016-12-28  written
"""

import MySQLdb
from influxdb import InfluxDBClient
from influxdb.client import InfluxDBClientError
from datetime import datetime
from settings_dbs import DBLIST_INFO, InfluxDB_INFO

# UNSIGNED
MAX_INT = {"tinyint": 256,  # 2**8
           "smallint": 65536,  # 2**16
           "mediumint": 16777216,  # 2**24
           "int": 4294967296,  # 2**32
           "bigint": 18446744073709551616  # 2**64
}


def query_table_info(*dbinfo):

    sql_str = """
    SELECT
        IFNULL(@@hostname, @@server_id) SERVER_NAME,
        %s as HOST,
        t.TABLE_SCHEMA,
        t.TABLE_NAME,
        t.TABLE_ROWS,
        t.DATA_LENGTH,
        t.INDEX_LENGTH,
        t.AUTO_INCREMENT,
      c.COLUMN_NAME,
      c.DATA_TYPE,
      LOCATE('unsigned', c.COLUMN_TYPE) COL_UNSIGNED
      # CONCAT(c.DATA_TYPE, IF(LOCATE('unsigned', c.COLUMN_TYPE)=0, '', '_unsigned'))
    FROM
        information_schema.`TABLES` t
    LEFT JOIN information_schema.`COLUMNS` c ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
    AND t.TABLE_NAME = c.TABLE_NAME
    AND c.EXTRA = 'auto_increment'
    WHERE
        t.TABLE_SCHEMA NOT IN (
            'mysql',
            'information_schema',
            'performance_schema',
            'sys'
        )
    AND t.TABLE_TYPE = 'BASE TABLE'
    """
    dbinfo_str = "%s:%d" % (dbinfo[0], dbinfo[1])
    rs = ({},)
    try:
        db_conn = MySQLdb.Connect(host=dbinfo[0], port=dbinfo[1], user=dbinfo[2], passwd=dbinfo[3],
                                  connect_timeout=5)
        cur = db_conn.cursor(MySQLdb.cursors.DictCursor)
        param = (dbinfo_str,)

        print "\n[%s] Get schema info from db: '%s'..." % (datetime.today(), dbinfo_str)
        cur.execute(sql_str, param)

        rs = cur.fetchall()

    except MySQLdb.Error, e:
        print "Error[%d]: %s (%s)" % (e.args[0], e.args[1], dbinfo_str)
        exit(-1)

    if InfluxDB_INFO is not None:
        print "Write '%s' schema table info to influxdb ..." % dbinfo_str
        write_influxdb(*rs)
    else:
        print rs

def write_influxdb(*schema_info):
    rs = schema_info

    metric = "mysql_info_schema"
    """
    # create database and retention policy for your data
    CREATE DATABASE "mysql_info"
    CREATE RETENTION POLICY "mysql_info_schema" ON "mysql_info" DURATION 730d REPLICATION 1 DEFAULT
    """

    point_time = int(datetime.today().strftime('%s'))
    series = []
    datafile_size = 0
    server_name = ()
    for row in rs:
        if row['DATA_TYPE'] is not None:
            max_int = MAX_INT[row['DATA_TYPE']] * 1.0
            if row['COL_UNSIGNED'] == 0:
                max_int = max_int / 2

            auto_usage = round(row['AUTO_INCREMENT'] / max_int, 3)
        else:
            auto_usage = None

        datafile_size += (row['DATA_LENGTH']/1024 + row['INDEX_LENGTH']/1024) / 1024  # G
        server_host = (row['SERVER_NAME'], row['HOST'])
        pointValues = {
            "time": point_time,
            "measurement": metric,
            'tags': {
                'server': row['SERVER_NAME'],
                'host': row['HOST'],
                'schema': row['TABLE_SCHEMA'],
                'table': row['TABLE_NAME'],
                'autoIncrColumn': row['COLUMN_NAME']
            },
            'fields': {
                'tableRows': row['TABLE_ROWS'],
                'dataLength': row['DATA_LENGTH'],
                'indexLength': row['INDEX_LENGTH'],
                'autoIncrValue': row['AUTO_INCREMENT'],
                'autoincrUsage': auto_usage
            }
        }
        series.append(pointValues)

    metric_size = "mysql_info_size"
    series_pointValues_size = [{
        "time": point_time,
        "measurement": metric_size,
        "tags": {
            'server': server_host[0],
            'host': server_host[1]
        },
        "fields": {
            'datafile_size': datafile_size
        }
    }]

    try:
        client = InfluxDBClient(InfluxDB_INFO['host'],
                                InfluxDB_INFO['port'],
                                InfluxDB_INFO['username'],
                                InfluxDB_INFO['password'],
                                InfluxDB_INFO['database'],
                                InfluxDB_INFO['timeout'])

        client.write_points(points=series,
                            time_precision='s',
                            batch_size=100)
        client.write_points(series_pointValues_size, 's')

    except InfluxDBClientError as e:
        print "Error[%s]: %s" % (e.code, e.content)


if __name__ == '__main__':
    for db in DBLIST_INFO:
        query_table_info(*db)