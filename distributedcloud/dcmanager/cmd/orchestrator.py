#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# Copyright (c) 2020 Wind River Systems, Inc.
#
# The right to copy, distribute, modify, or otherwise make use
# of this software may be licensed only pursuant to the terms
# of an applicable Wind River license agreement.
#

"""
DC Manager Orchestrator Service.
"""

import eventlet
eventlet.monkey_patch()

from oslo_config import cfg
from oslo_i18n import _lazy
from oslo_log import log as logging
from oslo_service import service

from dcmanager.common import config
from dcmanager.common import messaging


CONF = cfg.CONF
LOG = logging.getLogger('dcmanager.orchestrator')


def main():
    _lazy.enable_lazy()
    config.register_options()
    config.register_keystone_options()
    logging.register_options(CONF)
    CONF(project='dcmanager', prog='dcmanager-orchestrator')
    logging.setup(CONF, 'dcmanager-orchestrator')
    logging.set_defaults()
    messaging.setup()

    from dcmanager.orchestrator import service as orchestrator

    srv = orchestrator.DCManagerOrchestratorService()
    launcher = service.launch(CONF,
                              srv, workers=cfg.CONF.orch_workers)

    LOG.info("Configuration:")
    CONF.log_opt_values(LOG, logging.INFO)

    launcher.wait()

if __name__ == '__main__':
    main()
