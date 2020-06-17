#
# Copyright (c) 2020 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import mock
import uuid

from dcmanager.common import consts
from dcmanager.manager.states.base import BaseState
from oslo_utils import timeutils

from dcmanager.tests.unit.manager.test_sw_upgrade import TestSwUpgrade

PREVIOUS_VERSION = '12.34'
UPGRADED_VERSION = '56.78'


class FakeKeystoneClient(object):
    def __init__(self):
        self.session = mock.MagicMock()


class FakeLoad(object):
    def __init__(self,
                 obj_id,
                 compatible_version='N/A',
                 required_patches='N/A',
                 software_version=PREVIOUS_VERSION,
                 state='active',
                 created_at=None,
                 updated_at=None):
        self.id = obj_id
        self.uuid = uuid.uuid4()
        self.compatible_version = compatible_version
        self.required_patches = required_patches
        self.software_version = software_version
        self.state = state
        self.created_at = created_at
        self.updated_at = updated_at


class FakeSystem(object):
    def __init__(self,
                 obj_id=1,
                 software_version=UPGRADED_VERSION):
        self.id = obj_id
        self.uuid = uuid.uuid4()
        self.software_version = software_version


class FakeUpgrade(object):
    def __init__(self,
                 obj_id=1,
                 state='completed',
                 from_release=PREVIOUS_VERSION,
                 to_release=UPGRADED_VERSION):
        self.id = obj_id
        self.uuid = uuid.uuid4()
        self.state = state
        self.from_release = from_release
        self.to_release = to_release
        self.links = []


class FakeSysinvClient(object):
    def __init__(self):
        pass


class FakeController(object):
    def __init__(self,
                 host_id=1,
                 hostname='controller-0',
                 administrative=consts.ADMIN_UNLOCKED,
                 operational=consts.OPERATIONAL_ENABLED,
                 availability=consts.AVAILABILITY_ONLINE,
                 ihost_action=None,
                 target_load=UPGRADED_VERSION,
                 task=None):
        self.id = host_id
        self.hostname = hostname
        self.administrative = administrative
        self.operational = operational
        self.availability = availability
        self.ihost_action = ihost_action
        self.target_load = target_load
        self.task = task


class FakeSubcloud(object):
    def __init__(self,
                 subcloud_id=1,
                 name='subcloud1',
                 description='subcloud',
                 location='A location',
                 software_version='12.34',
                 management_state=consts.MANAGEMENT_MANAGED,
                 availability_status=consts.AVAILABILITY_ONLINE,
                 deploy_status=consts.DEPLOY_STATE_DONE):
        self.id = subcloud_id
        self.name = name
        self.description = description
        self.location = location
        self.software_version = software_version
        self.management_state = management_state
        self.availability_status = availability_status
        self.deploy_status = deploy_status
        # todo(abailey): add these and re-factor other unit tests to use
        # self.management_subnet = management_subnet
        # self.management_gateway_ip = management_gateway_ip
        # self.management_start_ip = management_start_ip
        # self.management_end_ip = management_end_ip
        # self.external_oam_subnet = external_oam_subnet
        # self.external_oam_gateway_address = external_oam_gateway_address
        # self.external_oam_floating_address = external_oam_floating_address
        # self.systemcontroller_gateway_ip = systemcontroller_gateway_ip
        self.created_at = timeutils.utcnow()
        self.updated_at = timeutils.utcnow()


class TestSwUpgradeState(TestSwUpgrade):
    def setUp(self):
        super(TestSwUpgradeState, self).setUp()

        # Mock the host environment.
        self.controller_0 = self.fake_controller('controller-0')

        # Mock the keystone client defined in the base upgrade state class
        self.keystone_client = FakeKeystoneClient()
        p = mock.patch.object(BaseState, 'get_keystone_client')
        self.mock_keystone_client = p.start()
        self.mock_keystone_client.return_value = self.keystone_client
        self.addCleanup(p.stop)

        # Mock the sysinv client defined in the base upgrade state class
        self.sysinv_client = FakeSysinvClient()
        p = mock.patch.object(BaseState, 'get_sysinv_client')
        self.mock_sysinv_client = p.start()
        self.mock_sysinv_client.return_value = self.sysinv_client
        self.addCleanup(p.stop)

    def fake_controller(self, hostname):
        return FakeController(hostname=hostname)
