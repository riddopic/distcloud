#
# Copyright (c) 2020 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import mock

from dcmanager.common.consts import DEPLOY_STATE_DONE
from dcmanager.common.consts import STRATEGY_STATE_COMPLETE
from dcmanager.common.consts import STRATEGY_STATE_FAILED
from dcmanager.common.consts \
    import STRATEGY_STATE_KUBE_CREATING_VIM_KUBE_UPGRADE_STRATEGY
from dcmanager.common.consts import STRATEGY_STATE_KUBE_UPGRADE_PRE_CHECK
from dcmanager.db.sqlalchemy import api as db_api

from dcmanager.tests.unit.common import fake_strategy
from dcmanager.tests.unit.orchestrator.states.fakes import FakeKubeUpgrade
from dcmanager.tests.unit.orchestrator.states.fakes import FakeKubeVersion
from dcmanager.tests.unit.orchestrator.states.fakes \
    import PREVIOUS_KUBE_VERSION
from dcmanager.tests.unit.orchestrator.states.fakes \
    import UPGRADED_KUBE_VERSION
from dcmanager.tests.unit.orchestrator.states.kube.test_base \
    import TestKubeUpgradeState


class TestKubeUpgradePreCheckStage(TestKubeUpgradeState):

    def setUp(self):
        super(TestKubeUpgradePreCheckStage, self).setUp()

        # Add the subcloud being processed by this unit test
        # The subcloud is online, managed with deploy_state 'installed'
        self.subcloud = self.setup_subcloud()

        # Add the strategy_step state being processed by this unit test
        self.strategy_step = \
            self.setup_strategy_step(STRATEGY_STATE_KUBE_UPGRADE_PRE_CHECK)

        # mock there not being a kube upgrade in progress
        self.sysinv_client.get_kube_upgrades = mock.MagicMock()
        self.sysinv_client.get_kube_upgrades.return_value = []

        # mock the get_kube_versions calls
        self.sysinv_client.get_kube_versions = mock.MagicMock()
        self.sysinv_client.get_kube_versions.return_value = []

    def test_pre_check_subcloud_existing_upgrade(self):
        """Test pre check step where the subcloud has a kube upgrade

        When a kube upgrade exists in the subcloud, do not skip, go to the
        next step, which is 'create the vim kube upgrade strategy'
        """
        next_state = STRATEGY_STATE_KUBE_CREATING_VIM_KUBE_UPGRADE_STRATEGY
        # Update the subcloud to have deploy state as "complete"
        db_api.subcloud_update(self.ctx,
                               self.subcloud.id,
                               deploy_status=DEPLOY_STATE_DONE)
        self.sysinv_client.get_kube_upgrades.return_value = [FakeKubeUpgrade()]
        # get kube versions invoked only for the system controller
        self.sysinv_client.get_kube_versions.return_value = [
            FakeKubeVersion(obj_id=1,
                            version=UPGRADED_KUBE_VERSION,
                            target=True,
                            state='active'),
        ]

        # invoke the strategy state operation on the orch thread
        self.worker.perform_state_action(self.strategy_step)

        # Verify the single query (for the system controller)
        self.sysinv_client.get_kube_versions.assert_called_once()

        # Verify the transition to the  expected next state
        self.assert_step_updated(self.strategy_step.subcloud_id, next_state)

    def test_pre_check_no_sys_controller_active_version(self):
        """Test pre check step where system controller has no active version

        The subcloud has no existing kube upgrade.
        There is no 'to-version' indicated in extra args.
        The target version is derived from the system controller.  Inability
        to query that version should fail orchestration.
        """
        next_state = STRATEGY_STATE_FAILED
        # Update the subcloud to have deploy state as "complete"
        db_api.subcloud_update(self.ctx,
                               self.subcloud.id,
                               deploy_status=DEPLOY_STATE_DONE)

        # No extra args / to-version in the database
        # Query system controller kube versions
        # override the first get, so that there is no active release
        # 'partial' indicates the system controller is still upgrading
        self.sysinv_client.get_kube_versions.return_value = [
            FakeKubeVersion(obj_id=1,
                            version=PREVIOUS_KUBE_VERSION,
                            target=True,
                            state='partial'),
            FakeKubeVersion(obj_id=2,
                            version=UPGRADED_KUBE_VERSION,
                            target=False,
                            state='unavailable'),
        ]
        # invoke the strategy state operation on the orch thread
        self.worker.perform_state_action(self.strategy_step)

        # Verify the expected next state happened
        self.assert_step_updated(self.strategy_step.subcloud_id, next_state)

    def test_pre_check_no_subcloud_available_version(self):
        """Test pre check step where subcloud has no available version

        This test simulates a fully upgraded system controller and subcloud.
        In practice, the audit should not have added this subcloud to orch.

        Setup:
        - The subcloud has no existing kube upgrade.
        - There is no 'to-version' indicated in extra args.
        - System Controller has an 'active' version
        - Subcloud has no 'available' version.
        Expectation:
        - Skip orchestration,  jump to 'complete' for this state.
        """
        # Update the subcloud to have deploy state as "complete"
        db_api.subcloud_update(self.ctx,
                               self.subcloud.id,
                               deploy_status=DEPLOY_STATE_DONE)

        # No extra args / to-version in the database
        # Query system controller kube versions
        self.sysinv_client.get_kube_versions.side_effect = [
            [   # first list: (system controller) has an active release
                FakeKubeVersion(obj_id=1,
                                version=PREVIOUS_KUBE_VERSION,
                                target=False,
                                state='unavailable'),
                FakeKubeVersion(obj_id=2,
                                version=UPGRADED_KUBE_VERSION,
                                target=True,
                                state='active'),
            ],
            [   # second list: (subcloud) fully upgraded (no available release)
                FakeKubeVersion(obj_id=1,
                                version=PREVIOUS_KUBE_VERSION,
                                target=False,
                                state='unavailable'),
                FakeKubeVersion(obj_id=2,
                                version=UPGRADED_KUBE_VERSION,
                                target=True,
                                state='active'),
            ],
        ]
        # fully upgraded subcloud.  Next state will be complete.
        next_state = STRATEGY_STATE_COMPLETE

        # invoke the strategy state operation on the orch thread
        self.worker.perform_state_action(self.strategy_step)

        # get_kube_versions gets called (more than once)
        self.sysinv_client.get_kube_versions.assert_called()

        # Verify the expected next state happened
        self.assert_step_updated(self.strategy_step.subcloud_id, next_state)

    def test_pre_check_subcloud_existing_upgrade_resumable(self):
        """Test pre check step where the subcloud has lower kube upgrade

        When a kube upgrade exists in the subcloud, it is skipped if to-version
        if less than its version.  This test should not skip the subcloud.
        """
        next_state = STRATEGY_STATE_KUBE_CREATING_VIM_KUBE_UPGRADE_STRATEGY
        # Update the subcloud to have deploy state as "complete"
        db_api.subcloud_update(self.ctx,
                               self.subcloud.id,
                               deploy_status=DEPLOY_STATE_DONE)

        low_version = "v1.2.3"
        high_partial_version = "v1.3"

        self.sysinv_client.get_kube_upgrades.return_value = [
            FakeKubeUpgrade(to_version=low_version)
        ]

        # The orchestrated version target is higher than the version of the
        # existing upgrade in the subcloud, so the subcloud upgrade should
        # continue
        extra_args = {"to-version": high_partial_version}
        self.strategy = fake_strategy.create_fake_strategy(
            self.ctx,
            self.DEFAULT_STRATEGY_TYPE,
            extra_args=extra_args)

        # invoke the strategy state operation on the orch thread
        self.worker.perform_state_action(self.strategy_step)

        # Do not need to mock query kube versions since extra args will be
        # queried to get the info for the system controller
        # and pre-existing upgrade is used for subcloud
        self.sysinv_client.get_kube_versions.assert_not_called()

        # Verify the transition to the  expected next state
        self.assert_step_updated(self.strategy_step.subcloud_id, next_state)

    def _test_pre_check_subcloud_existing_upgrade_skip(self,
                                                       target_version,
                                                       subcloud_version):
        """Test pre check step where the subcloud existing upgrade too high.

        When a kube upgrade exists in the subcloud, it is skipped if to-version
        is less than the version of the existing upgrade.
        For this test, the subcloud version is higher than the target, so
        it should not be resumed and the skip should occur.
        """
        next_state = STRATEGY_STATE_COMPLETE
        # Update the subcloud to have deploy state as "complete"
        db_api.subcloud_update(self.ctx,
                               self.subcloud.id,
                               deploy_status=DEPLOY_STATE_DONE)

        self.sysinv_client.get_kube_upgrades.return_value = [
            FakeKubeUpgrade(to_version=subcloud_version)
        ]

        extra_args = {"to-version": target_version}
        self.strategy = fake_strategy.create_fake_strategy(
            self.ctx,
            self.DEFAULT_STRATEGY_TYPE,
            extra_args=extra_args)

        # invoke the strategy state operation on the orch thread
        self.worker.perform_state_action(self.strategy_step)

        # Do not need to mock query kube versions since extra args will be
        # queried to get the info for the system controller
        # and pre-existing upgrade is used for subcloud
        self.sysinv_client.get_kube_versions.assert_not_called()

        # Verify the transition to the  expected next state
        self.assert_step_updated(self.strategy_step.subcloud_id, next_state)

    def test_pre_check_subcloud_existing_upgrade_too_high(self):
        target_version = "v1.2.1"
        subcloud_version = "v1.3.3"
        self._test_pre_check_subcloud_existing_upgrade_skip(target_version,
                                                            subcloud_version)

    def test_pre_check_subcloud_existing_upgrade_too_high_target_partial(self):
        target_version = "v1.2"
        subcloud_version = "v1.3.3"
        self._test_pre_check_subcloud_existing_upgrade_skip(target_version,
                                                            subcloud_version)

    def test_pre_check_subcloud_existing_upgrade_too_high_subcl_partial(self):
        target_version = "v1.2.1"
        subcloud_version = "v1.3"
        self._test_pre_check_subcloud_existing_upgrade_skip(target_version,
                                                            subcloud_version)

    def _test_pre_check_subcloud_existing_upgrade_resume(self,
                                                         target_version,
                                                         subcloud_version):
        """Test pre check step where target version >= existing upgrade

        When a kube upgrade exists in the subcloud, it is resumed if to-version
        is the same or higher.  The to-version can be a partial version.
        Test supports partial values for target_version and subcloud_version
        """
        next_state = STRATEGY_STATE_KUBE_CREATING_VIM_KUBE_UPGRADE_STRATEGY
        # Update the subcloud to have deploy state as "complete"
        db_api.subcloud_update(self.ctx,
                               self.subcloud.id,
                               deploy_status=DEPLOY_STATE_DONE)

        # Setup a fake kube upgrade in progress
        self.sysinv_client.get_kube_upgrades.return_value = [
            FakeKubeUpgrade(to_version=subcloud_version)
        ]

        # Setup a fake kube upgrade strategy with the to-version specified
        extra_args = {"to-version": target_version}
        self.strategy = fake_strategy.create_fake_strategy(
            self.ctx,
            self.DEFAULT_STRATEGY_TYPE,
            extra_args=extra_args)

        # invoke the strategy state operation on the orch thread
        self.worker.perform_state_action(self.strategy_step)

        # Do not need to mock query kube versions since extra args will be
        # queried to get the info for the system controller
        # and pre-existing upgrade is used for subcloud
        self.sysinv_client.get_kube_versions.assert_not_called()

        # Verify the transition to the  expected next state
        self.assert_step_updated(self.strategy_step.subcloud_id, next_state)

    def test_pre_check_subcloud_existing_upgrade_match(self):
        target_version = "v1.2.3"
        subcloud_version = "v1.2.3"
        self._test_pre_check_subcloud_existing_upgrade_resume(target_version,
                                                              subcloud_version)

    def test_pre_check_subcloud_existing_upgrade_match_target_partial(self):
        # v1.2 is considered the same as v1.2.3 (micro version gets ignored)
        target_version = "v1.2"
        subcloud_version = "v1.2.3"
        self._test_pre_check_subcloud_existing_upgrade_resume(target_version,
                                                              subcloud_version)

    def test_pre_check_subcloud_existing_upgrade_match_subcloud_partial(self):
        # v1.2 is considered the same as v1.2.3 (micro version gets ignored)
        target_version = "v1.2.3"
        subcloud_version = "v1.2"
        self._test_pre_check_subcloud_existing_upgrade_resume(target_version,
                                                              subcloud_version)
