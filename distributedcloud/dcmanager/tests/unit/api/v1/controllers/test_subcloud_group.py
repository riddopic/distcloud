# Copyright (c) 2017 Ericsson AB
# All Rights Reserved.
#
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

import mock
from six.moves import http_client

from dcmanager.common import consts
from dcmanager.db.sqlalchemy import api as db_api
from dcmanager.rpc import client as rpc_client

from dcmanager.tests.unit.api import test_root_controller as testroot
from dcmanager.tests.unit.api.v1.controllers.test_subclouds \
    import FAKE_SUBCLOUD_DATA
from dcmanager.tests import utils

SAMPLE_SUBCLOUD_GROUP_NAME = 'GroupX'
SAMPLE_SUBCLOUD_GROUP_DESCRIPTION = 'A Group of mystery'
SAMPLE_SUBCLOUD_GROUP_UPDATE_APPLY_TYPE = consts.SUBCLOUD_APPLY_TYPE_SERIAL
SAMPLE_SUBCLOUD_GROUP_MAX_PARALLEL_SUBCLOUDS = 3


# APIMixin can be moved to its own file, once the other
# unit tests are refactored to utilize it
class APIMixin(object):

    FAKE_TENANT = utils.UUID1

    api_headers = {
        'X-Tenant-Id': FAKE_TENANT,
        'X_ROLE': 'admin',
        'X-Identity-Status': 'Confirmed'
    }

    # subclasses should provide methods
    # get_api_prefix
    # get_result_key

    def setUp(self):
        super(APIMixin, self).setUp()

    def get_api_headers(self):
        return self.api_headers

    def get_single_url(self, uuid):
        return '%s/%s' % (self.get_api_prefix(), uuid)

    def get_api_prefix(self):
        raise NotImplementedError

    def get_result_key(self):
        raise NotImplementedError

    def get_expected_api_fields(self):
        raise NotImplementedError

    def get_omitted_api_fields(self):
        raise NotImplementedError

    # base mixin subclass MUST override these methods if the api supports them
    def _create_db_object(self, context):
        raise NotImplementedError

    # base mixin subclass should provide this method for testing of POST
    def get_post_object(self):
        raise NotImplementedError

    def get_update_object(self):
        raise NotImplementedError

    def assert_fields(self, api_object):
        # Verify that expected attributes are returned
        for field in self.get_expected_api_fields():
            self.assertIn(field, api_object)

        # Verify that hidden attributes are not returned
        for field in self.get_omitted_api_fields():
            self.assertNotIn(field, api_object)


#
# --------------------- POST -----------------------------------
#
# An API test will mixin only one of: PostMixin or PostRejectedMixin
# depending on whether or not the API supports a post operation or not
class PostMixin(object):

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_create_success(self, mock_client):
        # Test that a POST operation is supported by the API
        ndict = self.get_post_object()
        response = self.app.post_json(self.get_api_prefix(),
                                      ndict,
                                      headers=self.get_api_headers())
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status_code, http_client.OK)
        self.assert_fields(response.json)


class PostRejectedMixin(object):
    # Test that a POST operation is blocked by the API
    # API should return 400 BAD_REQUEST or FORBIDDEN 403
    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_create_not_allowed(self, mock_client):
        ndict = self.get_post_object()
        response = self.app.post_json(self.API_PREFIX,
                                      ndict,
                                      headers=self.get_api_headers(),
                                      expect_errors=True)
        self.assertEqual(response.status_code, http_client.FORBIDDEN)
        self.assertTrue(response.json['error_message'])
        self.assertIn("Operation not permitted.",
                      response.json['error_message'])


# ------  API GET mixin
class GetMixin(object):

    # Mixins can override initial_list_size if a table is not empty during
    # DB creation and migration sync
    initial_list_size = 0

    # Performing a GET on this ID should fail.  subclass mixins can override
    invalid_id = '123'

    def validate_entry(self, result_item):
        self.assert_fields(result_item)

    def validate_list(self, expected_length, results):
        self.assertIn(self.get_result_key(), results)
        result_list = results.get(self.get_result_key())
        self.assertEqual(expected_length, len(result_list))
        for result_item in result_list:
            self.validate_entry(result_item)

    def validate_list_response(self, expected_length, response):
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status_code, http_client.OK)

        # validate the list length
        self.validate_list(expected_length, response.json)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_initial_list_size(self, mock_client):
        # Test that a GET operation for a list is supported by the API
        response = self.app.get(self.get_api_prefix(),
                                headers=self.get_api_headers())
        # Validate the initial length
        self.validate_list_response(self.initial_list_size, response)

        # Add an entry
        context = utils.dummy_context()
        self._create_db_object(context)

        response = self.app.get(self.get_api_prefix(),
                                headers=self.get_api_headers())
        self.validate_list_response(self.initial_list_size + 1, response)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_fail_get_single(self, mock_client):
        # Test that a GET operation for an invalid ID returns the
        # appropriate error results
        response = self.app.get(self.get_single_url(self.invalid_id),
                                headers=self.get_api_headers(),
                                expect_errors=True)
        # Failures will return text rather than json
        self.assertEqual(response.content_type, 'text/plain')
        self.assertEqual(response.status_code, http_client.NOT_FOUND)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_get_single(self, mock_client):
        # create a group
        context = utils.dummy_context()
        group_name = 'TestGroup'
        db_group = self._create_db_object(context, name=group_name)

        # Test that a GET operation for a valid ID works
        response = self.app.get(self.get_single_url(db_group.id),
                                headers=self.get_api_headers())
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status_code, http_client.OK)
        self.validate_entry(response.json)


# ------ API  Update Mixin
class UpdateMixin(object):

    def validate_updated_fields(self, sub_dict, full_obj):
        for key, value in sub_dict.items():
            self.assertEqual(value, full_obj.get(key))

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_update_success(self, mock_client):
        context = utils.dummy_context()
        single_obj = self._create_db_object(context)
        update_data = self.get_update_object()
        response = self.app.patch_json(self.get_single_url(single_obj.id),
                                       headers=self.get_api_headers(),
                                       params=update_data)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status_code, http_client.OK)
        self.validate_updated_fields(update_data, response.json)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_update_empty_changeset(self, mock_client):
        context = utils.dummy_context()
        single_obj = self._create_db_object(context)
        update_data = {}
        response = self.app.patch_json(self.get_single_url(single_obj.id),
                                       headers=self.get_api_headers(),
                                       params=update_data,
                                       expect_errors=True)
        # Failures will return text rather than json
        self.assertEqual(response.content_type, 'text/plain')
        self.assertEqual(response.status_code, http_client.BAD_REQUEST)


# ------ API  Delete Mixin
class DeleteMixin(object):

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_delete_success(self, mock_client):
        context = utils.dummy_context()
        single_obj = self._create_db_object(context)
        response = self.app.delete(self.get_single_url(single_obj.id),
                                   headers=self.get_api_headers())
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status_code, http_client.OK)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_double_delete(self, mock_client):
        context = utils.dummy_context()
        single_obj = self._create_db_object(context)
        response = self.app.delete(self.get_single_url(single_obj.id),
                                   headers=self.get_api_headers())
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status_code, http_client.OK)
        # delete the same object a second time. this should fail (NOT_FOUND)
        response = self.app.delete(self.get_single_url(single_obj.id),
                                   headers=self.get_api_headers(),
                                   expect_errors=True)
        self.assertEqual(response.content_type, 'text/plain')
        self.assertEqual(response.status_code, http_client.NOT_FOUND)


class SubcloudGroupAPIMixin(APIMixin):

    API_PREFIX = '/v1.0/subcloud-groups'
    RESULT_KEY = 'subcloud_groups'
    EXPECTED_FIELDS = ['id',
                       'name',
                       'description',
                       'max_parallel_subclouds',
                       'update_apply_type',
                       'created-at',
                       'updated-at']

    def setUp(self):
        super(SubcloudGroupAPIMixin, self).setUp()
        self.fake_rpc_client.some_method = mock.MagicMock()

    def _get_test_subcloud_group_dict(self, **kw):
        # id should not be part of the structure
        group = {
            'name': kw.get('name', SAMPLE_SUBCLOUD_GROUP_NAME),
            'description': kw.get('description',
                                  SAMPLE_SUBCLOUD_GROUP_DESCRIPTION),
            'update_apply_type': kw.get(
                'update_apply_type',
                SAMPLE_SUBCLOUD_GROUP_UPDATE_APPLY_TYPE),
            'max_parallel_subclouds': kw.get(
                'max_parallel_subclouds',
                SAMPLE_SUBCLOUD_GROUP_MAX_PARALLEL_SUBCLOUDS)
        }
        return group

    def _post_get_test_subcloud_group(self, **kw):
        post_body = self._get_test_subcloud_group_dict(**kw)
        return post_body

    # The following methods are required for subclasses of APIMixin

    def get_api_prefix(self):
        return self.API_PREFIX

    def get_result_key(self):
        return self.RESULT_KEY

    def get_expected_api_fields(self):
        return self.EXPECTED_FIELDS

    def get_omitted_api_fields(self):
        return []

    def _create_db_object(self, context, **kw):
        creation_fields = self._get_test_subcloud_group_dict(**kw)
        return db_api.subcloud_group_create(context, **creation_fields)

    def get_post_object(self):
        return self._post_get_test_subcloud_group()

    def get_update_object(self):
        update_object = {
            'description': 'Updated description'
        }
        return update_object


# Combine Subcloud Group API with mixins to test post, get, update and delete
class TestSubcloudGroupPost(testroot.DCManagerApiTest,
                            SubcloudGroupAPIMixin,
                            PostMixin):
    def setUp(self):
        super(TestSubcloudGroupPost, self).setUp()

    def verify_post_failure(self, response):
        # Failures will return text rather than json
        self.assertEqual(response.content_type, 'text/plain')
        self.assertEqual(response.status_code, http_client.BAD_REQUEST)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_create_with_numerical_name_fails(self, mock_client):
        # A numerical name is not permitted. otherwise the 'get' operations
        # which support getting by either name or ID could become confused
        # if a name for one group was the same as an ID for another.
        ndict = self.get_post_object()
        ndict['name'] = '123'
        response = self.app.post_json(self.get_api_prefix(),
                                      ndict,
                                      headers=self.get_api_headers(),
                                      expect_errors=True)
        self.verify_post_failure(response)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_create_with_blank_name_fails(self, mock_client):
        # An empty name is not permitted
        ndict = self.get_post_object()
        ndict['name'] = ''
        response = self.app.post_json(self.get_api_prefix(),
                                      ndict,
                                      headers=self.get_api_headers(),
                                      expect_errors=True)
        self.verify_post_failure(response)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_create_with_default_name_fails(self, mock_client):
        # A name that is the same as the 'Default' group is not permitted.
        # This would be a duplicate, and names must be unique.
        ndict = self.get_post_object()
        ndict['name'] = 'Default'
        response = self.app.post_json(self.get_api_prefix(),
                                      ndict,
                                      headers=self.get_api_headers(),
                                      expect_errors=True)
        self.verify_post_failure(response)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_create_with_empty_description_fails(self, mock_client):
        # An empty description is considered invalid
        ndict = self.get_post_object()
        ndict['description'] = ''
        response = self.app.post_json(self.get_api_prefix(),
                                      ndict,
                                      headers=self.get_api_headers(),
                                      expect_errors=True)
        self.verify_post_failure(response)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_create_with_bad_apply_type(self, mock_client):
        # update_apply_type must be either 'serial' or 'parallel'
        ndict = self.get_post_object()
        ndict['update_apply_type'] = 'something_invalid'
        response = self.app.post_json(self.get_api_prefix(),
                                      ndict,
                                      headers=self.get_api_headers(),
                                      expect_errors=True)
        self.verify_post_failure(response)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_create_with_bad_max_parallel_subclouds(self, mock_client):
        # max_parallel_subclouds must be an integer between 1 and 100
        ndict = self.get_post_object()
        # All the entries in bad_values should be considered invalid
        bad_values = [0, 101, -1, 'abc']
        for bad_value in bad_values:
            ndict['max_parallel_subclouds'] = bad_value
            response = self.app.post_json(self.get_api_prefix(),
                                          ndict,
                                          headers=self.get_api_headers(),
                                          expect_errors=True)
            self.verify_post_failure(response)


class TestSubcloudGroupGet(testroot.DCManagerApiTest,
                           SubcloudGroupAPIMixin,
                           GetMixin):

    def setUp(self):
        super(TestSubcloudGroupGet, self).setUp()
        # Override initial_list_size. Default group is setup during db sync
        self.initial_list_size = 1

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_get_single_by_name(self, mock_client):
        # create a group
        context = utils.dummy_context()
        # todo(abailey) make this a generic method
        group_name = 'TestGroup'
        self._create_db_object(context, name=group_name)

        # Test that a GET operation for a valid ID works
        response = self.app.get(self.get_single_url(group_name),
                                headers=self.get_api_headers())
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status_code, http_client.OK)
        self.validate_entry(response.json)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_list_subclouds_empty(self, mock_client):
        # API GET on: subcloud-groups/<uuid>/subclouds
        uuid = 1  # The Default Subcloud Group is always ID=1
        url = '%s/%s/subclouds' % (self.get_api_prefix(), uuid)
        response = self.app.get(url,
                                headers=self.get_api_headers())
        # This API returns 'subclouds' rather than 'subcloud-groups'
        self.assertIn('subclouds', response.json)
        # no subclouds exist yet, so this length should be zero
        result_list = response.json.get('subclouds')
        self.assertEqual(0, len(result_list))

    def _create_subcloud_db_object(self, context):
        creation_fields = {
            'name': FAKE_SUBCLOUD_DATA.get('name'),
            'description': FAKE_SUBCLOUD_DATA.get('description'),
            'location': FAKE_SUBCLOUD_DATA.get('location'),
            'software_version': FAKE_SUBCLOUD_DATA.get('software_version'),
            'management_subnet': FAKE_SUBCLOUD_DATA.get('management_subnet'),
            'management_gateway_ip':
                FAKE_SUBCLOUD_DATA.get('management_gateway_ip'),
            'management_start_ip':
                FAKE_SUBCLOUD_DATA.get('management_start_ip'),
            'management_end_ip': FAKE_SUBCLOUD_DATA.get('management_end_ip'),
            'systemcontroller_gateway_ip':
                FAKE_SUBCLOUD_DATA.get('systemcontroller_gateway_ip'),
            'deploy_status': FAKE_SUBCLOUD_DATA.get('deploy_status'),
            'openstack_installed':
                FAKE_SUBCLOUD_DATA.get('openstack_installed'),
            'group_id': FAKE_SUBCLOUD_DATA.get('group_id', 1)
        }
        return db_api.subcloud_create(context, **creation_fields)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_list_subclouds_populated(self, mock_client):
        # subclouds are to Default group by default (unless specified)
        context = utils.dummy_context()
        self._create_subcloud_db_object(context)

        # API GET on: subcloud-groups/<uuid>/subclouds
        uuid = 1  # The Default Subcloud Group is always ID=1
        url = '%s/%s/subclouds' % (self.get_api_prefix(), uuid)
        response = self.app.get(url,
                                headers=self.get_api_headers())
        # This API returns 'subclouds' rather than 'subcloud-groups'
        self.assertIn('subclouds', response.json)
        # the subcloud created earlier will have been queried
        result_list = response.json.get('subclouds')
        self.assertEqual(1, len(result_list))


class TestSubcloudGroupUpdate(testroot.DCManagerApiTest,
                              SubcloudGroupAPIMixin,
                              UpdateMixin):
    def setUp(self):
        super(TestSubcloudGroupUpdate, self).setUp()

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_update_invalid_apply_type(self, mock_client):
        context = utils.dummy_context()
        single_obj = self._create_db_object(context)
        update_data = {
            'update_apply_type': 'something_bad'
        }
        response = self.app.patch_json(self.get_single_url(single_obj.id),
                                       headers=self.get_api_headers(),
                                       params=update_data,
                                       expect_errors=True)
        # Failures will return text rather than json
        self.assertEqual(response.content_type, 'text/plain')
        self.assertEqual(response.status_code, http_client.BAD_REQUEST)

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_update_invalid_max_parallel(self, mock_client):
        context = utils.dummy_context()
        single_obj = self._create_db_object(context)
        update_data = {
            'max_parallel_subclouds': -1
        }
        response = self.app.patch_json(self.get_single_url(single_obj.id),
                                       headers=self.get_api_headers(),
                                       params=update_data,
                                       expect_errors=True)
        # Failures will return text rather than json
        self.assertEqual(response.content_type, 'text/plain')
        self.assertEqual(response.status_code, http_client.BAD_REQUEST)


class TestSubcloudGroupDelete(testroot.DCManagerApiTest,
                              SubcloudGroupAPIMixin,
                              DeleteMixin):
    def setUp(self):
        super(TestSubcloudGroupDelete, self).setUp()

    @mock.patch.object(rpc_client, 'ManagerClient')
    def test_delete_default_fails(self, mock_client):
        default_zone_id = 1
        response = self.app.delete(self.get_single_url(default_zone_id),
                                   headers=self.get_api_headers(),
                                   expect_errors=True)
        # Failures will return text rather than json
        self.assertEqual(response.content_type, 'text/plain')
        self.assertEqual(response.status_code, http_client.BAD_REQUEST)