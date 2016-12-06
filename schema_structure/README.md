# 一种直观记录表结构变更历史的方法

## 1. Story
在没有形成自己的数据库管理平台以前，数据库实例一多（包括生产和测试环境），许多表要执行DDL会变得异常繁杂。

说个自己的经历，需要改现网的一个索引来看优化的效果，因为存在风险，不会一次全改，先只改1个库，然后逐步放开。前后验证效果可能花上一两周的时间，除非实现完整的记录了当时的ddl语句和对应的库，否则根本难以记得。这就完全依赖于个人的习惯及能力。

又比如现网出了个问题，开发追查到一个时间点，想确认那个时候有没有对库表进行过更改操作，如果没有记录表结构变更的历史，也就难以提供需要的信息。
<!-- more -->

记录差异，很早就思考过能不能用git来做。终于花了一天时间来实现，并验证、修改达到预期的效果，还算满意。

## 2. Concept
思路很简单，就是利用 `mydumper` 导出表时会把各表（结构）单独导成一个文件的特性，每天低峰期导出所有对象元数据：表、视图、存储过程、事件、触发器。需要过滤掉 `AUTO_INCREMENT` 值。

结构内容存放在一个git仓库下，通过shell脚本提交到 gitlab。所有DDL更改由原来依赖于DBA的主动记录，变成被动采集。

测试环境和生产环境表结构总会有些差异，为了兼顾同时收集两个环境的数据，设置了 `environment` 选项，根据当前所在运行的机器，自动判断采集哪些实例信息。

## 3. Usage
首先你需要能够存放表结构信息的git仓库，如gitlab，而且建议设置为私有。

1. 安装 git 和 mydumper
mydumper 0.9.1 版本需要编译安装，可以参考这里 [file-mydumper-install-ubuntu14-04-sh](https://gist.github.com/nicksantamaria/66726bca586d152a3a01#file-mydumper-install-ubuntu14-04-sh)。当然 yum 或 apt-get 安装其他版本也是一样的。
脚本会尝试自动获取 `mydumper` 命令的路径。

注意配置git权限的时候，最好不允许其它用户手动提交修改仓库内容。

2. 配置db实例地址

`settings.ini`示例：
```
[environment]
production=puppetmaster
test=puppettestmaster

[production]
production_auth=your_defaultuser:yourpassword

db_name1=192.168.1.100:3306
db_name2=192.168.1.101:3306
db_name3=name3.dbhost.com:3306
db_name4=192.168.1.100:3306:myuser:mypassword

[test]
test_auth=user1:password1

db_name1=10.0.100.1:3306
db_name2=10.0.100.1:3307
db_name3=10.0.100.2:3306

db_name4=10.0.100.3:3306:myuser1:mypassword1
```

- 上面的配置采集 `production`和`test`两个环境的表结构，识别两个环境是根据 hostname 来决定的。这样做的好吃就是这个脚本在两个环境下运行不需要做任何修改。
- `[production]`节的名字就是 `[environment]`节指定的名字 *production=xx*
- `dbname1=`就是配置各个db，地址+端口的形式。用户名和密码可以继续用 `:` 跟上
- `production_auth=`表示 production 环境下，如 `dbname1`没有配置用户名时，默认采用这个用户名和密码。这样设计主要是简化配置。
  该数据库用户需要 select,show view,event,trigger,procedure 权限。

`settings_parser.py` 用于解析上面的配置文件，输出`collect_tableMeta.sh`易处理的格式。

3. 每天运行
可使用 `python settings_parser.py` 测试解析配置是否正常。

在配置文件里两个环境下（一般网络不互通）分别加上定时任务：
```
# Puppet Name: collect_DBschema
5 5 * * * /opt/DBschema/collect_tableMeta.sh >> /tmp/collect_DBschema.log 2>&1

```

4. 展示效果
![mysql_schema_info](http://7q5fot.com1.z0.glb.clouddn.com/mysql-schema-structure1.png)

`A` 是新增，`M` 是修改，`D` 是删除，一目了然。点开可以前后对比。

## 4. More
思路和实现都不难，主要是意识，和如何快速找到解决当前需求的办法。一切都是为了效率 :)

目前所能想到更多的：  
1. 有内容push到git仓库后，使用 web hook 发出邮件。  
2. 根据A,B两个表的结构，快速得到A修改成B的样子的DDL。  
3. event 权限问题。event权限没有所谓的读和修改之分，阿里云RDS就把它从 *只读* 账号里拿除了，导致收集不到事件定义。所以它的高权限账号管理模式还是很有作用的。  
4. 密码明文。  
最近公司邀请了一个安全公司给做培训，数据库安全里面，密码明文配置在文件里面是广泛存在的，难搞。 
