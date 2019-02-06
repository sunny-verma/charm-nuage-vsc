#!/usr/bin/python

import os
import sys

from charmhelpers.core.hookenv import (
    config,
    log,
    ERROR,
    Hooks,
    UnregisteredHookError,
    relation_set,
    relation_get,
    relation_ids,
    status_set,
)

from charmhelpers.fetch import (
    apt_update, apt_install,
)
from charmhelpers.fetch.archiveurl import (
    ArchiveUrlFetchHandler
)

from distutils.spawn import (
    find_executable
)
import shutil
from charmhelpers.core.host import (
    mkdir
)


from helper_functions import(
    config_value_changed,
    get_db_value,
    has_db_value,
    set_db_value
)
import virshutils

from scan_ip import get_dns_ip


class ConfigurationError(Exception):
    pass


hooks = Hooks()

vm_ip_address = None
vsd_xmpp_domain = None

charm_vm_config = {}
charm_vm_config['VSP_VM_NAME'] = 'vsc'
charm_vm_config['VSP_VM_IMAGE_NAME'] = 'nuage_vsc.img'


@hooks.hook('install')
def install():
    e = 'Installing nuage-vsc'
    status_set('maintenance', e)
    dependencies = 'ubuntu-virt-server python-vm-builder bridge-utils '\
                   'virtinst python-cheetah python-pexpect python-paramiko'
    apt_update(fatal=True)
    apt_install(dependencies.split(), fatal=True)
    if (find_executable('virsh') is None or
            find_executable('qemu-img') is None):
        log("Missing virtualization binaries - cannot deploy service "
            "{}".format(charm_vm_config['VSP_VM_NAME']))
        e = "Missing virtualization binaries - cannot deploy service {}".\
            format(charm_vm_config['VSP_VM_NAME'])
        status_set('blocked', e)
        raise ConfigurationError(e)
    virshutils.install_guestfs()


@hooks.hook('config-changed')
def config_changed():
    global charm_vm_config

    if not config('vsc-vm-ip-address'):
        e = 'vsc-vm-ip-address is not specified'
        status_set('blocked', e)
        raise ConfigurationError(e)
    if not config('vsc-vm-default-gw'):
        e = 'vsc-vm-default-gw is not specified'
        status_set('blocked', e)
        raise ConfigurationError(e)
    if not config('vsc-vm-dns-server'):
        e = 'vsc-vm-dns-server is not specified'
        status_set('blocked', e)
        raise ConfigurationError(e)

    if not config('vsc-vm-subnet-mask-length'):
        e = 'vsc-vm-subnet-mask is not specified'
        status_set('blocked', e)
        raise ConfigurationError(e)

    if not config('vsc-repository-url'):
        e = 'vsc-repository-url is not specified'
        status_set('blocked', e)
        raise ConfigurationError(e)

    vsc_vm_config_changed = False
    vsc_svc_config_changed = False
    if (config_value_changed('vsc-image-name') or
            config_value_changed('vsc-template-name') or
            config_value_changed('vsc-repository-url') or
            config_value_changed('vsc-vm-disk-size') or
            config_value_changed('vsc-vm-ip-address') or
            config_value_changed('vsc-vm-default-gw') or
            config_value_changed('vsc-vm-dns-server') or
            config_value_changed('vsc-vm-subnet-mask-length') or
            config_value_changed('bridge-name') or
            config_value_changed('vsc-vm-memory')):
        vsc_vm_config_changed = True

    if config_value_changed('admin-user') or\
            config_value_changed('xmpp-cluster-domain-name') or\
            config_value_changed('admin-password'):
        vsc_svc_config_changed = True

    if virshutils.is_vm_running(charm_vm_config) and not\
            vsc_vm_config_changed and not vsc_svc_config_changed:
        return

    if virshutils.is_vm_running(charm_vm_config) and vsc_vm_config_changed:
        stop()

    if virshutils.is_vm_running(charm_vm_config) and vsc_svc_config_changed:
        set_vsd_domain()
        return

    charm_templates_dir = os.path.join(os.environ.get('CHARM_DIR'),
                                       'templates')

    if not os.path.exists(charm_templates_dir):
        mkdir(charm_templates_dir)

    if not config('vsc-vm-disk-size'):
        charm_vm_config['VSP_VM_DISK_SIZE'] = '20G'
    else:
        charm_vm_config['VSP_VM_DISK_SIZE'] = config('vsc-vm-disk-size')

    charm_vm_config['VSP_VM_XML'] = config('vsc-template-name')
    charm_vm_config['VSP_VM_ORIG_IMAGE_NAME'] = config('vsc-image-name')

    source = config('vsc-repository-url')
    if (config_value_changed('vsc-repository-url') or
            (not has_db_value('vsc-repository-fetch-path'))):

        if source is None:
            e = 'vsc-repository-url has invalid value'
            status_set('blocked', e)
            raise ConfigurationError(e)

        handler = ArchiveUrlFetchHandler()
        path = handler.install(source)
        set_db_value('vsc-repository-fetch-path', path)

    path = get_db_value('vsc-repository-fetch-path')
    if path is None:
        e = 'vsc-repository fetch failed: {}'.format(source)
        status_set('blocked', e)
        raise ConfigurationError(e)

    log("path : {}".format(path))

    for root, dirnames, filenames in os.walk(path):
        if config('vsc-image-name') in filenames:
            path_of_vsc_image = os.path.join(root, config('vsc-image-name'))
            path = root
            log("file path vsc-image : {} ".format(path_of_vsc_image))
            log("file path root-folder : {} ".format(root))
            set_db_value('vsc-image-path', path_of_vsc_image)

    if not os.path.exists(get_db_value('vsc-image-path')):
        e = 'vsc-image not found in repository at: {}'.format(source)
        status_set('blocked', e)
        raise ConfigurationError(e)

    for root, dirnames, filenames in os.walk(path):
        if config('vsc-template-name') in filenames:
            path_of_vsc_template = os.path.join(
                root, config('vsc-template-name')
            )
            log("file path vsc-template: {} ".format(path_of_vsc_template))
            log("file path root-folder : {} ".format(root))
            set_db_value('vsc-template-path', path_of_vsc_template)

    if not os.path.exists(get_db_value('vsc-template-path')):
        e = 'vsc-template not found at: {}'.format(source)
        status_set('blocked', e)
        raise ConfigurationError(e)

    for root, dirnames, filenames in os.walk(path):
        if 'bof.cfg' in filenames:
            path_of_bof = os.path.join(root, 'bof.cfg')
            log("file path bof : {} ".format(path_of_bof))
            log("file path root-folder : {} ".format(root))
            set_db_value('vsc-bof-path', path_of_bof)

    from Cheetah.Template import Template
    cheetah_xml_file = Template(
        file=str(get_db_value('vsc-template-path')),
        searchList=[{'vsp_image_name': str(config('vsc-image-name')),
                     'bridge_name': str(config('bridge-name')),
                     'memory': str(config('vsc-vm-memory'))}]
    )

    if cheetah_xml_file is None:
        e = 'Could not define cheetah_xml_file with'\
            ' configurable parameters'
        status_set('blocked', e)
        raise ConfigurationError(e)

    file = open(
        os.path.join(charm_templates_dir, config('vsc-template-name')), 'w+')
    file.truncate()
    file.write(str(cheetah_xml_file))
    file.close()

    if os.path.exists(get_db_value('vsc-bof-path')):
        shutil.move(get_db_value('vsc-bof-path'),
                    os.path.join(charm_templates_dir, 'bof.cfg'))
    else:
        log('vsc-bof configuration is not found at: {}'.
            format(get_db_value('path_of_bof')))
    charm_vm_config['VSP_VM_DIR'] = charm_templates_dir
    charm_vm_config['VSP_VM_IMAGE_DIR'] = path

    if os.path.exists(os.path.join(charm_vm_config['VSP_VM_DIR'], 'bof.cfg')):
        with open(os.path.join(charm_vm_config['VSP_VM_DIR'],
                               'bof.cfg'), "r") as bof:
            contents = bof.read()
            if (config('vsc-vm-ip-address') is not None and
                    config('vsc-vm-subnet-mask-length') is not None):
                contents = contents + "\n" + 'address ' +\
                    config('vsc-vm-ip-address') + '/' + \
                    config('vsc-vm-subnet-mask-length') + ' active'
            else:
                contents = contents + 'ip-address-dhcp' + '\n'
                contents = contents + 'address 169.254.10.1/24 active' + '\n'

            if config('vsc-vm-dns-server') is not None:
                contents = contents + '\n' + 'primary-dns ' + \
                    config('vsc-vm-dns-server') + '\n'
            else:
                contents = contents + "\n" + 'primary-dns ' + \
                    get_dns_ip() + '\n'
            if len(contents) > 0:
                virshutils.write_guestfs(
                    os.path.join(charm_vm_config['VSP_VM_IMAGE_DIR'],
                                 charm_vm_config['VSP_VM_ORIG_IMAGE_NAME']),
                    '/bof.cfg', contents)

    is_vm_created = virshutils.createvm(charm_vm_config)
    if is_vm_created == 0:
        e = 'could not create {} vm'.format(charm_vm_config['VSP_VM_NAME'])
        status_set('blocked', e)
        raise ConfigurationError(e)

    start()


@hooks.hook('vrs-controller-service-relation-joined')
@hooks.hook('vrsg-controller-service-relation-joined')
def vrs_controller_joined(rid=None):
    global vm_ip_address
    if config('vsc-vm-ip-address') is not None:
        vm_ip_address = config('vsc-vm-ip-address')
    else:
        vm_ip_address = virshutils.get_vm_ip_address(charm_vm_config)
    if not vm_ip_address:
        e = "Could not find VSC VM IP address"
        status_set('blocked', e)
        raise ConfigurationError(e)
    settings = {
        'vsc-ip-address': vm_ip_address
    }
    relation_set(relation_id=rid, **settings)


@hooks.hook('vsd-service-relation-changed')
def vsd_changed(relation_id=None, remote_unit=None):
    global vsd_xmpp_domain
    vsd_ip_address = relation_get('vsd-ip-address')
    if not vsd_ip_address:
        log('VSD IP Address is none')
        return

    log('VSD IP Address is not none')
    # vsd domain name
    vsd_xmpp_domain = virshutils.get_domain_name(vsd_ip_address)
    if vsd_xmpp_domain is not None and\
            virshutils.is_vm_running(charm_vm_config):
        set_vsd_domain()


def set_vsd_domain():
    global vm_ip_address, vsd_xmpp_domain
    if config('vsc-vm-ip-address') is not None:
        vm_ip_address = config('vsc-vm-ip-address')
    else:
        vm_ip_address = virshutils.get_vm_ip_address(charm_vm_config)
    if not vm_ip_address:
        e = "FATAL ERROR: Could not find VSC VM IP address"
        status_set('blocked', e)
        raise ConfigurationError(e)

    if config('xmpp-cluster-domain-name') is not None:
        log('VSD xmpp domain name will be set from config to '
            '{}'.format(config('xmpp-cluster-domain-name')))
        virshutils.update_vsd_domain(vm_ip_address, config('admin-user'),
                                     config('admin-password'),
                                     config('xmpp-cluster-domain-name'))
        e = 'vsd xmpp domain: {}'.format(config('xmpp-cluster-domain-name'))
        status_set('active', e)
    elif vsd_xmpp_domain is not None:
        log('VSD xmpp domain name will be set from relation hook to '
            '{}'.format(vsd_xmpp_domain))
        virshutils.update_vsd_domain(vm_ip_address, config('admin-user'),
                                     config('admin-password'), vsd_xmpp_domain)
        e = 'vsd xmpp domain: {}'.format(vsd_xmpp_domain)
        status_set('active', e)


@hooks.hook('upgrade-charm')
def upgrade_charm():
    log('Upgrading {}'.format(charm_vm_config['VSP_VM_NAME']))


@hooks.hook('start')
def start():
    global vm_ip_address
    virshutils.startvm(charm_vm_config)
    if config('vsc-vm-ip-address') is not None:
        vm_ip_address = config('vsc-vm-ip-address')
    else:
        vm_ip_address = virshutils.get_vm_ip_address(charm_vm_config)
    if not vm_ip_address:
        e = "FATAL ERROR: Could not find VSC VM IP address"
        status_set('blocked', e)
        raise ConfigurationError(e)

    virshutils.wait_for_vm_to_be_pingable(vm_ip_address)
    log('Firing identity_changed hook for all related services.')
    # HTTPS may have been set - so fire all identity relations
    # again
    settings = {
        'vsc-ip-address': vm_ip_address
    }
    for r_id in relation_ids('vrs-controller-service'):
        relation_set(relation_id=r_id, **settings)

    set_vsd_domain()


@hooks.hook('stop')
def stop():
    virshutils.stopvm(charm_vm_config)
    log("{} is successfully shutdown ".format(charm_vm_config['VSP_VM_NAME']))


if __name__ == "__main__":
    # execute a hook based on the name the program is called by
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {}, skipping'.format(e))
    except ConfigurationError as ce:
        log('Configuration error: {}'.format(ce), level=ERROR)
        sys.exit(1)
