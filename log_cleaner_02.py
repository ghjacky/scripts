#!/usr/bin/python
# encoding: utf-8

import argparse
import os
import types
import time
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler

# 脚本自身执行日志配置
logfile = '/tmp/log_cleaner.log'
logformater = logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s(%(lineno)d) %(message)s')
loghandler = RotatingFileHandler(filename=logfile, mode='a', maxBytes=5*1024*1024, backupCount=2)
loghandler.setFormatter(logformater)
mylog = logging.getLogger('root')
mylog.setLevel(logging.DEBUG)
mylog.addHandler(loghandler)


def get_log_file(path, _postfix, _expire):
    assert isinstance(path, str)
    # 根据最终修改时间和expire的值计算日志过期时间戳
    log_expir_timestamp = time.mktime((datetime.now() - timedelta(_expire)).timetuple())
    if not os.path.isdir(path):
        mylog.error("{0} is not a directory".format(path))
        return
    for f in os.listdir(path):
        pathtmp = os.path.join(path, f)
        # 如果符合日志处理规则 则yield该日志文件路径
        if os.path.isfile(pathtmp) and pathtmp.endswith(_postfix):
            if _expire == 0:
                yield pathtmp
            elif float(os.path.getmtime(path)) <= float(log_expir_timestamp):
                yield pathtmp
            else:
                continue
        # 如果是目录则递归调用get_log_file，yield一个生成器
        elif os.path.isdir(pathtmp):
            yield get_log_file(pathtmp, _postfix, _expire)
        else:
            continue


def deal_with_file(gen, _remove):
    assert isinstance(gen, types.GeneratorType)
    for path in gen:
        # 如果不是生成器，则应该是符合处理规则的日志文件路径，根据remove参数来确定是删文件还是清内容（保持inode不变）
        if not isinstance(path, types.GeneratorType):
            if _remove:
                try:
                    mylog.info('Deleting file: {0}'.format(path))
                    os.remove(path)
                except:
                    mylog.error('Failed to delete file: {0}'.format(path))
                    continue
            else:
                try:
                    mylog.info('Clearing content of file: {0}'.format(path))
                    open(path, 'w').close()
                except:
                    mylog.error('Failed to clear content of file: {0}'.format(path))
        # 如果是生成器，则递归调用deal_with_file来处理该生成器返回的日志文件
        else:
            deal_with_file(path, _remove)


def parseArg():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--directory', type=str, help="日志文件所在的顶层目录")
    parser.add_argument('-p', '--postfix', type=str, help="日志文件后缀")
    parser.add_argument('--remove', dest='remove', action='store_true', help="删除文件")
    parser.add_argument('-e', '--expire', type=int, help="过期时间（天）")
    parser.add_argument('--not-remove', dest='remove', action='store_false', help="仅清空文件内容，不删除文件")
    # 设置默认参数，如果不加相应选项，则使用一下默认值
    parser.set_defaults(remove=False, postfix='.log', expire=30)
    return parser.parse_args()


if __name__ == "__main__":
    args = parseArg()
    directory = args.directory
    postfix = args.postfix
    remove = args.remove
    expire = args.expire
    mylog.info("dir: {0}; postfix: {1}; remove: {2}; expire: {3}".format(directory, postfix, remove, expire))
    deal_with_file(get_log_file(directory, postfix, expire), remove)

