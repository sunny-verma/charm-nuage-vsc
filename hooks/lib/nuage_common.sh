#!/bin/bash

LOG_TERMINAL=0

function logger
{
    if [ $LOG_TERMINAL -eq 1 ]; then
        echo $1
    else
        juju-log $1
    fi
}


function check_env
{
    logger "VSP_VM_NAME: ${VSP_VM_NAME}"
    logger "VSP_VM_DIR: ${VSP_VM_DIR}"
    logger "VSP_VM_XML: ${VSP_VM_XML}"
    logger "VSP_VM_IMAGE_NAME: ${VSP_VM_IMAGE_NAME}"
    logger "VSP_VM_ORIG_IMAGE_NAME: ${VSP_VM_ORIG_IMAGE_NAME}"
    logger "VSP_VM_IMAGE_DIR: ${VSP_VM_IMAGE_DIR}"
    logger "VSP_VM_MAC_ADDR: ${VSP_VM_MAC_ADDR}"
}

# Returns 0 if VSP is not running
function is_vsp_vm_running
{
    local run=$(sudo virsh list --all | grep ${VSP_VM_NAME} | awk '{print $NF}')
    if [ "$run" == "running" ]; then
        return 1
    else
        return 0
    fi
}

# Returns 0 if VSP VM is not created
function is_vsp_vm_created
{
    if [ `/usr/bin/virsh list --all | grep -c ${VSP_VM_NAME}` -eq 1 ]; then
        return 1
    else
        return 0
    fi
}

function create_vsp_qemu_img
{
    logger "Check and create the qemu-img"

    is_vsp_vm_running
    if [ $? -eq 0 ]; then
        set -e
        /usr/bin/qemu-img create -f qcow2 -b ${VSP_VM_IMAGE_DIR}/${VSP_VM_ORIG_IMAGE_NAME} ${VSP_VM_IMAGE_DIR}/${VSP_VM_IMAGE_NAME}
        sudo /usr/bin/qemu-img resize ${VSP_VM_IMAGE_DIR}/${VSP_VM_IMAGE_NAME} ${VSP_VM_DISK_SIZE}

        sudo cp ${VSP_VM_IMAGE_DIR}/${VSP_VM_ORIG_IMAGE_NAME} /var/lib/libvirt/images/${VSP_VM_ORIG_IMAGE_NAME}
        sudo mv ${VSP_VM_IMAGE_DIR}/${VSP_VM_IMAGE_NAME} /var/lib/libvirt/images/${VSP_VM_IMAGE_NAME}

        set +e
        logger "qemu-img create done"
    fi
}

# It creates a persistent VSP VM if it was not created already
# Returns 1 if it was not able to create it
function create_vsp_vm
{
    logger "Check if ${VSP_VM_NAME} vm already exists"

    if [ `/usr/bin/virsh list --all | grep -c ${VSP_VM_NAME}` -eq 1 ]; then
        logger "vsp vm is already created"
        return
    fi

    create_vsp_qemu_img

    logger "Define vsp vm"
    if [ ! -f ${VSP_VM_DIR}/${VSP_VM_XML} ]; then
        logger "Error: ${VSP_VM_NAME} template does not exist"
        exit 1
    fi
    /usr/bin/virsh define ${VSP_VM_DIR}/${VSP_VM_XML}
    if [ "`sudo virsh list --all | awk '/shut off/{print $2}'`" != "${VSP_VM_NAME}" ]; then
        logger "start: unable to define vsp vm"
        exit 1
    fi
}

function start_vsp_vm
{
    logger "Get vsp vm state"
    state="`sudo virsh dominfo ${VSP_VM_NAME} | awk '/State:/' | cut -d: -f 2 | tr -d ' '`"
    case $state in
        running)   logger "vsp ${VSP_VM_NAME} is already runnning"
                   ;;
        shut*)     logger "need to start vsp ${VSP_VM_NAME}"
                   /usr/bin/virsh start ${VSP_VM_NAME}
                   if [ $? -eq 1 ]; then
                       logger "Error: vsp vm is shutdown but couldn't restart it"
                       exit 1
                   fi
                   ;;
        *)         logger "Unknown state($state) of vsp ${VSP_VM_NAME}"
                   ;;
    esac
}

function stop_vsp_vm
{
    is_vsp_vm_running
    if [ $? -eq 1 ]; then
        logger "Shutting down vsp vm"
        virsh shutdown ${VSP_VM_NAME}
        sleep 5
    fi

    is_vsp_vm_running
    if [ $? -eq 1 ]; then
        logger "Destroying vsp vm"
        /usr/bin/virsh destroy ${VSP_VM_NAME}
    fi
    /usr/bin/virsh undefine ${VSP_VM_NAME}
}

function get_vsp_vm_ip_address
{
    vsp_vm_mac=$(virsh domiflist ${VSP_VM_NAME} |grep br0|grep -o -E "([0-9a-f]{2}:){5}([0-9a-f]{2})")
    vsp_vm_ip=$(arp -a | grep $vsp_vm_mac | cut -d " " -f2 | sed 's/[(),]//g')
    echo $vsp_vm_ip
}

export -f logger is_vsp_vm_running is_vsp_vm_created create_vsp_qemu_img create_vsp_vm start_vsp_vm stop_vsp_vm get_vsp_vm_ip_address
