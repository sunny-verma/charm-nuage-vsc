#!/usr/bin/python

import os
import sys
import subprocess
import time

from charmhelpers.core.hookenv import (
    log,
    ERROR,
)


def is_vm_running(vmconfig):
    try:
        env = os.environ.copy()
        env['VSP_VM_NAME'] = vmconfig['VSP_VM_NAME']
        run_state = subprocess.check_output(['bash', '-c',
                                             'sudo virsh list --all |'
                                             ' grep ${VSP_VM_NAME} |'
                                             ' awk \'{print $NF}\''],
                                            env=env)
        run_state = run_state.strip('. \n')
        if run_state == 'running':
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        log("Error: is_vm_running Failed with error:{}"
            .format(e.returncode), level=ERROR)
        return False


def wait_for_vm_to_be_pingable(vm_ip_address):
    try:
        pingable = '0'
        command = 'ping -c 1 %s | grep received |' \
                  ' awk \'{print $4}\'' % vm_ip_address
        for x in (1, 60):
            pingable = subprocess.check_output([
                'bash', '-c', command]).strip()
            if(pingable == '0'):
                time.sleep(10)
            else:
                log("successfully pinged {}".format(vm_ip_address))
                return
    except subprocess.CalledProcessError as  e:
        log("Error: wait_for_vm_to_be_pingable "
            "failed with error:{}".format(e.returncode),
            level=ERROR)
    log("Error: Failed to ping: {}".format(vm_ip_address))


def _run_virsh_command(cmd, vmconfig, ignore=False):
    """
    Run virsh command, checking output

    :param: cmd: str: The virsh command to run.
    """
    log_level = ERROR
    if ignore:
        log_level = None
    env = os.environ.copy()
    for key, value in list(vmconfig.items()):
        log('virsh env key:{0} value:{1}'.format(key, value))
        env[key] = value

    # env['VSP_VM_NAME'] = vmconfig['VSP_VM_NAME']
    # env['VSP_VM_DIR'] = vmconfig['VSP_VM_DIR']
    # env['VSP_VM_XML'] = vmconfig['VSP_VM_XML']
    # env['VSP_VM_IMAGE_NAME'] = vmconfig['VSP_VM_IMAGE_NAME']
    # env['VSP_VM_ORIG_IMAGE_NAME'] = vmconfig['VSP_VM_ORIG_IMAGE_NAME']
    # env['VSP_VM_IMAGE_DIR'] = vmconfig['VSP_VM_IMAGE_DIR']
    # env['VSP_VM_DISK_SIZE'] = vmconfig['VSP_VM_DISK_SIZE']
    try:
        log("execute virsh cmd {0}\n".format(cmd))
        resultstr = subprocess.check_output(cmd, env=env)
    except ValueError:
        log("Error: virsh cmd {0} Failed with error:{1}"
            .format(cmd, resultstr), level=log_level)
        if ignore:
            return
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        log("Error: virsh cmd {0} Failed with error:{1}"
            .format(cmd, e.returncode), level=log_level)
        if ignore:
            return
        sys.exit(1)
    log("virsh cmd result: {0}\n".format(resultstr))
    return resultstr


def createvm(vmconfig):
    _run_virsh_command(
        ['bash', '-c',
         'source ./hooks/lib/nuage_common.sh'
         ' && create_vsp_vm'], vmconfig)
    log("{} is successfully created."
        .format(vmconfig['VSP_VM_NAME']))


def startvm(vmconfig):
    _run_virsh_command(
        ['bash', '-c',
         'source ./hooks/lib/nuage_common.sh'
         ' && start_vsp_vm'], vmconfig)
    log("{} is successfully started."
        .format(vmconfig['VSP_VM_NAME']))


def stopvm(vmconfig):
    _run_virsh_command(
        ['bash', '-c',
         'source ./hooks/lib/nuage_common.sh'
         ' && stop_vsp_vm'], vmconfig, True)
    log("{} is successfully shutdown."
        .format(vmconfig['VSP_VM_NAME']))


def createnet(netxml, netname):
    try:
        subprocess.check_output(
            ['bash', '-c',
             'virsh net-define {}'.format(netxml)])
        subprocess.check_output(
            ['bash', '-c',
             'virsh net-start {}'.format(netname)])
    except subprocess.CalledProcessError as e:
        log("Error: createnet Failed with error:{}"
            .format(e.returncode), level=ERROR)
        return None


def install_guestfs():
    try:
        subprocess.check_output(
            ['bash', '-c', 'sudo apt-get --yes'
                           ' install libguestfs-tools'])
        subprocess.check_output(
            ['bash', '-c', 'sudo update-guestfs-appliance'])
        subprocess.check_output(
            ['bash', '-c', 'sudo chmod +r /boot/vmlinuz-*'])

    except subprocess.CalledProcessError as e:
        log("Error: install_guestfs Failed with error:{}"
            .format(str(e.returncode)), level=ERROR)
        return None


def write_guestfs(vm_img, file, contents):
    try:
        subprocess.check_output(
            ['bash', '-c', 'sudo chmod 777 {}'.format(vm_img)])
        subprocess.check_output(
            ['bash', '-c', 'guestfish add {0} : run : mount /dev/sda1 /'
                           ' : write {1} \"{2}\"'
                .format(vm_img, file, contents)])
    except subprocess.CalledProcessError as e:
        log("Error: install_guestfs Failed with error:{}"
            .format(str(e.returncode)), level=ERROR)
        return None


def get_vm_ip_address(vmconfig):
    # if vmconfig is None:
    #     return None
    vm_ip_address = _run_virsh_command(
        ['bash', '-c', 'source ./hooks/lib/nuage_common.sh'
                       ' && get_vsp_vm_ip_address'], vmconfig)
    return vm_ip_address.strip()
    # for mac in `virsh domiflist vsc |grep -o -E
    # "([0-9a-f]{2}:){5}([0-9a-f]{2})"`
    #  ; do arp -e |grep $mac  |grep -o -P
    # "^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}" ; done


def get_domain_name(ip_address):
    try:
        cmdstr = 'nslookup {} | grep -o -E \"name = .*.\"'\
            .format(ip_address)
        log('get_domain_name: {}'.format(cmdstr))
        result_str = subprocess.check_output(
            ['bash', '-c', cmdstr])
        domain_name = None
        if result_str.startswith('name = '):
            domain_name = result_str.replace('name = ', '')
            domain_name = domain_name.strip('. \n')
        return domain_name
    except subprocess.CalledProcessError as e:
        log("Error: get_domain_name Failed with error:{}"
            .format(e.returncode), level=ERROR)
        return None


def update_vsd_domain(vsc_host, username, password, vsd_domain):
    import pexpect
    try:
        ssh_newkey = 'Are you sure you want to continue connecting'
        child = pexpect.spawn('ssh %s@%s -o ConnectTimeout=1500'
                              ' -o ConnectionAttempts=300'
                              % (username, vsc_host), timeout=1500)
        log('ssh %s@%s' % (username, vsc_host))
        i = child.expect([ssh_newkey, 'password:',
                          pexpect.EOF, pexpect.TIMEOUT], 1)
        if i == 0:
            child.sendline('yes')
            i = child.expect([ssh_newkey, 'password:', pexpect.EOF])
        if i == 1:
            child.sendline(password)
        elif i == 2:
            child.close()
            raise pexpect.EOF("End of file error")
        elif i == 3:
            # timeout
            child.close()
            raise pexpect.TIMEOUT("Got a connection timeout")
        child.sendline("\r")
        child.sendline("configure vswitch-controller xmpp-server \"{}\""
                       .format(vsd_domain))
        child.sendline("logout")
        child.close()
    except pexpect.ExceptionPexpect as e:
        log("Got an exception: traceback %s" % e.get_trace())
    except Exception as e:
        log("Got a generic exception: %s" % e.strerror)
    else:
        log("Failed to update vsd domain in VSD")
    finally:
        log("Exiting update_vsd_domain")
