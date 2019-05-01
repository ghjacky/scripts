import jenkins
import argparse
from functools import wraps
import sys
import json
import requests
import time
import os
import re

TOKEN = '36e2e2c59d5a5ae19f9a4e63ea22d2c9'
USER = 'user01'
PASS = 'passforuser01'
TEMPDEPSWAPFILE = '/tmp/.jktool_dependency_temp'
ISTOPJOB = 0

# 单例装饰器
def singleins(cls):
    instances = {}

    @wraps(cls)
    def wrapper(**kwargs):
        if not instances.get(cls, None):
            instances[cls] = cls(**kwargs)
        return instances[cls]
    return wrapper


# 单例模式
@singleins
class JK (object):
    def __init__(self, host='<string>'):
        self.token = TOKEN
        self.user = USER
        self.password = PASS
        self.host = host
        crumburl = "http://{0}:{1}@{2}/crumbIssuer/api/json".format(self.user, self.token, self.host)
        self.crumb = requests.get(crumburl).json()
        self.server = jenkins.Jenkins("http://" + self.host, username=self.user, password=self.password)
        self.server.crumb = self.crumb

    def _build(self, jobname, params):
        return self.server.build_job(jobname, token=self.token, parameters=params)

    def build(self, jobname, params):
        return self._build(jobname, params)


# job build
def jk_jobs(jenkinshost, jobname, params):
    jk = JK(host=jenkinshost)
    try:
        jk.server.assert_job_exists(jobname)
    except jenkins.JenkinsException as e:
        print("[ERROR]  -   Job with name {0} doesn't exists. System exit with None zero code: -1".format(jobname))
        print(e)
        sys.exit(-1)
    queue_id = jk.build(jobname, params)
    while True:
        time.sleep(0.5)
        build_info = jk.server.get_queue_item(queue_id, depth=1)
        if not build_info["executable"]["building"]:
            break
    build_status = build_info["executable"]["result"]
    build_number = build_info["executable"]["number"]
    return build_number, queue_id, build_status


# 获取命令行参数
def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--jenkins_host', metavar='jenkins_host', type=str,
                        help='define the jenkins address')
    parser.add_argument('--view_name', metavar='view_name', type=str,
                        help='define the jenkins view name in which the jobs is')
    parser.add_argument('--jobs', metavar='jobs', type=json.loads,
                        help='define the jenkins job name to be invoked')
    parser.add_argument('--parameters', metavar='parameters', type=json.loads,
                        help='define the k-v parameters which would used by invoked job')
    parser.add_argument('--action', metavar='str', type=str,
                        help='define what operation should be done to the job')
    return parser.parse_args()


def rmtempfile(flag):
    if flag:
        print("##### ISTOPJOB: {0}".format(flag))
        try:
            os.remove(TEMPDEPSWAPFILE)
        except:
            print("##############"
                  "#####  删除临时文件：{0}失败！，请务必手动删除！！！！  #####"
                  "##############".format(TEMPDEPSWAPFILE))


if __name__ == '__main__':
    pargs = get_args()
    jenkins_host = getattr(pargs, 'jenkins_host')
    jobs = getattr(pargs, 'jobs')
    view_name = getattr(pargs, 'view_name')
    parameters = getattr(pargs, 'parameters')
    action = getattr(pargs, 'action')
    assert isinstance(jobs, dict)
    assert isinstance(parameters, dict)
    # 创建jktool记录依赖jobs的临时文件,如果不存在。如果创建，则说明调用此jktool的job为顶层job
    try:
        open(TEMPDEPSWAPFILE, 'r').close()
        ISTOPJOB = 0
    except FileNotFoundError:
        open(TEMPDEPSWAPFILE, 'w+').close()
        print("####### SET ISTOPJOB = {0}".format(1))
        ISTOPJOB = 1
    temp_dependency_file = open(TEMPDEPSWAPFILE, 'ab+')
    # 循环遍历jobs，并获取设定的编译分支，如果分支为空则使用命令行参数parameters中设定的branch值
    for job in jobs.items():
        job_name = job[0]
        job_branch = job[1]
        # 检测此job名称是否在job依赖临时记录文件里，如果有则跳过
        temp_dependency_file.seek(0, os.SEEK_SET)
        dependency_jobs = temp_dependency_file.read()
        if re.findall(r'{0}'.format(job_name), dependency_jobs.decode('utf-8')):
            continue
        # 如果shell中定义的dependency_jobs中的分支不为空则使用改变量中定义的相应job的分支
        if job_branch:
            parameters.update({"branch": job_branch})
        if job_name:
            # 如果special构建参数存在，并且special指定的job名与当前一致，则使用special中指定的分支；
            # 分支使用优先级：parameters: special -> <dependency_jobs item>[1] -> parameters: branch
            specials_string = parameters.get('special', None)
            assert isinstance(specials_string, str)
            if specials_string:
                for special_item in specials_string.split(','):
                    special_name = special_item.split(':')[0]
                    special_branch = special_item.split(':')[1]
                    if special_name == job_name:
                        parameters.update({"branch": special_branch})
                        break
            build_number, queue_id, res = jk_jobs(jenkins_host, job_name, parameters)
            console_url = '/'.join(['http://' + jenkins_host, 'job', job_name, str(build_number), 'console'])
            print("res:::: ", res)
            if res == "SUCCESS":
                print("[INFO]   -   Job {0} ({1}) with queue id {2} build successfully!".format(job_name, build_number,
                                                                                               queue_id))
                # 编译成功则把此依赖job写入依赖job的临时记录文件
                temp_dependency_file.write(bytes('{0}\n'.format(job_name), encoding='utf-8'))

            elif res == "FAILURE":
                print("[ERROR]   -   Job {0} ({1}) with queue id {2} Failed: {3}".format(job_name, build_number,
                                                                                         queue_id, console_url))
                temp_dependency_file.close()
                rmtempfile(ISTOPJOB)
                sys.exit(-2)
            elif not res:
                print("[INFO]   -   Job {0} ({1}) with queue id {2} not changed!".format(job_name, build_number,
                                                                                         queue_id))
                temp_dependency_file.close()
                rmtempfile(ISTOPJOB)
                sys.exit(-3)

    temp_dependency_file.close()
    rmtempfile(ISTOPJOB)
    sys.exit(0)

