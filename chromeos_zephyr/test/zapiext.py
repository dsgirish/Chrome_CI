# -*- coding: utf-8 -*
#!/usr/bin/env python
'''
A child class of the base class ZAPI by extending the functionalities to 
support deleting issues, updating issue comments, maintaining issue links, 
maintaining test steps, deleting test cycles.
'''
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import os
import re
import logging
import time
from json import dumps
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

#add the parent folder to system path
sys.path.append( os.path.split((os.path.split( os.path.realpath( sys.argv[0] ) )[0]))[0])
from zapi import ZAPI

class ZAPIEXT(ZAPI):
    #reserved methods for future use
    def __init__(self, url, username=None, password=None, disableSSL=None, cert=None):
        super(ZAPIEXT,self).__init__(url, username, password, disableSSL, cert)

    def deleteCycle(self, cycleId):
        """
        delete a test cycle
        :params cycleId: cycle Id
        """
        data = dumps({
            "cycleId": str(cycleId)
        })
        res = self.session.delete(
            self.baseURL + "/rest/zapi/latest/cycle/" + str(cycleId), headers=self.headers)
        if res.ok:
            progress = 0
            estimateDuration = self.timeout
            acturalDuration = 0
            while progress <> 1:
                time.sleep(estimateDuration)
                acturalDuration += estimateDuration
                progress = self.getJobProgressStatus(res.json()["jobProgressToken"], "cycle_delete_job_progress")
            logging.debug("deleteCycle Duration - estimated: %d, actual: %d" % (10, acturalDuration))
            return
        else:
            self.reportErrorAndExit(res, "Failed to delete a test cycle!")

    def createTestIssue(self, data):
        """
        Create a new Zephyr for JIRA Test issue in specified project
        :params data: dict type of test data, data detail from /rest/api/2/issue/createmeta
        :returns: test id
        """
        res = self.session.post(
            self.baseURL + "/rest/api/2/issue/", data=data, headers=self.headers)
        newTest = res.json()
        newTestId = res.json()['id']
        logging.info("Test Issue Created! New ID is:" % newTestId)
        return newTest

    def deleteIssues(self, keys):
        """
        delete an issue from JIRA
        :params keys: list type of issues
        """
        deletedKeys = []
        for key in keys:
            res = self.session.delete(
                self.baseURL + "/rest/api/2/issue/" + key, headers=self.headers)
            if res.ok:
                deletedKeys.append(key)
            else:
                logging.info("Met error when deleting %s: %s" % (key, res.json()['errorMessages']))
                self.reportErrorAndExit(res)
        logging.info("%d issues deleted." % len(deletedKeys))
        return

    def getTestStep(self, testId, stepId):
        """
        Get step data for specific testId and stepId
        :params testId: test id, string
        :params stepId: step id, string
        :returns: step data, json
        """
        res = self.session.get(
            self.baseURL + "/rest/zapi/latest/teststep/" + str(testId) + "/" + str(stepId), headers=self.headers)
        return res.json()

    def getTests(self, summaryText, projectKey):
        """
        Get tests for summary test
        Reservered for future use
        :params summaryText: Test summary, string
        :returns: tests data, list of json
        """
        jql = 'project = ' + projectKey + ' AND summary ~ ' + summaryText + ' ORDER BY key DESC'
        res = self.session.get(
            self.baseURL + '/rest/api/2/search?fields=summary&jql=' + jql, headers=self.headers)
        issues = []
        if res.ok:
            js_data = res.json()
            if 'issues' not in js_data:
                logging.warn(js_data['msg'])
            else:
                for issue in js_data['issues']:
                    if summaryText == issue['fields']['summary']:
                        issues.append(issue)

        return issues

    def getIssueID(self, issueKey):
        """
        Get issueId for issueKey
        Reservered for future use
        :params issueKey: issueKey, string
        :returns: issueId, string
        """
        res = self.session.get(
            self.baseURL + '/rest/api/2/issue/' + issueKey + '?fields=id', headers=self.headers)
        if res.ok:
            return res.json()['id']
        return None

    def executeCreate(self, cycleId, issueId, projectId):
        """
        create an execution
        Reservered for future use
        :params cycleId: cycle Id
        :params issueId: issue Id
        :params projectId: project Id
        :returns: execution Id, string
        """
        data = dumps({
            "cycleId": str(cycleId),
            "issueId": str(issueId),
            "projectId": str(projectId)
        })
        res = self.session.post(
            self.baseURL + "/rest/zapi/latest/execution/", data=data, headers=self.headers)
        if res.ok:
            return res.json().keys()[0]
        return -1

    def listIssues(self, filterName=None, filterId=None):
        """
        list all issues by filterName or filterId
        reservered for future use
        :params filterName: filter Name
        :params filterId: filter Id
        :returns: list of dict
        """
        def getIssuesByFilterId(filterId):
            res = self.session.get(
                self.baseURL + '/rest/api/2/filter/' + str(filterId), headers=self.headers)
            js_data = res.json()
            if not res.ok:
                logging.error(js_data["errorMessages"][0])
                if "errorMessages" in res.json():
                    logging.error(res.json()["errorMessages"])
                sys.exit(1)
            searchURL = js_data['searchUrl']
            res = self.session.get(
                searchURL + '&fields=summary,description,labels', headers=self.headers)
            js_data = res.json()
            if res.ok:
                return js_data['issues']
            else:
                logging.error(js_data["errorMessages"][0])
                if "errorMessages" in res.json():
                    logging.error(res.json()["errorMessages"])
                sys.exit(1)
        if filterId is not None:
            return getIssuesByFilterId(filterId)
        if filterName is not None:
            res = self.session.get(
                self.baseURL + '/rest/zapi/latest/picker/filters?query=' + filterName, headers=self.headers)
            if res.ok:
                js_data = res.json()
                if 'options' in js_data:
                    if len(js_data['options']) > 1:
                        logging.error("Multiple filter found")
                        for option in js_data['options']:
                            logging.debug("%s %s" % (option['id'], option['value']))
                        sys.exit(1)
                    else:
                        filter_id = js_data['options'][0]['id']
                        return getIssuesByFilterId(filter_id)
                else:
                    logging.warn(
                        'No filter found from your filter name search: ' + filterName)
                    return []

    def editIssue(self, issueKey, data):
        """
        edit an issue
        :params issueKey: issueKey
        :params data: json of issue
        :returns:
        :raises:
        """
        res = self.session.put(
            self.baseURL + '/rest/api/2/issue/' + issueKey, data=data, headers=self.headers)
        if not res.ok:
            res.raise_for_status()

    def getCycleExecutionCount(self, cycleId):
        """
        Not used, to be removed
        :params projectId: project id
        :params cycleName: cycle name
        :params versionId: project version id
        :returns: list of dict
        """
        url = self.baseURL + \
            '/rest/zapi/latest/cycle?projectId=' + str(projectId)
        if versionId is not None:
            url += '&versionId=%s' % str(versionId)
        res = self.session.get(url, headers=self.headers)
        js_data = res.json()
        if versionId is not None:
            for _cycleId, cycle_info in js_data.items():
                if isinstance(cycle_info, dict):
                    if cycle_info['name'] == cycleName:
                        return _cycleId
        else:
            cycles = []
            for _, cycle_list in js_data.items():
                for cycle in cycle_list:
                    for _cycleId, cycle_info in cycle.items():
                        if isinstance(cycle_info, dict):
                            if cycle_info['name'] == cycleName:
                                cycles.append(_cycleId)
            if len(cycles) > 1:
                raise(
                    'Multiple cycles found for cycle Name: %s, and you must specifiy project version' %
                      cycleName)
            else:
                return cycles[0]

    def testsByRequirement(self, issues):
        """
        get tests traceability data by requirements
        :params issues: list of test ids
        :returns: a list of tests
        """
        keylist = ",".join(issues)
        res = self.session.get(self.baseURL + "/rest/zapi/latest/traceability/testsByRequirement?requirementIdOrKeyList=" + keylist, headers=self.headers)
        if res.ok:
            return res.json()
        else:
            return -1

    def executionsByDefect(self, issue):
        """
        get traceability data by defects
        :params issues: list of defect ids
        :returns: a list of executions
        """
        res = self.session.get(self.baseURL + "/rest/zapi/latest/traceability/executionsByDefect?defectIdOrKey=" + issue, headers=self.headers)
        if res.ok:
            return res.json()
        else:
            return -1

    def createTestStep(self, testId, step):
        """
        Use new Test issue ID created to add a new test step
        :params testId: test id, string
        :params step: dict type of test step
        :returns: test step id, string
        """
        #if "orderid" in step:
        #    step.pop("orderid")
        zephyrStep = {}
        if "step" in step:
            zephyrStep["step"] = step["step"]
        if "data" in step:
            zephyrStep["data"] = step["data"]
        if "result" in step:
            zephyrStep["result"] = step["result"]

        res = self.session.post(
            self.baseURL + "/rest/zapi/latest/teststep/" + str(testId), data=dumps(zephyrStep), headers=self.headers)
        if res.ok:
            newTestStepId = res.json()['id']
            return newTestStepId
        else:
            self.reportErrorAndExit(res, "Failed to create test steps!")

    def createTestSteps(self, testId, steps):
        """
        Use new Test issue ID created to add new test steps
        :params testId: test id, string
        :params steps: dict type of test steps
        """
        for step in steps:
            self.createTestStep(testId, step)

    def getTestSteps(self, testId):
        """
        Get all step data for specific testId
        :params testId: test id, string
        :returns: step data, list of json
        """
        res = self.session.get(
            self.baseURL + "/rest/zapi/latest/teststep/" + str(testId), headers=self.headers)
        if res.ok:
            return res.json()["stepBeanCollection"]
        else:
            self.reportErrorAndExit(res, "Failed to get test steps!")

    def deleteTestStep(self, testId, stepId):
        """
        Get all step data for specific testId
        :params testId: test id, string
        :params stepId: step id, string
        """
        res = self.session.delete(
            self.baseURL + "/rest/zapi/latest/teststep/" + str(testId) + "/" + str(stepId), headers=self.headers)
        if not res.ok:
            self.reportErrorAndExit(res, "Failed to delete a test step!")

    def updateTestStep(self, testId, stepId, data):
        """
        Update step data for specific testId and stepId
        :params testId: test id, string
        :params stepId: step id, string
        :params data: step, data, result
        """
        #improvement to be done for not required data fields like orderid, teststep execution status, defects, results.
        if "orderid" in data:
            data.pop("orderid")
        res = self.session.put(
            self.baseURL + "/rest/zapi/latest/teststep/" + str(testId) + "/" + str(stepId), data=dumps(data), headers=self.headers)
        if not res.ok:
            logging.error("Failed to update a test step!")
            sys.exit(1)

    def updateIssueLinks(self, issueKey, inputIssues, existingIssues, linkName, linkType, linkIssueType, updateLinks):
        """
        update linkages between issues
        :params issueKey: issue initiating the link
        :params inputIssues: issues to link
        :params linkType: the relationship between issues
        :params existingIssues: existing outward issues in JIRA
        :params updateLinks: tag to decide whether to delete issue links not in the outward issue list
        """
        for issue in inputIssues:
            if issue in existingIssues:
               existingLinkId = existingIssues[issue]
               existingLinkType = linkName
               logging.debug("The linkage already exists: %s is %s for %s" % (issueKey, linkType, issue))
               continue
            else:
               self.createIssueLink(issueKey, issue, linkName, linkType, linkIssueType)

        if updateLinks:
            for issue in existingIssues:
                existingLinkId = existingIssues[issue]
                if issue not in inputIssues:
                    logging.debug("Deleting the linkage: %s is %s for %s" % (issueKey, linkType, issue))
                    self.deleteIssueLink(existingLinkId)

    def createIssueLink(self, issueKey, issue, linkName, linkType, linkIssueType):
        """
        create linkage between two issues
        :params inwardIssue: issue initiating the link
        :params outwardIssue: issue to link
        :params linkName: the relationship between two issues
        :params linkType: the link direction, inwardIssue or outwardIssue
        """
        if linkIssueType == "outwardIssue":
            inwardIssue = issueKey
            outwardIssue = issue
        else:
            inwardIssue = issue
            outwardIssue = issueKey
        data = dumps({
            "type": {
                "name": linkName
            },
            "inwardIssue": {
                "key": inwardIssue
            },
            "outwardIssue": {
                "key": outwardIssue
            }
        })
        res = self.session.post(
            self.baseURL + "/rest/api/2/issueLink", data=data, headers=self.headers)
        if not res.ok:
            logging.error("Failed to create an issue link: %s %s %s!" % (issueKey, linkType, issue))
            logging.debug("linkName: %s" % linkName)
            logging.debug("data: %s" % data)
            self.reportErrorAndExit(res)

    def deleteIssueLink(self, linkId):
        """
        delete linkage between two issues
        :params linkId: the id of the link between two issues
        """
        res = self.session.delete(
            self.baseURL + "/rest/api/2/issueLink/" + str(linkId), headers=self.headers)
        if not res.ok:
            self.reportErrorAndExit(res, "Failed to delete an issue link!")
