# Licensed to the StackStorm, Inc ('StackStorm') under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from six.moves import http_client

from st2api.controllers.resource import ResourceController
from st2common import log as logging
from st2common.util import action_db as action_utils
from st2common.util import system_info
from st2common.services import executions
from st2common.rbac.types import PermissionType
from st2common.rbac import utils as rbac_utils
from st2common.router import abort
from st2common.models.api.execution import ActionExecutionAPI
from st2common.persistence.execution import ActionExecution

__all__ = [
    'InquiriesController'
]

LOG = logging.getLogger(__name__)


class InquiriesController(ResourceController):
    """Everything in this controller is just a PoC at this point. Just getting my feet wet and
       using dummy data before diving into the actual back-end queries.
    """
    supported_filters = {}

    # No data model currently exists for Inquiries, so we're "borrowing" ActionExecutions
    model = ActionExecutionAPI
    access = ActionExecution

    def get_all(self, requester_user=None):

        # TODO(mierdin): Evaluate which options need to be carried over from execution list
        # And update client with those options (such as "limit")

        raw_inquiries = super(InquiriesController, self)._get_all(
            raw_filters={'status': 'pending'}
        )

        inquiries = []
        for raw_inquiry in json.loads(raw_inquiries.body):
            new_inquiry = self._transform_inquiry(raw_inquiry)
            if new_inquiry:
                inquiries.append(new_inquiry)

        return inquiries

    def get_one(self, iid, requester_user=None):
        """Retrieve a single Inquiry
        """

        raw_inquiry = self._get_one_by_id(
            id=iid,
            requester_user=requester_user,
            permission_type=PermissionType.EXECUTION_VIEW
        )
        return self._transform_inquiry(raw_inquiry.__dict__)

    def _transform_inquiry(self, raw_inquiry):
        """Transform ActionExecutionAPI model into something specific to Inquiries

        We're borrowing the ActionExecution data model for the time being, so we
        need to pick and choose fields from this to form a new franken-model for Inquiries
        so we don't return a bunch of extra crap. The idea is to provide data in response to
        requests that make it look like Inquiry is its own data model.
        """

        # The status filter returns all executions that either HAVE that status, or
        # have subexecutions with that status, so we want to make sure we're ONLY
        # returning Inquiries that represent subexecutions, not workflows
        if not raw_inquiry.get("parent"):
            return None

        # Retrieve response schema from parameters if exists.
        # If not, assume default from runner.
        schema = raw_inquiry["parameters"].get(
            "schema",
            # TODO(mierdin): Gross.
            raw_inquiry["runner"]["runner_parameters"]["schema"]["default"]
        )

        return {
            "id": raw_inquiry.get("id"),
            "parent": raw_inquiry.get("parent"),
            "tag": raw_inquiry["parameters"].get("tag", ""),
            "users": raw_inquiry["parameters"].get("users", []),
            "roles": raw_inquiry["parameters"].get("roles", []),
            "schema": schema
        }

    def put(self, iid, rdata, requester_user):
        """
        This function in particular will:

        1. Retrieve details of the inquiry via ID (i.e. params like schema)
        2. Determine permission of this user to respond to this Inquiry
        3. Validate the body of the response against the schema parameter for this inquiry,
           (reject if invalid)
        4. Update inquiry's execution result with a successful status and the validated response
        5. Retrieve parent execution for the inquiry, and pass this to action_service.request_resume

        TODO(mierdin): The header param (iid) and the body field (rdata.id) are redundant, but
        other API endpoints do the same. Should figure out if this should/can be pruned - you'll
        only actually use one of them
        """

        LOG.debug("Inquiry %s received response payload: %s" % (iid, rdata.response))

        #
        # Retrieve details of the inquiry via ID (i.e. params like schema)
        #
        existing_inquiry = self._get_one_by_id(
            id=iid,
            requester_user=requester_user,
            permission_type=PermissionType.EXECUTION_VIEW
        )
        LOG.info("Got existing inquiry ID: %s" % existing_inquiry.id)

        #
        # Determine permission of this user to respond to this Inquiry
        #
        if not requester_user:

            # TODO(mierdin): do we need to update openapi def with possible error responses?
            abort(
                http_client.FORBIDDEN,
                'Requesting user must be provided to respond to an Inquiry'
            )
        roles = existing_inquiry.parameters.get('roles')
        users = existing_inquiry.parameters.get('users')
        if roles:
            for role in roles:
                LOG.info("Checking user %s is in role %s" % (requester_user, role))
                LOG.info(rbac_utils.user_has_role(requester_user, role))
                # TODO(mierdin): Note that this will always return True if Rbac is not enabled
                # Need to test with rbac enabled and configured
                if rbac_utils.user_has_role(requester_user, role):
                    break
            else:
                # TODO(mierdin) figure out how to return this in an HTTP code
                # (and modify the openapi def accordingly)
                abort(http_client.FORBIDDEN, 'Insufficient permission to respond to this Inquiry.')
        if users:
            if requester_user not in users:
                # TODO(mierdin) figure out how to return this in an HTTP code
                # (and modify the openapi def accordingly)
                abort(http_client.FORBIDDEN, 'Insufficient permission to respond to this Inquiry.')

        #
        # Validate the body of the response against the schema parameter for this inquiry,
        #

        #
        # Update inquiry's execution result with a successful status and the validated response
        #
        # stamp liveaction with process_info
        runner_info = system_info.get_process_info()
        # Update liveaction status to "running"
        # liveaction_db = action_utils.update_liveaction_status(
        #     status=action_constants.LIVEACTION_STATUS_RUNNING,
        #     runner_info=runner_info,
        #     liveaction_id=liveaction_db.id)
        # self._running_liveactions.add(liveaction_db.id)
        # action_execution_db = executions.update_execution(liveaction_db)

        return "Received data for inquiry %s" % id

        response = getattr(rdata, 'response')

        return {
            "id": iid,
            "response": response
        }


inquiries_controller = InquiriesController()
