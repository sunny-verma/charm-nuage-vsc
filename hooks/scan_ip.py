#!/usr/bin/python

# import os
# import sys
import subprocess
import threading

from charmhelpers.core.hookenv import (
    log,
    ERROR,
)


class ScannerThread(threading.Thread):
    def __init__(self, threadId, name, lower, upper, subnet, logging):
        threading.Thread.__init__(self)
        self.threadId = threadId
        self.name = name
        self.lower = lower
        self.upper = upper
        self.subnet = subnet
        self.logging = logging

    def run(self):
        log_level = ERROR
        if not self.logging:
            log_level = None
        # log("Running scanner for thread {0}".format(self.name),
        #  level=log_level)
        for i in range(self.lower, self.upper):
            if(i != 0 and i != 255):
                try:
                    ip = self.subnet + str(i)
                    # log("Scanning for ip: {0}".format(ip),
                    #  level=log_level)
                    # we don't care about the output here, for
                    #  all we know the return code is 1
                    subprocess.call(['ping', '-w1', ip])
                except ValueError:
                    log("ping command failed with value error",
                        level=log_level)
                    return
                except subprocess.CalledProcessError, e:
                    log("ping command failed with error {0}"
                        .format(e.returncode), level=log_level)
                    return


def scan_ips(numThreads, subnet):
    threads = []
    for i in range(0, numThreads):
        thread_i = ScannerThread(i, "Thread-"+str(i),
                                 i*255/numThreads,
                                 (i+1)*255/numThreads,
                                 subnet, False)
        threads.append(thread_i)
        thread_i.start()

    for t in threads:
        t.join()


def run_arping(vm_name):
    source_ip = subprocess.check_output(
        ['bash', '-c', 'ifconfig br0 | grep "inet addr"'])
    source_ip = source_ip.strip().split(":", 1)[1].split(" ", 1)[0]
    source_hw_addr = subprocess.check_output(
        ['bash', '-c', 'ifconfig br0 | grep \'HWaddr\''
                       ' | awk \'{print $NF}\''])
    source_hw_addr = source_hw_addr.strip('. \n')
    cmd = 'virsh domiflist ' + vm_name + \
          ' | grep br0 | grep -o -E \"([0-9a-f]{2}:){5}([0-9a-f]{2})\" '
    dest_hw_addr = subprocess.check_output(['bash', '-c', cmd])\
        .strip('. \n')
    arpCmd = 'sudo arping -S ' + source_ip +\
             ' -s ' + source_hw_addr + ' -p ' + \
             dest_hw_addr + ' -i br0 ' + ' -c 3'
    subprocess.call(['bash', '-c', arpCmd])


def get_dns_ip():
    source_ip = subprocess.check_output(
        ['bash', '-c', 'ifconfig br0 | grep "inet addr"'])
    source_ip = source_ip.strip().split(":", 1)[1].split(" ", 1)[0]
    cmd = 'nslookup ' + source_ip + ' | grep Server |' \
                                    ' awk \'{print $NF}\' '
    return subprocess.check_output(['bash', '-c', cmd])\
        .strip()

if __name__ == "__main__":
    scan_ips(15, "192.168.2.")
