# 监控MySQL你还应该收集表信息

## 1. Story
也许你经常会被问到，库里某个表最近一年的内每个月的数据量增长情况。当然如果你有按月分表比较好办，挨个 `show table status`，如果只有一个大表，那估计要在大家都休息的时候，寂寞的夜里去跑sql统计了，因为你只能获取当前的表信息，历史信息追查不到了。

除此以外，作为DBA本身也要对数据库空间增长情况进行预估，用以规划容量。我们说的表信息主要包括：

1. 表数据大小（DATA_LENGTH）
2. 索引大小(INDEX_LENGTH)
3. 行数（ROWS）
4. 当前自增值（AUTO_INCREMENT，如果有）

目前是没有看到哪个mysql监控工具上提供这样的指标。这些信息不需要采集的太频繁，而且结果也只是个预估值，不一定准确，所以这是站在一个全局、长远的角度去监控(采集)表的。

本文要介绍的自己写的采集工具，是基于组内现有的一套监控体系：
- `InfluxDB`：时间序列数据库，存储监控数据
- `Grafana`：数据展示面板
- `Telegraf`：收集信息的agent
  看了下 telegraf 的最新的 [mysql 插件](https://github.com/influxdata/telegraf/tree/master/plugins/inputs/mysql)，一开始很欣慰：支持收集 Table schema statistics 和 Info schema auto increment columns。试用了一下，有数据，但是如前面所说，除了自增值外其他都是预估值，telegraf收集频率过高没啥意义，也许一天2次就足够了，它提供的 `IntervalSlow`选项固定写死在代码里，只能是放缓 global status 监控频率。不过倒是可以与其它监控指标分开成两份配置文件，各自定义收集间隔来实现。
  最后打算自己用python撸一个，上报到influxdb里 :)

## 2. Concept
完整代码见 GitHub项目地址：[DBschema_gather](https://github.com/seanlook/DBschema_gather)
实现也特别简单，就是查询 `information_schema` 库的 `COLUMNS`、`TABLES` 两个表：

```
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
```

关于 `auto_increment`，我们除了关注当前增长到哪了，还会在意相比 `int / bigint` 的最大值，还有多少可用空间。于是计算了 `autoIncrUsage` 这一列，用于保存当前已使用的比例。

然后使用 InfluxDB 的python客户端，批量存入influxdb。如果没有InfluxDB，结果会打印出json —— 这是Zabbix、Open-Falcon这些监控工具普遍支持的格式。

最后就是使用 Grafana 从 influxdb 数据源画图。

## 3. Usage
1. 环境
在 python 2.7 环境下编写的，2.6，3.x没测。
运行需要`MySQLdb`、`influxdb`两个库：
```
$ sudo pip install mysql-python influxdb
```

2. 配置
`settings_dbs.py` 配置文件
  - `DBLIST_INFO`：列表存放需要采集的哪些MySQL实例表信息，元组内分别是连接地址、端口、用户名、密码
  用户需要select表的权限，否则看不到对应的信息.
 - `InfluxDB_INFO`：influxdb的连接信息，注意提前创建好数据库名 `mysql_info`
 设置为 `None` 可输出结果为json.

3. 创建influxdb上的数据库和存储策略
存放2年，1个复制集：（按需调整）
```
CREATE DATABASE "mysql_info"
CREATE RETENTION POLICY "mysql_info_schema" ON "mysql_info" DURATION 730d REPLICATION 1 DEFAULT
```
看大的信息类似于：
![schema-influxdb-data][1]

4. 放crontab跑
可以单独放在用于监控的服务器上，不过建议在生产环境可以运行在mysql实例所在主机上，安全起见。
一般库在晚上会有数据迁移的动作，可以在迁移前后分别运行 `mysql_schema_info.py` 来收集一次。不建议太频繁。
```
40 23,5,12,18 * * * /opt/DBschema_info/mysql_schema_info.py >> /tmp/collect_DBschema_info.log 2>&1
```

5. 生成图表

导入项目下的 `grafana_table_stats.json` 到 Grafana面板中。效果如下：
![表数据大小和行数][2]
*表数据大小和行数*

![每天行数变化增量,auto_increment使用率][3]
*每天行数变化增量,auto_increment使用率*

## 4. More  
1. 分库分表情况下，全局唯一ID在表里无法计算 autoIncrUsage  
2. 实现上其实很简单，更主要的是唤醒收集这些信息的意识  
3. 可以增加 Graphite 输出格式  


  [1]: http://7q5fot.com1.z0.glb.clouddn.com/mysql-schema-statistics.png
  [2]: http://7q5fot.com1.z0.glb.clouddn.com/mysql-schema-statistics2.png
  [3]: http://7q5fot.com1.z0.glb.clouddn.com/mysql-schema-statistics3.png
