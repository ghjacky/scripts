#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script name: log_cleaner.py
Author: guomingyang
Version: v1.0.0
"""

import logging
from logging.handlers import RotatingFileHandler
from multiprocessing import pool
from os import listdir, remove
from os.path import isfile, join, getmtime, isdir
from datetime import datetime, timedelta
import time
import types


# 配置(此处LOG_ROOT配置必须为元组)
LOG_ROOT = ('/var/log', '/data/nginx_logs', '/home/xdjl/logs')
LOG_EXPIR_TIME = 30 #天

# 定义需要跳过的目录（防止误删）
DIR_GOD = '/'
DIR_TOBE_SKIPPED = ('/usr', '/sbin', '/bin', '/proc',
                    '/home/xdjl/app',
                    '/home/xdjl/customLib',
                    '/home/xdjl/kafka.client.truststore.jks',
                    '/home/xdjl/bin', '/boot', '/etc',
                    '/root', '/dev', '/run', '/sys',
                    '/lib', '/lib64', '/var/lib', '/var/local', '/var/mail',
                    '/var/spool', '/var/opt', '/var/run')

# 日志配置
logfile = '/var/log/log_cleaner.log'
logformater = logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s(%(lineno)d) %(message)s')
loghandler = RotatingFileHandler(filename=logfile, mode='a', maxBytes=5*1024*1024, backupCount=2)
loghandler.setFormatter(logformater)
mylog = logging.getLogger('root')
mylog.setLevel(logging.DEBUG)
mylog.addHandler(loghandler)

# 日志过期时间戳
log_expir_timestamp = time.mktime((datetime.now() - timedelta(
    LOG_EXPIR_TIME)).timetuple())


def shouldbeskipped(d):
    return (1 if DIR_GOD == d else 0) + sum([1 if d.startswith(x) else 0
                                             for x in DIR_TOBE_SKIPPED])


# 目录遍历生成器
def getexpiredlog(directory):
    # 如果传参不是目录直接return
    if not isdir(directory):
        mylog.warning("Dir {0} doesn't exist!".format(directory))
        return
    # 遍历目录
    for x in listdir(directory):
        # 文件绝对路径
        abpath = join(directory, x)
        if isfile(abpath):
            # 如果是普通文件，则看其修改时间是否在过期时间戳之前
            if float(getmtime(abpath)) < float(log_expir_timestamp):
                # 如果过期则yield改文件的绝对路径
                yield abpath
            continue
        else:
            # 如果是目录，则调用自身递归遍历该目录
            yield getexpiredlog(abpath)


def recursgenerator(gen):
    for x in gen:
        if not isinstance(x, types.GeneratorType):
            try:
                # 根据DIR_GOD和DIR_TOBE_SKIPPED的配置判断是否该删除此文件
                if not shouldbeskipped(x):
                    mylog.info('Deleting file: {0}'.format(x))
                    remove(x)
                else:
                    mylog.warning('Skipped file: {0}'.format(x))
            except:
                mylog.error('文件删除失败！{0}'.format(x))
                continue
        else:
            recursgenerator(x)


if __name__ == "__main__":
    for directory in LOG_ROOT:
        if not shouldbeskipped(directory):
            mylog.info('Rescuring directory: {0}'.format(directory))
            recursgenerator(getexpiredlog(directory))
        else:
            mylog.warning('Skipped directory: {0}'.format(directory))
            exit(0)
