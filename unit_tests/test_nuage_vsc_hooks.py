from mock import patch, call
import os
from test_utils import (
    CharmTestCase,
)

import hooks as hooks

with patch('charmhelpers.core.hookenv.config') as config:
    config.return_value = 'nuage-vsc'


hooks.hooks._config_save = False

TO_PATCH = [
    'relation_set',
    'os',
    'stop',
    'set_vsd_domain',
    'config',
    'apt_update',
    'apt_install',
    'find_executable',
    'relation_get',
    'relation_ids',
    'status_set',
    'config_value_changed',
    'get_db_value',
    'has_db_value',
    'set_db_value',
    'virshutils',
    'ArchiveUrlFetchHandler',
]

nuage_vsc_config_changed = {
    'vsc-image-name': False,
    'vsc-template-name': False,
    'vsc-repository-url': False,
    'vsc-vm-disk-size': False,
    'xmpp-cluster-domain-name': False,
    'admin-user': False,
    'admin-password': False,
    'vsc-vm-ip-address': False,
    'vsc-vm-default-gw': False,
    'vsc-vm-dns-server': False,
    'vsc-vm-subnet-mask-length': False,
    'bridge-name': False,
    'vsc-vm-memory': False
}
charm_vm_config = {}
charm_vm_config['VSP_VM_NAME'] = 'vsc'
charm_vm_config['VSP_VM_IMAGE_NAME'] = 'nuage_vsc.img'


def _mock_config_value_changed(option):
    return nuage_vsc_config_changed[option]


class TestNuageVSC(CharmTestCase):
    def _call_hook(self, hookname):
        hooks.hooks.execute([
            'hooks/{}'.format(hookname)])

    def setUp(self):
        super(TestNuageVSC, self).setUp(hooks, TO_PATCH)
        self.config_value_changed.side_effect = _mock_config_value_changed
        self.config.side_effect = self.test_config.get
        self.relation_get.side_effect = self.test_relation.get

    def test_install_nuage_vsc(self):
        _pkgs = ['ubuntu-virt-server', 'python-vm-builder', 'bridge-utils','virtinst', 'python-cheetah', 'python-pexpect', 'python-paramiko']

        self._call_hook('install')
        self.apt_update.assert_called_with(fatal=True)
        self.apt_install.assert_has_calls([
            call(_pkgs, fatal=True),
        ])
        self.find_executable.assert_any_call('virsh')
        self.find_executable.assert_any_call('qemu-img')
        self.virshutils.install_guestfs.assert_called_with()

    def test_config_changed(self):
        with self.assertRaises(Exception) as context:
            self._call_hook('config_changed')
        self.assertEqual(context.exception.message,
            'vsc-vm-ip-address is not specified')
        vsc_vm_ip = '1.2.3.4'
        self.test_config.set('vsc-vm-ip-address',vsc_vm_ip)

        with self.assertRaises(Exception) as context:
            self._call_hook('config_changed')
        self.assertEqual(context.exception.message,
                            'vsc-vm-default-gw is not specified')
        vsc_vm_gw = '1.2.3.1'
        self.test_config.set('vsc-vm-default-gw', vsc_vm_gw)


        with self.assertRaises(Exception) as context:
            self._call_hook('config_changed')
        self.assertEqual(context.exception.message,
                            'vsc-vm-dns-server is not specified')
        vsc_vm_dns = '8.8.8.8'
        self.test_config.set('vsc-vm-dns-server',vsc_vm_dns)


        with self.assertRaises(Exception) as context:
            self._call_hook('config_changed')
        self.assertEqual(context.exception.message,
                            'vsc-vm-subnet-mask is not specified')
        vsc_vm_subnet= '255.255.255.0'
        self.test_config.set('vsc-vm-subnet-mask-length',vsc_vm_subnet)

     
        with self.assertRaises(Exception) as context:
            self._call_hook('config_changed')
        self.assertEqual(context.exception.message,
                            'vsc-repository-url is not specified')
        vsc_repo_url = "http://vsc_url"
        self.test_config.set('vsc-repository-url',vsc_repo_url)
         
        self._call_hook('config_changed')
        self.virshutils.is_vm_running.assert_called_with(charm_vm_config)
        ret = self.virshutils.is_vm_running.return_value
        self.assertTrue(ret)

        self.assertFalse(self.set_vsd_domain.called)
        self.assertFalse(self.stop.called)
        nuage_vsc_config_changed['vsc-image-name'] = True
        nuage_vsc_config_changed['admin-user'] = True

        self._call_hook('config_changed')

        self.assertTrue(self.set_vsd_domain.called)
        self.assertTrue(self.stop.called)
        self.assertTrue(self.virshutils.stopvm(charm_vm_config))

        nuage_vsc_config_changed['vsc-image-name'] = True
        nuage_vsc_config_changed['admin-user'] = False
        self.assertTrue(self.stop.called)


        os.environ['CHARM_DIR'] = os.getcwd()

        '''
        charm_vm_config['VSP_VM_DISK_SIZE']= '20G'
        charm_vm_config['VSP_VM_ORIG_IMAGE_NAME'] =  'vsc_singledisk.qcow2'
        charm_vm_config['VSP_VM_XML']= 'vsc.xml'
        template_path =  os.environ['CHARM_DIR']+'/templates/vsc.xml'
        '''
        #self._call_hook('config_changed')
        #self.assertTrue(self.set_db_value.called)
        #self.assertTrue(self.get_db_value.called)

        

    def test_vrs_controller_joined(self):
        #self.test_config.set('vsc-vm-ip-address',None)
        #self._call_hook('vrs-controller-service-relation-joined')
        #self.virshutils.get_vm_ip_addres.assert_called_with(charm_vm_config)
        
        self.test_config.set('vsc-vm-ip-address','1.1.1.1')
        self._call_hook('vrsg-controller-service-relation-joined')
        vm_ip = self.test_config.get('vsc-vm-ip-address')
        settings = {
            'vsc-ip-address': vm_ip
        }
        self.relation_set.assert_called_with(relation_id=None,**settings)


    def test_vsd_service(self):
        self._call_hook('vsd-service-relation-changed')
        self.assertTrue(self.relation_get.called)
        self.assertFalse(self.virshutils.get_domain_name.called)


        self.test_relation.set({'vsd-ip-address':'1.1.1.1'})
        self._call_hook('vsd-service-relation-changed')
        vsd_ip_address = self.test_relation.get('vsd-ip-address')
        self.relation_get.assert_called_with('vsd-ip-address')
        self.assertTrue(self.virshutils.get_domain_name.called)
        self.virshutils.get_domain_name.assert_called_with(vsd_ip_address)
        self.assertTrue(self.set_vsd_domain.called)

    def test_start_hook(self):
        self.test_config.set('vsc-vm-ip-address','1.1.1.1')
        self._call_hook('start')
        self.assertTrue(self.virshutils.startvm.called)
        self.virshutils.startvm.assert_called_with(charm_vm_config)
        vm_ip = self.test_config.get('vsc-vm-ip-address')

        self.virshutils.wait_for_vm_to_be_pingable.assert_called_with(vm_ip)
        self.assertTrue(self.set_vsd_domain.called)
    
    def test_stop_hook(self):
        self._call_hook('stop')
        self.virshutils.stopvm.assert_called_with(charm_vm_config)
